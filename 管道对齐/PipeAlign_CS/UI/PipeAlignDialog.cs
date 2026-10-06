using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Windows.Forms;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET.WinForms;

namespace PipeAlign
{
    /// <summary>
    /// 管道标高对齐窗口（开发指南 §26 的 <c>PipeAlignDialog</c>）。
    /// <para>
    /// 采用 Bentley SDK 示例（<c>QueryPipeWithPortsExample</c>）的 <see cref="Adapter"/> +
    /// <c>AttachAsTopLevelForm</c> + <c>WindowManager.DockPanel</c> 非模态窗口做法 ——
    /// 这是官方示例里验证过的宿主方式，比自建 WPF 宿主风险低。
    /// </para>
    /// <para>
    /// ⚠️ 关键约定：点取工具的回调里**只把元素 ID 入队**，真正的 EC 读取由
    /// <see cref="ProcessPendingPicks"/> 在 <c>BeginInvoke</c> 排到消息队列之后执行。
    /// 实测在工具回调内部访问 EC 实例会让 OPM 崩溃。
    /// </para>
    /// </summary>
    internal sealed partial class PipeAlignDialog : Adapter
    {
        private static PipeAlignDialog _instance;

        private readonly PipeAlignSession _session;
        private readonly Queue<PendingPick> _pending = new Queue<PendingPick>();
        private readonly object _pendingLock = new object();

        private Bentley.Windowing.WindowContent _windowContent;
        private Timer _pickTimer;
        private bool _closing;
        private bool _loadingUi = true;
        private bool _applying;
        private bool _autoPreviewPending;
        private DateTime _previewAfter;

        // ---- 控件 ----
        private Label _referenceLabel;
        private Button _pickReferenceButton;
        private RadioButton _bottomRadio;
        private RadioButton _centerRadio;
        private RadioButton _topRadio;
        private RadioButton _surfacePipeRadio;
        private RadioButton _surfaceInsulationRadio;
        private RadioButton _scopeSingleRadio;
        private RadioButton _scopeGroupRadio;
        private RadioButton _scopeZRadio;
        private NumericUpDown _zDeltaInput;
        private NumericUpDown _toleranceInput;
        private Button _pickTargetsButton;
        private Button _selectionSetButton;
        private Button _removeTargetButton;
        private Button _clearTargetsButton;
        private Label _targetCountLabel;
        private CheckBox _showCurrentCheck;
        private CheckBox _showTargetCheck;
        private Button _refreshPreviewButton;
        private Button _clearPreviewButton;
        private ListView _planList;
        private Label _summaryLabel;
        private Label _readoutLabel;
        private Button _applyButton;
        private Button _resetButton;
        private Button _saveOptionsButton;
        private Button _closeButton;
        private Label _statusLabel;

        private PipeAlignDialog(PipeAlignSession session)
        {
            _session = session;

            Text = "管道标高对齐 · PipeAlign";
            Name = "PipeAlignDialog";
            FormBorderStyle = FormBorderStyle.Sizable;
            StartPosition = FormStartPosition.CenterScreen;
            MinimizeBox = true;
            MaximizeBox = true;
            ShowInTaskbar = false;

            BuildUi();
            LoadSessionIntoUi();
            _loadingUi = false;

            // 点取结果的兜底通道：正常路径是 BeginInvoke（工具回调返回后立刻处理），
            // 但万一句柄尚未创建或 BeginInvoke 失败，这个定时器保证队列最终一定会被消费，
            // **而不会退化成"在工具回调里直接读 EC"**（那会让 OPM 崩溃）。
            _pickTimer = new Timer { Interval = 150 };
            _pickTimer.Tick += delegate { ProcessPendingPicks(); ProcessAutoPreview(); };
            _pickTimer.Start();
            TransactionManager.OnUndoRedoFinished += OnUndoRedoFinished;

            AttachAsTopLevelForm(PipeAlignAddIn.Instance, true);
            NETDockable = false;

            Bentley.Windowing.WindowManager windowManager =
                Bentley.Windowing.WindowManager.GetForMicroStation();
            _windowContent = windowManager.DockPanel(this, Name, Text,
                Bentley.Windowing.DockLocation.Floating);
            _windowContent.CanDockHorizontally = false;
            _windowContent.CanDockVertically = false;

            // 实测：这个窗体是被 MicroStation 的 WindowContent **框架**承载的，
            // 光调 Form.Close() 只会销毁里面那层，外面留下一个空白框架（标题栏还在、内容全空）。
            // 所以必须自己接管框架的关闭询问，并且在关闭时把框架一并关掉。
            try { _windowContent.ContentCloseQuery += OnContentCloseQuery; }
            catch { }
        }

        /// <summary>
        /// MicroStation 侧（框架标题栏的 ✕）请求关闭本内容。
        /// <para>先把点取工具与预览收干净，再让框架按 <see cref="ContentCloseAction.Dispose"/> 关闭。</para>
        /// </summary>
        private void OnContentCloseQuery(object sender, Bentley.Windowing.ContentCloseEventArgs e)
        {
            if (_closing)
            {
                // 已经在"我方主动关闭"的流程里，不要重复清理（否则会递归）。
                e.CloseAction = Bentley.Windowing.ContentCloseAction.Dispose;
                return;
            }

            _closing = true;
            CleanUp();
            e.CloseAction = Bentley.Windowing.ContentCloseAction.Dispose;
        }

        /// <summary>可重复调用的收尾：停点取、停定时器、清预览、关会话。</summary>
        private void CleanUp()
        {
            TransactionManager.OnUndoRedoFinished -= OnUndoRedoFinished;
            try { if (_pickTimer != null) _pickTimer.Stop(); }
            catch { }
            try { PipePickTool.End(); }
            catch { }
            try { _session.Close(); }
            catch { }
        }

        /// <summary>关闭窗口：**框架与窗体一起关**，否则会留一个空白框架。</summary>
        private void CloseDialog()
        {
            if (_closing)
            {
                // 已经从框架那边开始关了；这里只确保窗体本身也收掉。
                try { Close(); }
                catch { }
                return;
            }

            _closing = true;
            CleanUp();
            try { if (_windowContent != null) _windowContent.Close(); }
            catch { }
            try { Close(); }
            catch { }
        }

        /// <summary>打开（或前置）窗口。同一时刻只有一个实例。</summary>
        internal static PipeAlignDialog ShowDialog(PipeAlignSession session, AlignmentMode? mode)
        {
            if (_instance == null || _instance.IsDisposed)
            {
                _instance = new PipeAlignDialog(session);
                _instance.Show();
            }
            else
            {
                if (!_instance.Visible) _instance.Show();
                _instance.Activate();
                _instance.BringToFront();
            }

            if (mode.HasValue) _instance.SetMode(mode.Value);
            _instance._loadingUi = true;
            try { _instance.LoadSessionIntoUi(); }
            finally { _instance._loadingUi = false; }
            _instance.SetStatus(session.Scope == MoveScope.ZStretch
                ? "选择基准管和起点水平管，选择管底／中心／管顶，自动计算 Z 位移后点【应用】。"
                : "选择基准管和目标管，参数或选择变化后自动预览，点【应用】执行。");
            return _instance;
        }

        internal static bool IsOpen
        {
            get { return _instance != null && !_instance.IsDisposed; }
        }

        /// <summary>不修改模型、只打印选中管道的调试数据（指南 §31）。</summary>
        internal static void ShowDebugReport(PipeAlignSession session, bool dumpAllProperties)
        {
            string report = PipeDebugReport.Build(session, dumpAllProperties);
            MessageBox.Show(report, "PIPEALIGN DEBUG", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        // ------------------------------------------------------------------
        // 界面构建
        // ------------------------------------------------------------------

        private void BuildLegacyUi()
        {
            MinimumSize = new Size(700, 560);
            Size = new Size(760, 660);

            var root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 9,
                Padding = new Padding(10)
            };
            root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 基准管
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 参数
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 目标管
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 预览控制
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100f)); // 表
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 摘要
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 读数
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 按钮
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));   // 状态

            root.Controls.Add(BuildReferenceGroup(), 0, 0);
            root.Controls.Add(BuildParameterGroup(), 0, 1);
            root.Controls.Add(BuildTargetGroup(), 0, 2);
            root.Controls.Add(BuildPreviewGroup(), 0, 3);
            root.Controls.Add(BuildPlanList(), 0, 4);

            _summaryLabel = new Label
            {
                AutoSize = true,
                Padding = new Padding(3, 6, 3, 2),
                Text = "尚未计算。"
            };
            root.Controls.Add(_summaryLabel, 0, 5);

            _readoutLabel = new Label
            {
                AutoSize = true,
                Padding = new Padding(3, 0, 3, 4),
                ForeColor = Color.DimGray,
                Text = "读数：—"
            };
            root.Controls.Add(_readoutLabel, 0, 6);

            root.Controls.Add(BuildButtonRow(), 0, 7);

            _statusLabel = new Label
            {
                AutoSize = false,
                Dock = DockStyle.Fill,
                Height = 38,
                Padding = new Padding(3, 4, 3, 0),
                ForeColor = Color.FromArgb(0, 70, 140),
                Text = "就绪。"
            };
            root.Controls.Add(_statusLabel, 0, 8);

            Controls.Add(root);
        }

        private Control BuildReferenceGroup()
        {
            var group = new GroupBox
            {
                Text = "01 基准管（插件从它取得目标标高）",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(8)
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 3,
                AutoSize = true
            };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 70f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

            layout.Controls.Add(new Label { Text = "当前：", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
            _referenceLabel = new Label
            {
                Text = "（未选择）",
                AutoSize = true,
                Anchor = AnchorStyles.Left,
                ForeColor = Color.DimGray
            };
            layout.Controls.Add(_referenceLabel, 1, 0);

            _pickReferenceButton = new Button { Text = "选择基准管", AutoSize = true };
            _pickReferenceButton.Click += PickReference_Click;
            layout.Controls.Add(_pickReferenceButton, 2, 0);

            group.Controls.Add(layout);
            return group;
        }

        private Control BuildParameterGroup()
        {
            var group = new GroupBox
            {
                Text = "02 对齐方式与表面模式（程序不会替你猜表面）",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(8)
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 5,
                RowCount = 2,
                AutoSize = true
            };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 70f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 70f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));

            layout.Controls.Add(new Label { Text = "对齐基准：", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
            var modePanel = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = false };
            _bottomRadio = new RadioButton { Text = "管底", AutoSize = true, Checked = true };
            _centerRadio = new RadioButton { Text = "管中心", AutoSize = true };
            _topRadio = new RadioButton { Text = "管顶", AutoSize = true };
            _bottomRadio.CheckedChanged += Mode_Changed;
            _centerRadio.CheckedChanged += Mode_Changed;
            _topRadio.CheckedChanged += Mode_Changed;
            modePanel.Controls.Add(_bottomRadio);
            modePanel.Controls.Add(_centerRadio);
            modePanel.Controls.Add(_topRadio);
            layout.Controls.Add(modePanel, 1, 0);

            layout.Controls.Add(new Label { Text = "表面模式：", AutoSize = true, Anchor = AnchorStyles.Left }, 2, 0);
            var surfacePanel = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = false };
            _surfacePipeRadio = new RadioButton { Text = "管道外表面", AutoSize = true, Checked = true };
            _surfaceInsulationRadio = new RadioButton { Text = "保温层外表面", AutoSize = true };
            _surfacePipeRadio.CheckedChanged += Surface_Changed;
            _surfaceInsulationRadio.CheckedChanged += Surface_Changed;
            surfacePanel.Controls.Add(_surfacePipeRadio);
            surfacePanel.Controls.Add(_surfaceInsulationRadio);
            layout.Controls.Add(surfacePanel, 3, 0);

            var tolerancePanel = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = false };
            tolerancePanel.Controls.Add(new Label { Text = "水平容差：", AutoSize = true, Anchor = AnchorStyles.Left });
            _toleranceInput = new NumericUpDown
            {
                DecimalPlaces = 3,
                Increment = 0.5M,
                Minimum = 0M,
                Maximum = 1000M,
                Width = 80
            };
            _toleranceInput.ValueChanged += Tolerance_Changed;
            tolerancePanel.Controls.Add(_toleranceInput);
            tolerancePanel.Controls.Add(new Label { Text = "mm", AutoSize = true, Anchor = AnchorStyles.Left });
            layout.Controls.Add(tolerancePanel, 4, 0);

            layout.Controls.Add(new Label { Text = "移动范围：", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 1);
            var scopePanel = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true };
            _scopeSingleRadio = new RadioButton
            {
                Text = "只移动选中的管道",
                AutoSize = true,
                Checked = true
            };
            _scopeGroupRadio = new RadioButton
            {
                Text = "连同连通对象一起移动（Move Group）",
                AutoSize = true
            };
            _scopeSingleRadio.CheckedChanged += Scope_Changed;
            _scopeGroupRadio.CheckedChanged += Scope_Changed;
            scopePanel.Controls.Add(_scopeSingleRadio);
            scopePanel.Controls.Add(_scopeGroupRadio);
            _scopeZRadio = new RadioButton { Text = "锁 Z 轴（立管伸缩）", AutoSize = true };
            _scopeZRadio.CheckedChanged += Scope_Changed;
            scopePanel.Controls.Add(_scopeZRadio);
            scopePanel.Controls.Add(new Label { Text = "Z 位移 mm：", AutoSize = true });
            _zDeltaInput = new NumericUpDown
            {
                DecimalPlaces = 2, Increment = 10M, Minimum = -1000000M, Maximum = 1000000M, Width = 105
            };
            _zDeltaInput.ValueChanged += delegate
            {
                if (_loadingUi || _closing) return;
                _session.ZMoveDeltaMm = (double)_zDeltaInput.Value;
                InvalidatePlan("Z 位移已更新。");
            };
            scopePanel.Controls.Add(_zDeltaInput);
            layout.Controls.Add(scopePanel, 1, 1);
            layout.SetColumnSpan(scopePanel, 4);

            group.Controls.Add(layout);
            return group;
        }

        private Control BuildTargetGroup()
        {
            var group = new GroupBox
            {
                Text = "03 目标管（要移动的管道，可多选）",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(8)
            };

            var layout = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };

            _pickTargetsButton = new Button { Text = "选择目标管", AutoSize = true };
            _pickTargetsButton.Click += PickTargets_Click;
            layout.Controls.Add(_pickTargetsButton);

            _selectionSetButton = new Button { Text = "从选择集添加", AutoSize = true };
            _selectionSetButton.Click += SelectionSet_Click;
            layout.Controls.Add(_selectionSetButton);

            _removeTargetButton = new Button { Text = "移除选中行", AutoSize = true };
            _removeTargetButton.Click += RemoveTarget_Click;
            layout.Controls.Add(_removeTargetButton);

            _clearTargetsButton = new Button { Text = "清空目标管", AutoSize = true };
            _clearTargetsButton.Click += ClearTargets_Click;
            layout.Controls.Add(_clearTargetsButton);

            _targetCountLabel = new Label
            {
                Text = "已选 0 根",
                AutoSize = true,
                Anchor = AnchorStyles.Left,
                Padding = new Padding(10, 6, 0, 0)
            };
            layout.Controls.Add(_targetCountLabel);

            group.Controls.Add(layout);
            return group;
        }

        private Control BuildPreviewGroup()
        {
            var group = new GroupBox
            {
                Text = "04 预览（只画临时线，不改管道）",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(8)
            };

            var layout = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };

            _showCurrentCheck = new CheckBox { Text = "显示当前中心线（蓝）", AutoSize = true, Checked = true };
            _showCurrentCheck.CheckedChanged += PreviewOption_Changed;
            layout.Controls.Add(_showCurrentCheck);

            _showTargetCheck = new CheckBox { Text = "显示对齐后中心线（红）", AutoSize = true, Checked = true };
            _showTargetCheck.CheckedChanged += PreviewOption_Changed;
            layout.Controls.Add(_showTargetCheck);

            _refreshPreviewButton = new Button { Text = "预览 / 刷新", AutoSize = true };
            _refreshPreviewButton.Click += RefreshPreview_Click;
            layout.Controls.Add(_refreshPreviewButton);

            _clearPreviewButton = new Button { Text = "清除预览", AutoSize = true };
            _clearPreviewButton.Click += ClearPreview_Click;
            layout.Controls.Add(_clearPreviewButton);

            group.Controls.Add(layout);
            return group;
        }

        private Control BuildPlanList()
        {
            _planList = new ListView
            {
                Dock = DockStyle.Fill,
                View = View.Details,
                FullRowSelect = true,
                GridLines = true,
                MultiSelect = true,
                HideSelection = false
            };
            _planList.Columns.Add("管道", 130);
            _planList.Columns.Add("EC 类", 110);
            _planList.Columns.Add("外径 mm", 70, HorizontalAlignment.Right);
            _planList.Columns.Add("当前标高", 90, HorizontalAlignment.Right);
            _planList.Columns.Add("目标标高", 90, HorizontalAlignment.Right);
            _planList.Columns.Add("ΔZ mm", 80, HorizontalAlignment.Right);
            _planList.Columns.Add("连接", 120);
            _planList.Columns.Add("状态", 200);
            return _planList;
        }

        private Control BuildButtonRow()
        {
            var layout = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                WrapContents = true,
                FlowDirection = FlowDirection.LeftToRight
            };

            _applyButton = new Button { Text = "应用", AutoSize = true, Font = new Font(Font, FontStyle.Bold) };
            _applyButton.Click += Apply_Click;
            layout.Controls.Add(_applyButton);

            _resetButton = new Button { Text = "重置", AutoSize = true };
            _resetButton.Click += Reset_Click;
            layout.Controls.Add(_resetButton);

            _saveOptionsButton = new Button { Text = "保存参数到配置", AutoSize = true };
            _saveOptionsButton.Click += SaveOptions_Click;
            layout.Controls.Add(_saveOptionsButton);

            _closeButton = new Button { Text = "关闭", AutoSize = true };
            _closeButton.Click += Close_Click;
            layout.Controls.Add(_closeButton);

            return layout;
        }

        // ------------------------------------------------------------------
        // 会话 → 界面
        // ------------------------------------------------------------------

        private void LoadSessionIntoUi()
        {
            _toleranceInput.Value = (decimal)Clamp((double)_toleranceInput.Minimum,
                _session.Options.HorizontalToleranceMm, (double)_toleranceInput.Maximum);
            SetMode(_session.Mode);
            _surfacePipeRadio.Checked = _session.SurfaceMode == SurfaceMode.Pipe;
            _surfaceInsulationRadio.Checked = _session.SurfaceMode == SurfaceMode.Insulation;
            _scopeSingleRadio.Checked = _session.Scope == MoveScope.SelectedOnly;
            _scopeGroupRadio.Checked = _session.Scope == MoveScope.ConnectedGroup;
            _scopeZRadio.Checked = _session.Scope == MoveScope.ZStretch;
            _zDeltaInput.Value = (decimal)_session.ZMoveDeltaMm;
            UpdateRouteControls();
            RefreshReferenceLabel();
            RefreshTargetCount();
            RefreshPlanList();
        }

        private static double Clamp(double min, double value, double max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }

        private void SetMode(AlignmentMode mode)
        {
            _session.Mode = mode;
            _bottomRadio.Checked = mode == AlignmentMode.Bottom;
            _centerRadio.Checked = mode == AlignmentMode.Center;
            _topRadio.Checked = mode == AlignmentMode.Top;
        }

        private AlignmentMode ReadMode()
        {
            if (_topRadio.Checked) return AlignmentMode.Top;
            if (_centerRadio.Checked) return AlignmentMode.Center;
            return AlignmentMode.Bottom;
        }

        private SurfaceMode ReadSurface()
        {
            return _surfaceInsulationRadio.Checked ? SurfaceMode.Insulation : SurfaceMode.Pipe;
        }

        private void SetStatus(string message)
        {
            if (_closing) return;
            _statusLabel.Text = message ?? string.Empty;
        }

        private void RefreshReferenceLabel()
        {
            PipeInfo pipe = _session.ReferencePipe;
            if (pipe == null)
            {
                _referenceLabel.Text = "（未选择）";
                _referenceLabel.ForeColor = Color.DimGray;
                return;
            }

            _referenceLabel.ForeColor = Color.Black;
            string diameter = pipe.HasOutsideDiameter
                ? pipe.OutsideDiameterMm.Value.ToString("F1", CultureInfo.InvariantCulture)
                : "?";
            _referenceLabel.Text = string.Format(CultureInfo.InvariantCulture,
                "{0} · {1}\n外径 {2} mm · 保温 {3} mm\n{4}",
                pipe.DisplayName, pipe.ClassName, diameter,
                pipe.InsulationThicknessMm.HasValue
                    ? pipe.InsulationThicknessMm.Value.ToString("F1", CultureInfo.InvariantCulture)
                    : "—",
                string.IsNullOrEmpty(pipe.ReadWarning) ? "读取正常" : pipe.ReadWarning);
            _detailTips.SetToolTip(_referenceLabel,_referenceLabel.Text);
        }

        private void RefreshTargetCount()
        {
            _targetCountLabel.Text = string.Format(CultureInfo.InvariantCulture,
                "已选 {0} 根", _session.TargetPipes.Count);
        }

        private void RefreshPlanList()
        {
            _planList.BeginUpdate();
            try
            {
                _planList.Items.Clear();
                AlignmentPlan plan = _session.Plan;
                if (plan == null)
                {
                    _summaryLabel.Text = _session.TargetPipes.Count == 0
                        ? "尚未选择目标管。"
                        : "等待基准管或参数，选择完成后自动计算。";
                    _readoutLabel.Text = "读数：—";
                    return;
                }

                foreach (AlignmentPlanItem item in plan.Items)
                {
                    var row = new ListViewItem(item.Pipe == null ? "?" : item.Pipe.DisplayName);
                    if (item.AddedByGroup)
                    {
                        // Move Group 自动带进来的成员要看得出来，否则用户会困惑于行数变多。
                        row.Text = "＋ " + row.Text;
                        row.ToolTipText = "为保持连接完整，随选中管道一起移动的连通对象。";
                    }
                    row.SubItems.Add(item.Pipe == null ? "?" : item.Pipe.ClassName);
                    row.SubItems.Add(item.Pipe == null || !item.Pipe.HasOutsideDiameter
                        ? "—"
                        : item.Pipe.OutsideDiameterMm.Value.ToString("F1", CultureInfo.InvariantCulture));
                    row.SubItems.Add(item.Status == PlanItemStatus.Skipped && item.CurrentElevationMm == 0.0
                        ? "—"
                        : item.CurrentElevationMm.ToString("F2", CultureInfo.InvariantCulture));
                    row.SubItems.Add(item.Status == PlanItemStatus.Skipped && item.ReferenceElevationMm == 0.0
                        ? "—"
                        : item.ReferenceElevationMm.ToString("F2", CultureInfo.InvariantCulture));
                    row.SubItems.Add(item.Status == PlanItemStatus.Skipped
                        ? "—"
                        : item.DeltaZmm.ToString("+0.00;-0.00;0.00", CultureInfo.InvariantCulture));
                    row.SubItems.Add(item.Pipe == null || item.Pipe.Topology == null
                        ? "—"
                        : item.Pipe.Topology.Summary());

                    switch (item.Status)
                    {
                        case PlanItemStatus.Ready:
                            row.SubItems.Add(item.IsStretch
                                ? string.Format(CultureInfo.InvariantCulture, "立管伸缩：{0:F2} → {1:F2} mm（另一端固定）",
                                    item.Pipe.Axis.LengthMm, item.TargetAxis.LengthMm) : "将移动");
                            row.ForeColor = Color.FromArgb(0, 110, 0);
                            break;
                        case PlanItemStatus.AlreadyAligned:
                            row.SubItems.Add("已对齐，无需移动");
                            row.ForeColor = Color.DimGray;
                            break;
                        default:
                            row.SubItems.Add("跳过：" + item.SkipReason);
                            row.ForeColor = Color.FromArgb(170, 60, 0);
                            break;
                    }

                    if (item.Pipe != null) row.Tag = PipeIdentity.Key(item.Pipe);
                    _planList.Items.Add(row);
                }

                _summaryLabel.Text = string.Format(CultureInfo.InvariantCulture,
                    "基准标高 {0:F2} mm｜共 {1} 根：将移动 {2}，已对齐 {3}，跳过 {4}",
                    plan.ReferenceElevationMm, plan.Items.Count,
                    plan.ReadyCount, plan.AlreadyAlignedCount, plan.SkippedCount);

                if (!string.IsNullOrEmpty(_session.LastGroupNote))
                {
                    _summaryLabel.Text += "｜Move Group：" + _session.LastGroupNote
                        + "（行首带「＋」的是自动带进来一起移动的）";
                }

                _readoutLabel.Text = string.Format(CultureInfo.InvariantCulture,
                    "读数：基准标高 {0:F2} mm｜基准管中心标高 {1:F2} mm｜对齐模式 {2}｜表面模式 {3}｜{4}",
                    plan.ReferenceElevationMm,
                    plan.ReferencePipe != null && plan.ReferencePipe.Axis != null
                        ? plan.ReferencePipe.Axis.CenterElevationMm
                        : 0.0,
                    AlignmentModes.Chinese(plan.Mode),
                    SurfaceModes.Chinese(plan.SurfaceMode),
                    _session.DescribeTolerance());
            }
            finally
            {
                _planList.EndUpdate();
                RefreshCards();
            }
        }

        // ------------------------------------------------------------------
        // 参数变更
        // ------------------------------------------------------------------

        private void Mode_Changed(object sender, EventArgs e)
        {
            if (_closing || _loadingUi) return;
            var radio = sender as RadioButton;
            if (radio == null || !radio.Checked) return;
            _session.Mode = ReadMode();
            InvalidatePlan("对齐方式已改为「" + AlignmentModes.Chinese(_session.Mode) + "」，请重新预览。");
        }

        private void Surface_Changed(object sender, EventArgs e)
        {
            if (_closing) return;
            var radio = sender as RadioButton;
            if (radio == null || !radio.Checked) return;
            _session.SurfaceMode = ReadSurface();
            InvalidatePlan("表面模式已改为「" + SurfaceModes.Chinese(_session.SurfaceMode) + "」，请重新预览。");
        }

        private void Scope_Changed(object sender, EventArgs e)
        {
            if (_closing || _loadingUi) return;
            var radio = sender as RadioButton;
            if (radio == null || !radio.Checked) return;
            _session.Scope = _scopeZRadio.Checked ? MoveScope.ZStretch
                : _scopeGroupRadio.Checked ? MoveScope.ConnectedGroup : MoveScope.SelectedOnly;
            UpdateRouteControls();
            InvalidatePlan("移动范围已改为「" + MoveScopes.Chinese(_session.Scope) + "」，请重新预览。");
        }

        private void Tolerance_Changed(object sender, EventArgs e)
        {
            if (_closing) return;
            _session.Options.HorizontalToleranceMm = (double)_toleranceInput.Value;
            InvalidatePlan(string.Format(CultureInfo.InvariantCulture,
                "水平容差已改为 {0:G} mm，请重新预览。", _session.Options.HorizontalToleranceMm));
        }

        private void PreviewOption_Changed(object sender, EventArgs e)
        {
            if (_closing) return;
            try
            {
                if (_session.Plan != null) RefreshPreviewGraphics();
            }
            catch (Exception ex)
            {
                SetStatus("刷新预览失败：" + ex.Message);
            }
        }

        private void InvalidatePlan(string status)
        {
            _session.Plan = null;
            try { _session.Preview.Clear(); }
            catch { }
            RefreshPlanList();
            SetStatus(status);
            if (!_loadingUi && !_applying)
            {
                _autoPreviewPending = true;
                _previewAfter = DateTime.UtcNow.AddMilliseconds(350);
            }
        }

        private void UpdateRouteControls()
        {
            bool route = _session.Scope == MoveScope.ZStretch;
            _zDeltaInput.Enabled = false; // 基准与对齐方式自动计算，避免零输入误判已对齐。
            _pickReferenceButton.Enabled = true;
            _bottomRadio.Enabled = _centerRadio.Enabled = _topRadio.Enabled = true;
            _surfacePipeRadio.Enabled = _surfaceInsulationRadio.Enabled = true;
            _pickTargetsButton.Text = route ? "选择起点水平管" : "选择目标管";
        }

        private void ProcessAutoPreview()
        {
            if (_closing || _loadingUi || _applying || !_autoPreviewPending || DateTime.UtcNow < _previewAfter) return;
            _autoPreviewPending = false;
            if (_session.TargetPipes.Count == 0 || _session.ReferencePipe == null) return;
            if (!EnsurePlan()) return;
            try { RefreshPreviewGraphics(); }
            catch (Exception ex) { SetStatus("自动预览失败：" + ex.Message); }
        }

        private void OnUndoRedoFinished(object sender, OnUndoRedoFinishedEventArgs e)
        {
            if (_closing || _applying) return;
            try
            {
                BeginInvoke((MethodInvoker)delegate
                {
                    if (_closing || _applying) return;
                    _session.Preview.Clear();
                    _session.ReloadPipes(new List<string>());
                    InvalidatePlan("撤销 / 重做后已刷新管道数据。");
                });
            }
            catch (Exception ex) { SetStatus("撤销后刷新失败：" + ex.Message); }
        }

        // ------------------------------------------------------------------
        // 点取
        // ------------------------------------------------------------------

        private sealed class PendingPick
        {
            internal LocatedElement Element;
            internal PipePickTool.PickPurpose Purpose;
        }

        private void PickReference_Click(object sender, EventArgs e)
        {
            try
            {
                PipePickTool.Begin(PipePickTool.PickPurpose.Reference,
                    delegate (LocatedElement located) { QueuePick(located, PipePickTool.PickPurpose.Reference); },
                    OnPickingEnded);
                SetStatus("请在模型里点取一根水平直管作为基准管。");
            }
            catch (Exception ex)
            {
                SetStatus("无法启动点取：" + ex.Message);
            }
        }

        private void PickTargets_Click(object sender, EventArgs e)
        {
            if (_session.ReferencePipe == null)
            {
                SetStatus("请先选择基准管。");
                return;
            }
            try
            {
                PipePickTool.Begin(PipePickTool.PickPurpose.Target,
                    delegate (LocatedElement located) { QueuePick(located, PipePickTool.PickPurpose.Target); },
                    OnPickingEnded);
                SetStatus("请点取要移动的目标管，可连续左键多选；右键结束点取。");
            }
            catch (Exception ex)
            {
                SetStatus("无法启动点取：" + ex.Message);
            }
        }

        private void QueuePick(LocatedElement located, PipePickTool.PickPurpose purpose)
        {
            if (located == null) return;

            // ⚠️ 这里只入队。EC 读取必须等这次工具回调返回之后再执行。
            lock (_pendingLock)
            {
                _pending.Enqueue(new PendingPick { Element = located, Purpose = purpose });
            }

            try
            {
                if (IsHandleCreated) BeginInvoke(new Action(ProcessPendingPicks));
            }
            catch
            {
                // 交给定时器兜底；**绝不**在这里直接读 EC（会落在工具回调里）。
            }
        }

        /// <summary>在工具回调返回之后读取 EC 并更新界面。</summary>
        private void ProcessPendingPicks()
        {
            if (_closing) return;

            while (true)
            {
                PendingPick pick;
                lock (_pendingLock)
                {
                    if (_pending.Count == 0) return;
                    pick = _pending.Dequeue();
                }
                if (pick == null) continue;

                try
                {
                    PipeInfo pipe = _session.ReadPipe(pick.Element, false, true);
                    if (pick.Purpose == PipePickTool.PickPurpose.Reference)
                    {
                        if (pipe.IsFromReference)
                        {
                            SetStatus("所选管道位于参考文件中，参考文件不可修改，请选择活动模型里的管道。");
                            continue;
                        }
                        _session.SetReferencePipe(pipe);
                        RefreshReferenceLabel();
                        InvalidatePlan("基准管已选择：" + pipe.DisplayName + "。请继续选择目标管。");
                    }
                    else
                    {
                        if (_session.Scope == MoveScope.ZStretch) _session.ClearTargets();
                        if (_session.AddTargetPipe(pipe))
                        {
                            RefreshTargetCount();
                            InvalidatePlan("已添加目标管：" + pipe.DisplayName
                                + (string.IsNullOrEmpty(pipe.ReadWarning) ? "" : "（" + pipe.ReadWarning + "）"));
                            if (_session.Scope == MoveScope.ZStretch) StopPicking();
                        }
                        else
                        {
                            SetStatus("该管道已在目标列表里：" + pipe.DisplayName);
                        }
                    }
                }
                catch (Exception ex)
                {
                    SetStatus("读取所选对象失败：" + ex.Message);
                }
            }
        }

        private void OnPickingEnded()
        {
            if (_closing) return;
            SetStatus("点取已结束。");
        }

        private void SelectionSet_Click(object sender, EventArgs e)
        {
            try
            {
                if (!SelectionSetManager.IsActive() || SelectionSetManager.NumSelected() == 0)
                {
                    SetStatus("当前没有选择集。请先在模型里选中若干管道，再点本按钮。");
                    return;
                }

                uint count = SelectionSetManager.NumSelected();
                var located = new List<LocatedElement>();
                for (uint index = 0; index < count; index++)
                {
                    Element element = null;
                    DgnModelRef modelRef = null;
                    StatusInt status = SelectionSetManager.GetElement(index, ref element, ref modelRef);
                    if (status != StatusInt.Success || element == null) continue;
                    located.Add(new LocatedElement
                    {
                        ModelRef = modelRef ?? element.DgnModelRef,
                        ElementId = (ulong)element.ElementId
                    });
                }

                // 与点取同样的约定：读取放到回调之外。
                foreach (LocatedElement item in located)
                    QueuePick(item, PipePickTool.PickPurpose.Target);
            }
            catch (Exception ex)
            {
                SetStatus("读取选择集失败：" + ex.Message);
            }
        }

        private void RemoveTarget_Click(object sender, EventArgs e)
        {
            if (_pipeCards.SelectedItems.Count == 0)
            {
                SetStatus("请先在表里选中要移除的行。");
                return;
            }

            foreach (ListViewItem row in _pipeCards.SelectedItems)
            {
                var key = row.Tag as string;
                if (string.IsNullOrEmpty(key)) continue;
                _session.RemoveTargetPipe(key);
            }
            RefreshTargetCount();
            InvalidatePlan("已移除选中的目标管。");
        }

        private void ClearTargets_Click(object sender, EventArgs e)
        {
            _session.ClearTargets();
            RefreshTargetCount();
            InvalidatePlan("已清空目标管。");
        }

        // ------------------------------------------------------------------
        // 预览
        // ------------------------------------------------------------------

        private void RefreshPreview_Click(object sender, EventArgs e)
        {
            if (!EnsurePlan()) return;
            try
            {
                RefreshPreviewGraphics();
                SetStatus("预览已刷新。核对无误后点【应用】。");
            }
            catch (Exception ex)
            {
                SetStatus("绘制预览失败：" + ex.Message);
            }
        }

        private void ClearPreview_Click(object sender, EventArgs e)
        {
            try
            {
                _session.Preview.Clear();
                SetStatus("预览已清除。");
            }
            catch (Exception ex)
            {
                SetStatus("清除预览失败：" + ex.Message);
            }
        }

        private void RefreshPreviewGraphics()
        {
            _session.Preview.Rebuild(_session.Plan, _session.Units,
                _showCurrentCheck.Checked, _showTargetCheck.Checked);
        }

        private bool EnsurePlan()
        {
            if (_session.ReferencePipe == null)
            {
                SetStatus("请先选择基准管。");
                return false;
            }
            if (_session.TargetPipes.Count == 0)
            {
                SetStatus("请先选择至少一根目标管。");
                return false;
            }

            try
            {
                _session.BuildPlan();
                if (_session.Scope == MoveScope.ZStretch)
                {
                    bool loading = _loadingUi;
                    _loadingUi = true;
                    _zDeltaInput.Value = (decimal)_session.ZMoveDeltaMm;
                    _loadingUi = loading;
                }
                RefreshPlanList();
                return true;
            }
            catch (PipeAlignValidationException ex)
            {
                _session.Plan = null;
                RefreshPlanList();
                SetStatus(ex.Message);
                return false;
            }
            catch (Exception ex)
            {
                _session.Plan = null;
                RefreshPlanList();
                SetStatus("计算对齐计划失败：" + ex.Message);
                return false;
            }
        }

        // ------------------------------------------------------------------
        // 应用 / 重置 / 关闭
        // ------------------------------------------------------------------

        private void Apply_Click(object sender, EventArgs e)
        {
            if (_applying) return;
            StopPicking();

            // 指南 §27 第 1、2 步：再次读取所有 Pipe 对象并检查有效性。
            var notes = new List<string>();
            _session.ReloadPipes(notes);
            foreach (string note in notes) _session.Log.Warn(note);
            RefreshReferenceLabel();
            RefreshTargetCount();

            if (!EnsurePlan()) return;

            AlignmentPlan plan = _session.Plan;
            if (plan.ReadyCount == 0)
            {
                SetStatus("没有可移动的目标管（全部跳过或已对齐），未做任何修改。");
                return;
            }

            _applying = true;
            _autoPreviewPending = false;
            _applyButton.Enabled = false;

            try
            {
                AlignmentResult result = _session.Apply();

                // 对齐后原来的预览已经过期，清掉。
                try { _session.Preview.Clear(); }
                catch { }
                _session.Plan = null;
                if (result.MovedCount > 0 && string.IsNullOrEmpty(result.FailureMessage) && _session.Scope == MoveScope.ZStretch)
                {
                    _session.ZMoveDeltaMm = 0.0;
                    _zDeltaInput.Value = 0M;
                }
                _session.ReloadPipes(new List<string>());
                EnsurePlan();

                string summary = BuildResultSummary(result);
                SetStatus(summary.Replace("\r\n", " ").Replace("\n", " "));
                if (result.FailedCount > 0 || !string.IsNullOrEmpty(result.FailureMessage))
                    MessageBox.Show(this, summary, "执行失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            catch (Exception ex)
            {
                SetStatus("执行失败：" + ex.Message);
                MessageBox.Show(this, "执行失败：" + ex.Message, "管道标高对齐",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                _applying = false;
                _applyButton.Enabled = true;
            }
        }

        /// <summary>
        /// 执行结果的中文摘要。
        /// <para>
        /// **必须把失败 / 跳过的原因一起显示出来**：只报"失败 1 根"会逼着用户去翻日志才知道
        /// 为什么，这一点在真机实测里立刻就被验证了（第一次实测就是只看到数量、看不到原因）。
        /// 完整清单仍在窗口表格与调试日志里，这里最多各列 <see cref="MaxReasonsInSummary"/> 条。
        /// </para>
        /// </summary>
        private static string BuildResultSummary(AlignmentResult result)
        {
            var builder = new System.Text.StringBuilder();
            builder.AppendFormat(CultureInfo.InvariantCulture,
                "对齐完成：移动 {0} 根，已对齐 {1} 根，跳过 {2} 根，失败 {3} 根。",
                result.MovedCount, result.AlreadyAlignedCount, result.SkippedCount, result.FailedCount);

            AppendReasons(builder, result, MoveOutcome.Failed, "失败原因");
            AppendReasons(builder, result, MoveOutcome.Skipped, "跳过原因");
            if (!string.IsNullOrEmpty(result.FailureMessage))
                builder.AppendLine().Append("操作失败：").Append(result.FailureMessage);

            if (result.StoppedEarly)
                builder.AppendLine().Append("⚠️ 出现失败，已停止后续修改（未处理的管道也在下面的清单里）。");
            if (result.RolledBack)
                builder.AppendLine().Append("已回退到操作前的事务位置。");
            if (result.MovedCount > 0)
                builder.AppendLine().Append("可用一次 Undo 撤消整批操作。");
            if (result.FailedCount > 0 || result.SkippedCount > 0)
            {
                builder.AppendLine().AppendFormat(CultureInfo.InvariantCulture,
                    "完整清单见窗口表格；详细过程见 %LOCALAPPDATA%\\PipeAlign\\PipeAlign_debug_log.txt");
            }
            return builder.ToString();
        }

        private const int MaxReasonsInSummary = 4;

        private static void AppendReasons(System.Text.StringBuilder builder, AlignmentResult result,
            MoveOutcome outcome, string title)
        {
            var lines = new List<string>();
            foreach (AlignmentItemResult item in result.Items)
            {
                if (item.Outcome != outcome) continue;
                string message = string.IsNullOrEmpty(item.Message) ? item.Describe() : item.Message;
                lines.Add("· " + item.PipeName + "：" + message);
            }
            if (lines.Count == 0) return;

            builder.AppendLine().AppendLine().Append(title + "：");
            int shown = Math.Min(lines.Count, MaxReasonsInSummary);
            for (int index = 0; index < shown; index++)
                builder.AppendLine(lines[index]);
            if (lines.Count > shown)
                builder.AppendFormat(CultureInfo.InvariantCulture, "…另有 {0} 条，见窗口表格。",
                    lines.Count - shown).AppendLine();
        }

        private void Reset_Click(object sender, EventArgs e)
        {
            StopPicking();
            _session.Reset();
            RefreshReferenceLabel();
            RefreshTargetCount();
            RefreshPlanList();
            SetStatus("已重置：基准管、目标管与预览都已清空。");
        }

        private void SaveOptions_Click(object sender, EventArgs e)
        {
            try
            {
                // 把界面上当前的移动范围一并存成默认值，下次打开就是这次的选择。
                _session.Options.DefaultMoveScope = _session.Scope;
                string path = _session.SaveOptions();
                SetStatus("运行参数已写入：" + path);
            }
            catch (Exception ex)
            {
                SetStatus("写入配置失败：" + ex.Message);
            }
        }

        private void Close_Click(object sender, EventArgs e)
        {
            CloseDialog();
        }

        private void StopPicking()
        {
            try { PipePickTool.End(); }
            catch { }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // 用户在 WinForms 自己的标题栏 / 系统菜单上点了关闭：框架还开着，
            // 不一起关就会剩一个空白框架（实测就是这样）。
            if (!_closing)
            {
                CleanUp();
                try { if (_windowContent != null) _windowContent.Close(); }
                catch { }
            }
            _closing = true;
            base.OnFormClosing(e);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _closing = true;
                try
                {
                    if (_windowContent != null)
                    {
                        _windowContent.ContentCloseQuery -= OnContentCloseQuery;
                        // WindowContent 不是 IDisposable，用 Close() 收掉框架。
                        _windowContent.Close();
                    }
                }
                catch { }
                try { if (_pickTimer != null) { _pickTimer.Stop(); _pickTimer.Dispose(); } }
                catch { }
                try { PipePickTool.End(); }
                catch { }
                _detailTips.Dispose();
                _numberFont.Dispose();
                _planList.Dispose();
                _zDeltaInput.Dispose();
                _closeButton.Dispose();
                if (ReferenceEquals(_instance, this)) _instance = null;
            }
            base.Dispose(disposing);
        }
    }
}
