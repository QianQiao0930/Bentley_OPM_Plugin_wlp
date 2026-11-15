using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱拉索三维建模页：参数输入 → 点取筒身底部圆心 → 预览 → 确认生成。
    /// 生命周期、预览所有权、参数记忆与耗时统计沿用工程绘图类页面的既有约定。
    /// </summary>
    internal partial class ChimneyCablePage : UserControl, IWorkspacePage
    {
        private readonly EngineeringPreviewSession preview = new EngineeringPreviewSession("烟囱拉索预览");
        private readonly string[] fields = { "HeightText", "DiameterText", "AngleText", "HeadingText" };

        private DPoint3d? origin;
        private bool ready;
        private bool active;
        private int revision;
        private string elapsed;

        internal ChimneyCablePage()
        {
            InitializeComponent();
            PageLastInput.Restore(this, PageId, fields);
            ready = true;
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

        private ChimneyCableParameters Parameters()
        {
            return new ChimneyCableParameters
            {
                HeightMeters = Number(HeightText, "排气筒高度 H"),
                DiameterMm = Number(DiameterText, "筒身直径 D"),
                CableAngleDegrees = Number(AngleText, "拉索角度"),
                HeadingDegrees = Number(HeadingText, "绕竖轴旋转角")
            };
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
                    return;
                }

                EngineeringPlan plan = ChimneyCableCalculator.Calculate(parameters);
                ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
                SpecificationText.Text = ChimneyCableCalculator.Describe(plan, parameters);
                ShowSummary(spec);
            }
            catch (Exception exception)
            {
                SpecificationText.Text = exception.Message;
                ShowSummary(null);
            }
        }

        /// <summary>只读摘要：拉索外圆半径、拉索根数、是否需要中间层；非法输入显示短横线。</summary>
        private void ShowSummary(ChimneyCableSpec spec)
        {
            if (spec == null)
            {
                OuterRadiusText.Text = "—";
                CableCountText.Text = "—";
                ExtraLayerText.Text = "—";
                return;
            }

            OuterRadiusText.Text = spec.OuterRadiusMm.ToString("0.###", CultureInfo.CurrentCulture) + " mm";
            CableCountText.Text = spec.CableCount + " 根（锚墩 " + spec.AnchorCount + " 个）";
            ExtraLayerText.Text = spec.NeedsExtraCable
                ? "需要：H/(2R) = " + spec.ExtraCableRatio.ToString("0.###", CultureInfo.CurrentCulture) + " > 35"
                : "不需要：H/(2R) = " + spec.ExtraCableRatio.ToString("0.###", CultureInfo.CurrentCulture);
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
