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
    /// 烟囱（排气筒）底座三维建模页：参数输入 → 点取预埋板底面中心 → 预览 → 确认生成。
    /// 生命周期、预览所有权与耗时统计沿用工程绘图类页面的既有约定。
    /// </summary>
    internal partial class ChimneyBasePage : UserControl, IWorkspacePage
    {
        private readonly EngineeringPreviewSession preview = new EngineeringPreviewSession("烟囱底座预览");
        private readonly string[] fields =
        {
            "D1Text", "D2Text", "D3Text", "BoltCountText",
            "AbovePlateText", "FoundationThicknessText", "FoundationWidthText", "HeadingText"
        };

        private DPoint3d? origin;
        private bool ready;
        private bool active;
        private int revision;
        private string elapsed;

        internal ChimneyBasePage()
        {
            InitializeComponent();
            PageLastInput.Restore(this, PageId, fields);
            ready = true;
            UpdateSpecification();
        }

        public string PageId
        {
            get { return "chimney-base"; }
        }

        public string PageTitle
        {
            get { return "烟囱底座"; }
        }

        public string PageSubtitle
        {
            get { return "排气筒底座：风管、环形预埋板、加劲肋与 J 形地脚螺栓"; }
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

        private static int Count(TextBox input, string name)
        {
            int value;
            if (!int.TryParse(input.Text, NumberStyles.Integer, CultureInfo.CurrentCulture, out value) &&
                !int.TryParse(input.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
            {
                throw new InvalidOperationException(name + "必须是整数。");
            }

            return value;
        }

        private ChimneyBaseParameters Parameters()
        {
            return new ChimneyBaseParameters
            {
                ExhaustDiameterMm = Number(D1Text, "排气筒直径 D1"),
                BoltCircleDiameterMm = Number(D2Text, "螺栓路径直径 D2"),
                EmbeddedPlateDiameterMm = Number(D3Text, "预埋板直径 D3"),
                BoltCount = Count(BoltCountText, "螺栓个数"),
                AbovePlateMm = Number(AbovePlateText, "螺栓露出长度"),
                FoundationThicknessMm = Number(FoundationThicknessText, "混凝土基础厚度"),
                FoundationWidthMm = Number(FoundationWidthText, "混凝土基础宽度"),
                HeadingDegrees = Number(HeadingText, "绕竖轴旋转角")
            };
        }

        private EngineeringPlan Plan()
        {
            return ChimneyBaseCalculator.Calculate(Parameters());
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
                ChimneyBaseParameters parameters = Parameters();
                string error;
                if (!ChimneyBaseCatalog.Validate(parameters, out error))
                {
                    SpecificationText.Text = error;
                    return;
                }

                EngineeringPlan plan = ChimneyBaseCalculator.Calculate(parameters);
                SpecificationText.Text = ChimneyBaseCalculator.Describe(plan, parameters);
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
                EngineeringPlacementTool.Begin("左键点取烟囱底座预埋板底面中心。");
                Status("请点取烟囱底座预埋板底面中心。", false);
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
                Status("请先点取烟囱底座预埋板底面中心。", true);
                return;
            }

            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成烟囱底座预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                EngineeringPlan plan = Plan();
                preview.Show(EngineeringSolidFactory.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.PartCount + " 个实体；用时 " + elapsed + "。";
                Status("烟囱底座预览已更新。", false);
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
                PreviewText.Text = "尚未点取烟囱底座预埋板底面中心。";
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
                PreviewText.Text = "已确认生成一个烟囱底座；用时 " + elapsed + "。";
                Status("烟囱底座已生成。", false);
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
