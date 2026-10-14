using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class MagneticGaugePage : UserControl, IWorkspacePage
    {
        private readonly MagneticGaugePreviewSession preview = new MagneticGaugePreviewSession();
        private readonly string[] fields = { "SpacingText", "HeadingText" };
        private DPoint3d? origin;
        private bool ready, active;
        private int revision;
        private string elapsed;
        public string PageId { get { return "magnetic-level-gauge"; } }
        public string PageTitle { get { return "磁翻板液位计"; } }
        public string PageSubtitle { get { return "接口中心距、红白翻片及仪表外观模型"; } }
        public FrameworkElement View { get { return this; } }

        internal MagneticGaugePage()
        {
            InitializeComponent();
            PageLastInput.Restore(this, PageId, fields);
            ready = true; UpdateSpecification();
        }
        public void OnActivated()
        {
            if (active) return;
            active = true; MagneticGaugePlacementTool.Picked += OnPicked; MagneticGaugePlacementTool.Ended += OnEnded;
        }
        public void OnDeactivated()
        {
            active = false; revision++;
            MagneticGaugePlacementTool.Picked -= OnPicked; MagneticGaugePlacementTool.Ended -= OnEnded;
            PageLastInput.Save(this, PageId, fields);
            MagneticGaugePlacementTool.End(); ClearPreview();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }
        private static double Number(TextBox input, string name)
        {
            double value;
            if (!double.TryParse(input.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(input.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
                throw new InvalidOperationException(name + "必须是数字。");
            return value;
        }
        private MagneticGaugePlan Plan()
        {
            return MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters {
                ConnectionSpacingMm = Number(SpacingText, "上下接口中心距L1"),
                HeadingDegrees = Number(HeadingText, "旋转角") });
        }
        private void Parameter_Changed(object sender, RoutedEventArgs e)
        {
            if (!ready) return;
            preview.Invalidate(); ConfirmButton.IsEnabled = false;
            UpdateSpecification(); PageLastInput.Save(this, PageId, fields);
            if (origin.HasValue || preview.HasPreview)
            {
                PreviewUpdateHint.Set(UpdateButton, true); PreviewText.Text = "参数已变化，请更新预览。";
            }
        }
        private void UpdateSpecification()
        {
            try
            {
                var plan = Plan();
                SpecificationText.Text = string.Format(CultureInfo.CurrentCulture,
                    "上下接口中心距 {0:0.#} mm。\n翻片 {1} 片，节距 {2:0.##} mm；刻度 {3} 条；共 {4} 个构件。",
                    plan.Parameters.ConnectionSpacingMm, plan.FlipCount, plan.FlipPitchMm, plan.TickCount, plan.Parts.Length);
            }
            catch (Exception ex) { SpecificationText.Text = ex.Message; }
        }
        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try { Plan(); MagneticGaugePlacementTool.Begin(); Status("请点取下接口筒体轴心。", false); }
            catch (Exception ex) { Status(ex.Message, true); }
        }
        private void OnPicked(DPoint3d point)
        {
            if (!active) return;
            int token = ++revision;
            preview.Invalidate(); ConfirmButton.IsEnabled = false;
            Dispatcher.BeginInvoke(new Action(delegate {
                if (!active || token != revision) return;
                origin = point; Regenerate();
            }), DispatcherPriority.Background);
        }
        private void Regenerate()
        {
            if (!origin.HasValue) { Status("请先点取下接口筒体轴心。", true); return; }
            preview.Invalidate(); ConfirmButton.IsEnabled = false; PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成磁翻板液位计预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                var plan = Plan();
                preview.Show(MagneticGaugeBuilder.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true; PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.Parts.Length + " 个构件；用时 " + elapsed + "。";
                Status("磁翻板液位计预览已更新。", false);
            }
            catch (Exception ex) { PreviewText.Text = ex.Message; Status("预览失败：" + ex.Message, true); }
        }
        private void OnEnded() { revision++; ClearPreview(); }
        private void ClearPreview()
        {
            preview.Invalidate(); ConfirmButton.IsEnabled = false;
            try
            {
                preview.Cancel(); origin = null; PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "尚未点取下接口筒体轴心。";
            }
            catch (Exception ex) { Status("预览清理失败：" + ex.Message, true); }
        }
        private void End_Click(object sender, RoutedEventArgs e)
        {
            bool wasActive = MagneticGaugePlacementTool.IsActive;
            MagneticGaugePlacementTool.End();
            if (!wasActive) { revision++; ClearPreview(); }
        }
        private void Update_Click(object sender, RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender, RoutedEventArgs e) { revision++; ClearPreview(); }
        private void Confirm_Click(object sender, RoutedEventArgs e)
        {
            if (!ConfirmButton.IsEnabled) return;
            try
            {
                preview.Confirm(); revision++; origin = null; ConfirmButton.IsEnabled = false;
                PreviewUpdateHint.Set(UpdateButton, false); PageLastInput.Save(this, PageId, fields);
                PreviewText.Text = "已确认生成一个磁翻板液位计块；用时 " + elapsed + "。";
                Status("磁翻板液位计已生成。", false);
            }
            catch (Exception ex) { ConfirmButton.IsEnabled = false; Status(ex.Message, true); }
        }
        private static void Status(string text, bool error)
        { if (MainWindow.Current != null) MainWindow.Current.SetStatus(text, error); }
    }
}
