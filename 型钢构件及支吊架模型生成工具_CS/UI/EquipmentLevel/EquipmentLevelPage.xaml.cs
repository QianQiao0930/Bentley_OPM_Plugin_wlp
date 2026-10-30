using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class EquipmentLevelPage : UserControl, IWorkspacePage, IWorkspaceBusyPage
    {
        private EquipmentLevelDocument document;
        private EquipmentLevelSelection selection;
        private bool active, loading = true, busy, rendering;
        private readonly Stopwatch watch = new Stopwatch();
        private readonly DispatcherTimer timer;
        public string PageId { get { return "equipment-level"; } }
        public string PageTitle { get { return "设备图层与颜色"; } }
        public string PageSubtitle { get { return "统一设备内部图形的图层和颜色"; } }
        public FrameworkElement View { get { return this; } }
        public bool IsBusy { get { return busy; } }

        internal EquipmentLevelPage()
        {
            InitializeComponent();
            timer = new DispatcherTimer(DispatcherPriority.Render) { Interval = TimeSpan.FromMilliseconds(250) };
            timer.Tick += Timer_Tick;
            loading = false;
        }

        public void OnActivated()
        {
            if (active) return;
            active = true;
            TransactionManager.OnUndoRedoFinished += UndoFinished;
            RefreshDocument(false);
            ReadSelection();
            timer.Start();
        }
        public void OnDeactivated()
        {
            if (busy) throw new InvalidOperationException("正在修改设备，请等待处理完成后离开。");
            if (!active) return;
            active = false; timer.Stop();
            TransactionManager.OnUndoRedoFinished -= UndoFinished;
            selection = null;
            ChildCountText.Text = "子构件：未读取";
            UpdateEnabled();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }

        private void Timer_Tick(object sender, EventArgs e)
        {
            if (!active) return;
            if (busy) { ShowElapsed(); return; }
            try
            {
                var model = EquipmentLevelReader.ActiveModel();
                if (document == null || !ReferenceEquals(document.Model, model)) RefreshDocument(false);
            }
            catch
            {
                if (document != null)
                {
                    document = null; selection = null; LevelCombo.ItemsSource = null;
                    DocumentText.Text = "没有活动文档"; SelectionSummary.Text = "文档已关闭，请重新读取。";
                    ChildCountText.Text = "子构件：未读取"; ResultText.Text = SelectionSummary.Text;
                    UpdateEnabled();
                }
            }
        }
        private void UndoFinished(object sender, EventArgs e)
        {
            if (!active || busy) return;
            selection = null;
            SelectionSummary.Text = "已撤销或重做，请重新读取设备。";
            ChildCountText.Text = "子构件：未读取"; ResultText.Text = SelectionSummary.Text;
            UpdateEnabled();
        }

        private void RefreshDocument(bool retainTarget)
        {
            if (busy) return;
            uint? previous = retainTarget && LevelCombo.SelectedItem is EquipmentLevelChoice
                ? (uint?)((EquipmentLevelChoice)LevelCombo.SelectedItem).Id : null;
            try
            {
                var fresh = EquipmentLevelUiReader.ReadDocument();
                bool sameModel = document != null && ReferenceEquals(document.Model, fresh.Model);
                if (!sameModel)
                {
                    previous = null; selection = null; SelectionSummary.Text = "请在模型中选择设备，再读取选择。";
                    ChildCountText.Text = "子构件：未读取"; ResultText.Text = SelectionSummary.Text;
                }
                document = fresh;
                loading = true;
                LevelCombo.ItemsSource = document.Levels;
                LevelCombo.SelectedItem = document.Levels.FirstOrDefault(l => l.IsWritable && l.Id == (previous ?? document.ActiveLevelId));
                DocumentText.Text = Path.GetFileName(document.FileName) + " / " + document.ModelName +
                    " · 可用图层 " + document.Levels.Count(l => l.IsWritable) + " 个";
            }
            catch (Exception ex)
            {
                document = null; selection = null; LevelCombo.ItemsSource = null;
                SelectionSummary.Text = "图层读取失败，请刷新文档。";
                ChildCountText.Text = "子构件：未读取"; ResultText.Text = SelectionSummary.Text;
                DocumentText.Text = "图层读取失败"; Status(ex.Message, true);
            }
            finally { loading = false; UpdateParameters(); }
        }
        private void RefreshLevels_Click(object sender, RoutedEventArgs e) { RefreshDocument(true); }
        private void ReadSelection_Click(object sender, RoutedEventArgs e) { ReadSelection(); }
        private void ReadSelection()
        {
            if (!active || busy) return;
            try
            {
                if (document == null || !ReferenceEquals(document.Model, EquipmentLevelReader.ActiveModel())) RefreshDocument(false);
                busy = true; selection = null; watch.Restart(); ShowElapsed(); UpdateEnabled();
                SelectionSummary.Text = "正在读取选中设备…"; ChildCountText.Text = "子构件：统计中…";
                ResultText.Text = "正在读取设备及其内部子构件…";
                StageText.Text = "读取设备与子构件"; WorkProgress.IsIndeterminate = true;
                RenderProgress();
                EquipmentLevelUiReader.ValidateDocument(document);
                var freshSelection = EquipmentLevelUiReader.ReadSelection();
                EquipmentLevelUiReader.ValidateDocument(document);
                if (!ReferenceEquals(freshSelection.Model, document.Model))
                    throw new InvalidOperationException("活动文档或模型已切换，请重新读取设备。");
                selection = freshSelection;
                SelectionSummary.Text = "已读取 " + selection.Equipment.Count + " 台设备" +
                    (selection.Rejected.Count > 0 ? " · 跳过 " + selection.Rejected.Count + " 个非设备元素" : "");
                ChildCountText.Text = "子构件：" + selection.ChildElementCount + " 个";
                ResultText.Text = string.Join(Environment.NewLine, selection.Equipment.Select(e => e.Name + "  [" + e.ElementId +
                    "] · 子构件 " + selection.EquipmentChildCounts[e.ElementId] + " 个")
                    .Concat(selection.Rejected.Select(e => "跳过 " + e.ElementId + "：" + e.Reason)));
                if (selection.Equipment.Count == 0) ResultText.Text = string.IsNullOrEmpty(ResultText.Text)
                    ? "先在模型中选择一台或多台设备，再点击“读取选中设备”。" : ResultText.Text;
                StageText.Text = "等待处理"; WorkProgress.Value = 0;
                ProgressDetailText.Text = selection.Equipment.Count > 0 ? "选择目标图层与颜色，点击应用修改。" : "只处理设备实际包含的图形，支持撤销。";
                watch.Reset(); ShowElapsed();
            }
            catch (Exception ex)
            {
                selection = null; SelectionSummary.Text = "读取失败，请重新选择设备。";
                ChildCountText.Text = "子构件：统计失败"; StageText.Text = "读取未完成"; WorkProgress.Value = 0;
                ProgressDetailText.Text = ex.Message; ResultText.Text = ex.Message; Status("读取设备失败：" + ex.Message, true);
            }
            finally { watch.Stop(); ShowElapsed(); busy = false; WorkProgress.IsIndeterminate = false; UpdateEnabled(); }
        }

        private void Parameters_Changed(object sender, SelectionChangedEventArgs e) { if (!loading) UpdateParameters(); }
        private void ColorText_Changed(object sender, TextChangedEventArgs e) { if (!loading) UpdateParameters(); }
        private void UpdateParameters()
        {
            var level = LevelCombo.SelectedItem as EquipmentLevelChoice;
            LevelInfoText.Text = level == null ? "请选择一个可写图层。" : "目标层色：" + level.ColorHex + " · " + level.Availability;
            CustomColorPanel.Visibility = ColorModeCombo.SelectedIndex == 1 ? Visibility.Visible : Visibility.Collapsed;
            ColorHintText.Text = ColorModeCombo.SelectedIndex == 1 ? "指定颜色只应用于设备内部图元，不改变图层的颜色设置。" :
                ColorModeCombo.SelectedIndex == 2 ? "仅统一图层，保留各图元原有颜色。" : "内部图元颜色设为随层，以后可通过目标图层统一调整。";
            try
            {
                uint rgb = EquipmentAppearanceOptions.ParseRgb(ColorModeCombo.SelectedIndex == 1 ? ColorHexText.Text : level == null ? "#7FA37C" : level.ColorHex);
                ColorSwatch.Background = new SolidColorBrush(Color.FromRgb((byte)(rgb >> 16), (byte)(rgb >> 8), (byte)rgb));
            }
            catch { ColorSwatch.Background = Brushes.Transparent; }
            UpdateEnabled();
        }
        private void ChooseColor_Click(object sender, RoutedEventArgs e)
        {
            if (busy) return;
            uint rgb;
            try { rgb = EquipmentAppearanceOptions.ParseRgb(ColorHexText.Text); }
            catch { rgb = 0x7FA37C; }
            using (var dialog = new System.Windows.Forms.ColorDialog { FullOpen = true,
                Color = System.Drawing.Color.FromArgb((int)((rgb >> 16) & 255), (int)((rgb >> 8) & 255), (int)(rgb & 255)) })
            {
                if (dialog.ShowDialog(MainWindow.Current) == System.Windows.Forms.DialogResult.OK)
                    ColorHexText.Text = "#" + dialog.Color.R.ToString("X2") + dialog.Color.G.ToString("X2") + dialog.Color.B.ToString("X2");
            }
        }

        private void Apply_Click(object sender, RoutedEventArgs e)
        {
            if (!active || busy) return;
            busy = true; watch.Restart(); UpdateEnabled();
            try
            {
                StageText.Text = "检查设备与目标图层"; WorkProgress.IsIndeterminate = true;
                ProgressDetailText.Text = "正在检查活动文档与已选设备…";
                ShowElapsed(); RenderProgress();
                if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
                EquipmentLevelUiReader.Validate(document, selection);
                var level = LevelCombo.SelectedItem as EquipmentLevelChoice;
                if (level == null || !level.IsWritable) throw new InvalidOperationException("请选择可写的目标图层。");
                var fresh = EquipmentLevelUiReader.ReadDocument();
                if (!fresh.Levels.Any(l => l.IsWritable && l.Id == level.Id && l.Name == level.Name))
                    throw new InvalidOperationException("目标图层已改变或不可写，请刷新图层。");
                var mode = ColorModeCombo.SelectedIndex == 1 ? EquipmentColorMode.CustomRgb :
                    ColorModeCombo.SelectedIndex == 2 ? EquipmentColorMode.KeepOriginal : EquipmentColorMode.ByLevel;
                var options = new EquipmentAppearanceOptions { TargetLevelId = level.Id, TargetLevelName = level.Name,
                    ColorMode = mode, Rgb = mode == EquipmentColorMode.CustomRgb ? EquipmentAppearanceOptions.ParseRgb(ColorHexText.Text) : 0 };
                EquipmentLevelUiReader.ValidateDocument(document);
                var report = EquipmentLevelApplier.Apply(document.Model, selection.Equipment.Select(item => item.ElementId).ToList(), options,
                    OnProgress, delegate { EquipmentLevelUiReader.ValidateDocument(document); });
                watch.Stop(); WorkProgress.IsIndeterminate = false;
                StageText.Text = report.Succeeded ? "处理完成" : "处理未完成";
                WorkProgress.Value = report.Succeeded ? 100 : 0;
                ShowElapsed();
                ProgressDetailText.Text = report.Succeeded ? "修改 " + report.ChangedElementCount + " 个 · 校验 " + report.VerifiedElementCount + " 个图形" : report.Summary;
                if (report.Succeeded) ChildCountText.Text = "子构件：" + report.VerifiedElementCount + " 个";
                ResultText.Text = report.Summary + Environment.NewLine + string.Join(Environment.NewLine, report.Details.Concat(report.Problems));
                Status(report.Summary + " 用时 " + watch.Elapsed.TotalSeconds.ToString("0.0") + " s。", !report.Succeeded);
            }
            catch (Exception ex)
            {
                StageText.Text = "处理未完成"; WorkProgress.Value = 0;
                ProgressDetailText.Text = ex.Message; ResultText.Text = ex.Message;
                Status(ex.Message, true);
            }
            finally { watch.Stop(); ShowElapsed(); busy = false; WorkProgress.IsIndeterminate = false; UpdateEnabled(); }
        }

        private void OnProgress(EquipmentLevelProgress progress)
        {
            if (!busy) return;
            StageText.Text = progress.Stage;
            WorkProgress.IsIndeterminate = progress.Total <= 0;
            if (progress.Total > 0) WorkProgress.Value = progress.Completed * 100.0 / progress.Total;
            ProgressDetailText.Text = (progress.Total > 0 ? progress.Completed + " / " + progress.Total + "  " : "") + progress.Detail;
            ShowElapsed();
            Status(progress.Stage + " · " + ProgressDetailText.Text + " · 用时 " + watch.Elapsed.TotalSeconds.ToString("0.0") + " s", false);
            RenderProgress();
        }
        private void RenderProgress()
        {
            if (rendering) return;
            rendering = true;
            try
            {
                UpdateLayout();
                // 只请求 WPF 的渲染优先级刷新；不使用 DoEvents，也不把 Bentley API 放到线程池。
                Dispatcher.Invoke(DispatcherPriority.Render, new Action(delegate { }));
            }
            finally { rendering = false; }
        }
        private void ShowElapsed() { ElapsedText.Text = "用时 " + watch.Elapsed.TotalSeconds.ToString("0.0") + " s"; }
        private void UpdateEnabled()
        {
            SettingsPanel.IsEnabled = !busy; ColorPanel.IsEnabled = !busy;
            ReadSelectionButton.IsEnabled = !busy; PageChrome.IsEnabled = !busy;
            ApplyButton.IsEnabled = active && !busy && document != null && selection != null && selection.Equipment.Count > 0 &&
                LevelCombo.SelectedItem is EquipmentLevelChoice && ((EquipmentLevelChoice)LevelCombo.SelectedItem).IsWritable;
        }
        private void Status(string message, bool error)
        {
            if (MainWindow.Current != null) MainWindow.Current.SetStatus(message, error);
        }
    }
}
