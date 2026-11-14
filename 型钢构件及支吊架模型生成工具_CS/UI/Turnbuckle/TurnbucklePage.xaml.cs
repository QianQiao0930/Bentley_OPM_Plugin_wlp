using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class TurnbucklePage : UserControl, IWorkspacePage
    {
        private readonly EngineeringPreviewSession preview = new EngineeringPreviewSession("花篮螺栓预览");
        private readonly string[] fields = { "SizeCombo", "EndGapText", "ProtrusionText", "HeadingText" };
        private DPoint3d? origin;
        private bool ready;
        private bool active;
        private int revision;
        private string elapsed;

        internal TurnbucklePage()
        {
            InitializeComponent();
            foreach (int size in TurnbuckleCatalog.Sizes)
            {
                SizeCombo.Items.Add("M" + size);
            }

            SizeCombo.SelectedIndex = 3;
            PageLastInput.Restore(this, PageId, fields);
            ready = true;
            UpdateSpecification();
        }

        public string PageId
        {
            get { return "turnbuckle"; }
        }

        public string PageTitle
        {
            get { return "花篮螺栓"; }
        }

        public string PageSubtitle
        {
            get { return "拉杆、花篮螺母、U 形卸扣及销轴装配"; }
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

        private TurnbuckleParameters Parameters()
        {
            return new TurnbuckleParameters
            {
                Size = TurnbuckleCatalog.Sizes[Math.Max(0, SizeCombo.SelectedIndex)],
                EndGapMm = Number(EndGapText, "端部间隙"),
                StudProtrusionMm = Number(ProtrusionText, "伸入叉口长度"),
                HeadingDegrees = Number(HeadingText, "旋转角")
            };
        }

        private EngineeringPlan Plan()
        {
            return TurnbuckleCalculator.Calculate(Parameters());
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
                TurnbuckleParameters parameters = Parameters();
                string error;
                if (!TurnbuckleCatalog.Validate(parameters, out error))
                {
                    SpecificationText.Text = error;
                    return;
                }

                EngineeringPlan plan = TurnbuckleCalculator.Calculate(parameters);
                TurnbuckleSpec spec = TurnbuckleCatalog.Resolve(parameters);
                SpecificationText.Text = TurnbuckleCalculator.Describe(plan, spec);
            }
            catch (Exception exception)
            {
                SpecificationText.Text = exception.Message;
            }
        }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Plan();
                EngineeringPlacementTool.Begin("左键点取花篮螺栓中心。");
                Status("请点取花篮螺栓中心。", false);
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
                Status("请先点取花篮螺栓中心。", true);
                return;
            }

            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成花篮螺栓预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                EngineeringPlan plan = Plan();
                preview.Show(EngineeringSolidFactory.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.PartCount + " 个实体；用时 " + elapsed + "。";
                Status("花篮螺栓预览已更新。", false);
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
                PreviewText.Text = "尚未点取花篮螺栓中心。";
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
                PreviewText.Text = "已确认生成一个花篮螺栓总成；用时 " + elapsed + "。";
                Status("花篮螺栓已生成。", false);
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
