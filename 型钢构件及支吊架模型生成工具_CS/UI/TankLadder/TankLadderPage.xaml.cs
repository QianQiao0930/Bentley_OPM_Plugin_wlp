using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class TankLadderPage : UserControl, IWorkspacePage
    {
        private readonly TankLadderPreviewSession preview = new TankLadderPreviewSession();
        private readonly string[] fields = { "HeightText", "WidthText", "SupportSpacingText", "HeadingText", "MergeCheck" };
        private DPoint3d? origin;
        private bool ready, active;
        private int revision;
        private string elapsed;
        public string PageId { get { return "tank-ladder"; } }
        public string PageTitle { get { return "水箱爬梯"; } }
        public string PageSubtitle { get { return "角钢框架、翻弯梯腿及圆钢踏步"; } }
        public FrameworkElement View { get { return this; } }

        internal TankLadderPage()
        {
            InitializeComponent();
            PageLastInput.Restore(this, PageId, fields);
            ready = true; UpdateSpecification();
        }
        public void OnActivated()
        {
            if (active) return;
            active = true; TankLadderPlacementTool.Picked += OnPicked; TankLadderPlacementTool.Ended += OnEnded;
        }
        public void OnDeactivated()
        {
            active = false; revision++;
            TankLadderPlacementTool.Picked -= OnPicked; TankLadderPlacementTool.Ended -= OnEnded;
            PageLastInput.Save(this, PageId, fields);
            TankLadderPlacementTool.End(); ClearPreview();
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
        private TankLadderPlan Plan()
        {
            return TankLadderCalculator.Calculate(new TankLadderParameters {
                TankHeightMm = Number(HeightText, "水箱高度"), WidthMm = Number(WidthText, "顶部净距"),
                ReinforcementSpacingMm = Number(SupportSpacingText, "加强撑间距"),
                HeadingDegrees = Number(HeadingText, "朝向角"), MergeComponents = MergeCheck.IsChecked == true });
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
                    "梯腿净距 {0:0.#} mm；竖向落差 {1:0.#} mm。\n踏步 {2} 根，长 {3:0.#} mm；加强撑每侧 {4} 根；共 {5} 个构件。",
                    plan.LegClearWidthMm, plan.LegVerticalHeightMm, plan.RungCenters.Length,
                    plan.RungLengthMm, plan.ReinforcementOrigins.Length / 2, plan.ComponentCount);
            }
            catch (Exception ex) { SpecificationText.Text = ex.Message; }
        }
        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try { Plan(); TankLadderPlacementTool.Begin(); Status("请点取箱顶基准点。", false); }
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
            if (!origin.HasValue) { Status("请先点取箱顶基准点。", true); return; }
            preview.Invalidate(); ConfirmButton.IsEnabled = false; PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成水箱爬梯预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                var plan = Plan();
                preview.Show(TankLadderBuilder.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true; PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.ComponentCount + " 个构件；用时 " + elapsed + "。";
                Status("水箱爬梯预览已更新。", false);
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
                PreviewText.Text = "尚未点取箱顶基准点。";
            }
            catch (Exception ex) { Status("预览清理失败：" + ex.Message, true); }
        }
        private void End_Click(object sender, RoutedEventArgs e)
        {
            bool wasActive = TankLadderPlacementTool.IsActive;
            TankLadderPlacementTool.End();
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
                PreviewText.Text = "已确认生成一个水箱爬梯块；用时 " + elapsed + "。";
                Status("水箱爬梯已生成。", false);
            }
            catch (Exception ex) { ConfirmButton.IsEnabled = false; Status(ex.Message, true); }
        }
        private static void Status(string text, bool error)
        { if (MainWindow.Current != null) MainWindow.Current.SetStatus(text, error); }
    }
}
