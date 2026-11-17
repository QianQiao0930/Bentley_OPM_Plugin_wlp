using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Microsoft.Win32;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱拉索三维建模页：参数输入 → 点取筒身底部圆心 → 预览 → 确认生成；
    /// 材料用量放在独立页签统计（照灭火器箱“生成 / 统计”的分页做法）。
    /// 生命周期、预览所有权、参数记忆与耗时统计沿用工程绘图类页面的既有约定。
    /// </summary>
    internal partial class ChimneyCablePage : UserControl, IWorkspacePage
    {
        private static readonly string[] fields = {
            "HeightText", "DiameterText", "WallThicknessText", "AngleText", "HeadingText",
            "CableCheck", "BaseCheck", "BoltCountText", "AbovePlateText",
            "FoundationThicknessText", "BoltCircleText", "PlateDiameterText"
        };

        private readonly EngineeringPreviewSession preview = new EngineeringPreviewSession("烟囱拉索预览");

        private DPoint3d? origin;
        private bool ready;
        private bool active;
        private int revision;
        private string elapsed;
        private ChimneyCableMaterials materials;

        internal ChimneyCablePage()
        {
            InitializeComponent();
            PageLastInput.Restore(this, PageId, fields);
            ready = true;
            ApplyToggleState();
            UpdateSpecification();
        }

        public string PageId
        {
            get { return "chimney-cable"; }
        }

        public string PageTitle
        {
            get { return "烟囱拉索"; }
        }

        public string PageSubtitle
        {
            get { return "排气筒筒身、φ16 拉索与两端绳眼装配三维示意"; }
        }

        public FrameworkElement View
        {
            get { return this; }
        }

        public void OnActivated()
        {
            if (active)
            {
                return;
            }

            active = true;
            EngineeringPlacementTool.Picked += OnPicked;
            EngineeringPlacementTool.Ended += OnEnded;
        }

        public void OnDeactivated()
        {
            active = false;
            revision++;
            EngineeringPlacementTool.Picked -= OnPicked;
            EngineeringPlacementTool.Ended -= OnEnded;
            PageLastInput.Save(this, PageId, fields);
            EngineeringPlacementTool.End();
            ClearPreview();
        }

        public void OnWorkspaceClosing()
        {
            OnDeactivated();
        }

        private static double Number(TextBox input, string name)
        {
            double value;
            if (!double.TryParse(input.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(input.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
            {
                throw new InvalidOperationException(name + "必须是数字。");
            }

            return value;
        }

        private static double NumberOrDefault(TextBox input, string name, double fallback)
        {
            try
            {
                return Number(input, name);
            }
            catch (InvalidOperationException)
            {
                return fallback;
            }
        }

        private ChimneyCableParameters Parameters()
        {
            var parameters = new ChimneyCableParameters
            {
                HeightMeters = Number(HeightText, "排气筒高度 H"),
                DiameterMm = Number(DiameterText, "筒身直径 D"),
                WallThicknessMm = Number(WallThicknessText, "筒壁厚度 t"),
                HeadingDegrees = Number(HeadingText, "绕竖轴旋转角"),
                GenerateCables = CableCheck.IsChecked == true,
                GenerateBase = BaseCheck.IsChecked == true
            };

            // 关掉的开关对应的输入框不再参与解析：用户可以留空，不会因此报“必须是数字”。
            parameters.CableAngleDegrees = parameters.GenerateCables
                ? Number(AngleText, "拉索角度")
                : NumberOrDefault(AngleText, "拉索角度", ChimneyCableConstants.DefaultCableAngleDegrees);

            if (parameters.GenerateBase)
            {
                parameters.BoltCount = (int)Math.Round(Number(BoltCountText, "地脚螺栓个数"));
                parameters.AbovePlateMm = Number(AbovePlateText, "螺栓露出长度");
                parameters.FoundationThicknessMm = Number(FoundationThicknessText, "基础厚度");
                parameters.BoltCircleDiameterMm = Number(BoltCircleText, "螺栓圆直径 D2");
                parameters.EmbeddedPlateDiameterMm = Number(PlateDiameterText, "预埋板直径 D3");
            }

            return parameters;
        }

        /// <summary>
        /// 两个开关的状态连带：不生成拉索时拉索角度无意义（禁用输入框）；
        /// 不生成基础时底座的五个输入框一并禁用，避免填了不生效。
        /// </summary>
        private void Toggle_Changed(object sender, RoutedEventArgs e)
        {
            if (!ready)
            {
                return;
            }

            ApplyToggleState();
            Parameter_Changed(sender, e);
        }

        private void ApplyToggleState()
        {
            bool cables = CableCheck.IsChecked == true;
            bool foundation = BaseCheck.IsChecked == true;
            AngleText.IsEnabled = cables;
            BoltCountText.IsEnabled = foundation;
            AbovePlateText.IsEnabled = foundation;
            FoundationThicknessText.IsEnabled = foundation;
            BoltCircleText.IsEnabled = foundation;
            PlateDiameterText.IsEnabled = foundation;
        }

        private EngineeringPlan Plan()
        {
            return ChimneyCableCalculator.Calculate(Parameters());
        }

        private void Parameter_Changed(object sender, RoutedEventArgs e)
        {
            if (!ready)
            {
                return;
            }

            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            UpdateSpecification();
            PageLastInput.Save(this, PageId, fields);
            if (origin.HasValue || preview.HasPreview)
            {
                PreviewUpdateHint.Set(UpdateButton, true);
                PreviewText.Text = "参数已变化，请更新预览。";
            }
        }

        /// <summary>
        /// 绕竖轴旋转角的快捷按钮：按 ±90° 递进并把结果归一到 0～360；
        /// 手动输入保持原样（不做归一），输入框仍然是唯一的取值来源。
        /// </summary>
        private void Rotate_By(double deltaDegrees)
        {
            double current;
            if (!double.TryParse(HeadingText.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out current) &&
                !double.TryParse(HeadingText.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out current))
            {
                current = 0.0;
            }

            double next = (current + deltaDegrees) % 360.0;
            if (next < 0.0)
            {
                next += 360.0;
            }

            if (next == 0.0)
            {
                next = 0.0; // 消除 -0 的显示。
            }

            HeadingText.Text = next.ToString("0.###", CultureInfo.CurrentCulture);
            HeadingText.CaretIndex = HeadingText.Text.Length;
        }

        private void RotatePlus_Click(object sender, RoutedEventArgs e)
        {
            Rotate_By(90.0);
        }

        private void RotateMinus_Click(object sender, RoutedEventArgs e)
        {
            Rotate_By(-90.0);
        }

        private void UpdateSpecification()
        {
            try
            {
                ChimneyCableParameters parameters = Parameters();
                string error;
                if (!ChimneyCableCatalog.Validate(parameters, out error))
                {
                    SpecificationText.Text = error;
                    ShowSummary(null);
                    ShowMaterials(null);
                    return;
                }

                EngineeringPlan plan = ChimneyCableCalculator.Calculate(parameters);
                ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
                SpecificationText.Text = ChimneyCableCalculator.Describe(plan, parameters);
                ShowSummary(spec);
                ShowMaterials(ChimneyCableTakeoff.Of(spec, plan));
            }
            catch (Exception exception)
            {
                SpecificationText.Text = exception.Message;
                ShowSummary(null);
                ShowMaterials(null);
            }
        }

        /// <summary>
        /// 只读摘要：拉索外圆半径、拉索根数、中间层、基础与检修门；非法输入显示短横线。
        /// 自立式时拉索三项显式写“自立式/不生成”，不留上一次的旧值。
        /// </summary>
        private void ShowSummary(ChimneyCableSpec spec)
        {
            if (spec == null)
            {
                OuterRadiusText.Text = "—";
                CableCountText.Text = "—";
                ExtraLayerText.Text = "—";
                BaseText.Text = "—";
                return;
            }

            if (spec.GenerateCables)
            {
                OuterRadiusText.Text = spec.OuterRadiusMm.ToString("0.###", CultureInfo.CurrentCulture) + " mm";
                CableCountText.Text = spec.CableCount + " 根（锚墩 " + spec.AnchorCount + " 个）";
                ExtraLayerText.Text = spec.NeedsExtraCable
                    ? "需要：H/(2R) = " + spec.ExtraCableRatio.ToString("0.###", CultureInfo.CurrentCulture) + " > 35"
                    : "不需要：H/(2R) = " + spec.ExtraCableRatio.ToString("0.###", CultureInfo.CurrentCulture);
            }
            else
            {
                OuterRadiusText.Text = "自立式（不生成拉索）";
                CableCountText.Text = "0 根";
                ExtraLayerText.Text = "—";
            }

            if (spec.GenerateBase)
            {
                BaseText.Text = spec.FoundationSideMm.ToString("0", CultureInfo.CurrentCulture) + "×" +
                    spec.FoundationSideMm.ToString("0", CultureInfo.CurrentCulture) + "×" +
                    spec.FoundationThicknessMm.ToString("0", CultureInfo.CurrentCulture) + "，螺栓 " +
                    spec.BoltCount + " 颗，检修门 +Y";
            }
            else
            {
                BaseText.Text = "不生成基础";
            }
        }

        /// <summary>
        /// 材料统计页签：表格行、合计与导出按钮状态；
        /// null 表示参数非法，表格与导出一并清空（不保留上一次的旧数）。
        /// </summary>
        private void ShowMaterials(ChimneyCableMaterials current)
        {
            materials = current;
            if (current == null)
            {
                MaterialGrid.ItemsSource = null;
                TotalsText.Text = "参数不完整或超出范围，无法统计材料用量。";
                TotalMassText.Text = "—";
                ExcelButton.IsEnabled = JsonButton.IsEnabled = false;
                return;
            }

            MaterialGrid.ItemsSource = current.Rows;
            TotalsText.Text = "钢材 " + current.SteelMassKg.ToString("0.#", CultureInfo.CurrentCulture) +
                " kg · 钢丝绳 " + current.RopeMassKg.ToString("0.#", CultureInfo.CurrentCulture) +
                " kg · 合计 " + current.TotalMassKg.ToString("0.#", CultureInfo.CurrentCulture) + " kg" +
                "　（钢管 " + current.StackMassKg.ToString("0.#", CultureInfo.CurrentCulture) + " kg / " +
                current.StackMassKgPerMeter.ToString("0.#", CultureInfo.CurrentCulture) + " kg·m⁻¹）";
            TotalMassText.Text = current.TotalMassKg.ToString("0.#", CultureInfo.CurrentCulture) + " kg";
            ExcelButton.IsEnabled = JsonButton.IsEnabled = current.Rows.Count > 0;
        }

        /// <summary>切换页签：离开建模页时结束点取；进入材料统计时按当前参数重算。</summary>
        private void Tab_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!active || !ReferenceEquals(e.Source, PageTabs) || PageTabs.SelectedIndex != 1)
            {
                return;
            }

            if (EngineeringPlacementTool.IsActive)
            {
                EngineeringPlacementTool.End();
            }

            UpdateSpecification();
        }

        private void Materials_Click(object sender, RoutedEventArgs e)
        {
            UpdateSpecification();
            Status(materials == null ? "材料统计失败，请检查参数。" : "材料统计已按当前参数刷新。", materials == null);
        }

        private void Excel_Click(object sender, RoutedEventArgs e)
        {
            Export(true);
        }

        private void Json_Click(object sender, RoutedEventArgs e)
        {
            Export(false);
        }

        private void Export(bool excel)
        {
            UpdateSpecification();
            if (materials == null || materials.Rows.Count == 0)
            {
                Status("没有可导出的材料用量。", true);
                return;
            }

            var dialog = new SaveFileDialog
            {
                Title = "导出烟囱拉索材料用量",
                FileName = "烟囱拉索材料用量" + (excel ? ".xlsx" : ".json"),
                Filter = excel ? "Excel 工作簿 (*.xlsx)|*.xlsx" : "JSON 文件 (*.json)|*.json",
                DefaultExt = excel ? ".xlsx" : ".json",
                AddExtension = true,
                OverwritePrompt = true
            };
            if (dialog.ShowDialog() != true)
            {
                return;
            }

            try
            {
                if (excel)
                {
                    WriteExcel(dialog.FileName);
                }
                else
                {
                    WriteJson(dialog.FileName);
                }

                Status("材料用量已导出：" + dialog.FileName, false);
            }
            catch (Exception exception)
            {
                Status("导出失败：" + exception.Message, true);
            }
        }

        /// <summary>Excel：一行说明 + 表头 + 明细 + 合计；不计重的附件重量列留空。</summary>
        private void WriteExcel(string path)
        {
            ChimneyCableParameters parameters = Parameters();
            var sheet = new List<object[]>
            {
                new object[] { "烟囱拉索材料用量" },
                new object[]
                {
                    "H " + parameters.HeightMeters.ToString("0.###", CultureInfo.CurrentCulture) + " m",
                    "D " + parameters.DiameterMm.ToString("0.###", CultureInfo.CurrentCulture) + " mm",
                    "壁厚 " + parameters.WallThicknessMm.ToString("0.###", CultureInfo.CurrentCulture) + " mm",
                    "拉索角度 " + parameters.CableAngleDegrees.ToString("0.###", CultureInfo.CurrentCulture) + "°"
                },
                new object[] { "项目", "规格", "数量", "单位", "单重(kg)", "总重(kg)", "备注" }
            };

            foreach (ChimneyCableMaterialRow row in materials.Rows)
            {
                sheet.Add(new object[]
                {
                    row.Item, row.Specification, row.Quantity, row.Unit,
                    row.Weighed ? (object)row.UnitMassKg : null,
                    row.Weighed ? (object)row.TotalMassKg : null,
                    row.Note
                });
            }

            sheet.Add(new object[] { "合计", "", "", "", "", materials.TotalMassKg,
                "钢材 " + materials.SteelMassKg.ToString("0.###", CultureInfo.CurrentCulture) +
                " kg + 钢丝绳 " + materials.RopeMassKg.ToString("0.###", CultureInfo.CurrentCulture) + " kg" });

            SupportStatisticsExporter.WriteWorkbook(path, new List<KeyValuePair<string, List<object[]>>>
            {
                new KeyValuePair<string, List<object[]>>("材料用量", sheet)
            });
        }

        /// <summary>JSON：参数、派生量与逐行明细，供后续对账。</summary>
        private void WriteJson(string path)
        {
            ChimneyCableParameters parameters = Parameters();
            var payload = new
            {
                page = PageId,
                parameters = new
                {
                    heightMeters = parameters.HeightMeters,
                    diameterMm = parameters.DiameterMm,
                    wallThicknessMm = parameters.WallThicknessMm,
                    cableAngleDegrees = parameters.CableAngleDegrees,
                    headingDegrees = parameters.HeadingDegrees
                },
                totals = new
                {
                    steelMassKg = materials.SteelMassKg,
                    ropeMassKg = materials.RopeMassKg,
                    totalMassKg = materials.TotalMassKg,
                    stackMassKgPerMeter = materials.StackMassKgPerMeter,
                    strandLengthM = materials.StrandLengthM,
                    ropeTotalLengthM = materials.RopeTotalLengthM
                },
                rows = materials.Rows
            };

            File.WriteAllText(path,
                new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(payload),
                new UTF8Encoding(false));
        }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Plan();
                EngineeringPlacementTool.Begin("左键点取筒身底部圆心。");
                Status("请点取筒身底部圆心。", false);
            }
            catch (Exception exception)
            {
                Status(exception.Message, true);
            }
        }

        private void OnPicked(DPoint3d point)
        {
            if (!active)
            {
                return;
            }

            int token = ++revision;
            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || token != revision)
                {
                    return;
                }

                origin = point;
                Regenerate();
            }), DispatcherPriority.Background);
        }

        private void Regenerate()
        {
            if (!origin.HasValue)
            {
                Status("请先点取筒身底部圆心。", true);
                return;
            }

            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成烟囱拉索预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                EngineeringPlan plan = Plan();
                preview.Show(EngineeringSolidFactory.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.PartCount + " 个实体；" +
                    EngineeringTiming.Report() + "（含预览写入共 " + elapsed + "）。";
                Status(EngineeringTiming.Report(), false);
            }
            catch (Exception exception)
            {
                PreviewText.Text = exception.Message;
                Status("预览失败：" + exception.Message, true);
            }
        }

        private void OnEnded()
        {
            revision++;
            ClearPreview();
        }

        private void ClearPreview()
        {
            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            try
            {
                preview.Cancel();
                origin = null;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "尚未点取筒身底部圆心。";
            }
            catch (Exception exception)
            {
                Status("预览清理失败：" + exception.Message, true);
            }
        }

        private void End_Click(object sender, RoutedEventArgs e)
        {
            bool wasActive = EngineeringPlacementTool.IsActive;
            EngineeringPlacementTool.End();
            if (!wasActive)
            {
                revision++;
                ClearPreview();
            }
        }

        private void Update_Click(object sender, RoutedEventArgs e)
        {
            Regenerate();
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            revision++;
            ClearPreview();
        }

        private void Confirm_Click(object sender, RoutedEventArgs e)
        {
            if (!ConfirmButton.IsEnabled)
            {
                return;
            }

            try
            {
                preview.Confirm();
                revision++;
                origin = null;
                ConfirmButton.IsEnabled = false;
                PreviewUpdateHint.Set(UpdateButton, false);
                PageLastInput.Save(this, PageId, fields);
                PreviewText.Text = "已确认生成一个烟囱拉索总成；用时 " + elapsed + "。";
                Status("烟囱拉索已生成。", false);
            }
            catch (Exception exception)
            {
                ConfirmButton.IsEnabled = false;
                Status(exception.Message, true);
            }
        }

        private static void Status(string text, bool error)
        {
            if (MainWindow.Current != null)
            {
                MainWindow.Current.SetStatus(text, error);
            }
        }
    }
}
