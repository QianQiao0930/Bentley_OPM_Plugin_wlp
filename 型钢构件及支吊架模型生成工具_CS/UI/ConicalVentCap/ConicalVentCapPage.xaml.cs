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
    /// 锥形风帽页面（14K117-3 构造图）：点取底部接口中心后预览整组三维实体，
    /// 生命周期与花篮螺栓页一致，预览与定位共用 EngineeringPreviewSession / EngineeringPlacementTool。
    /// </summary>
    internal partial class ConicalVentCapPage : UserControl, IWorkspacePage
    {
        private readonly EngineeringPreviewSession preview = new EngineeringPreviewSession("锥形风帽预览");
        private readonly string[] fields = { "DiameterText", "ThicknessText", "SupportCombo", "HeadingText" };
        private DPoint3d? origin;
        private bool ready;
        private bool active;
        private int revision;
        private string elapsed;

        internal ConicalVentCapPage()
        {
            InitializeComponent();
            double[] presets = ConicalVentCapCatalog.PresetDiameters;
            foreach (double diameter in presets)
            {
                DiameterText.Items.Add(diameter.ToString("0.###", CultureInfo.InvariantCulture));
            }

            int selected = Array.IndexOf(presets, 1250.0);
            DiameterText.SelectedIndex = selected >= 0 ? selected : 0;
            for (int count = ConicalVentCapCatalog.MinSupportCount;
                 count <= ConicalVentCapCatalog.MaxSupportCount; count++)
            {
                SupportCombo.Items.Add(count.ToString(CultureInfo.InvariantCulture));
            }

            SupportCombo.SelectedIndex = 4 - ConicalVentCapCatalog.MinSupportCount;
            PageLastInput.Restore(this, PageId, fields);
            ready = true;
            UpdateSpecification();
        }

        public string PageId
        {
            get { return "conical-vent-cap"; }
        }

        public string PageTitle
        {
            get { return "锥形风帽"; }
        }

        public string PageSubtitle
        {
            get { return "14K117-3 锥形风帽：连接短管、内外锥、雨帽、法兰与支撑"; }
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

        /// <summary>允许输入 D1250、Φ1250、Ø1250 等写法，统一取数字部分。</summary>
        private static string NormalizeDiameter(string text)
        {
            string value = (text ?? string.Empty).Trim();
            while (value.Length > 0)
            {
                char first = char.ToUpperInvariant(value[0]);
                if (first == 'D' || first == 'Φ' || first == 'Ø' || char.IsWhiteSpace(value[0]))
                {
                    value = value.Substring(1).Trim();
                    continue;
                }

                break;
            }

            return value;
        }

        private double Diameter()
        {
            string text = NormalizeDiameter(DiameterText.Text);
            double value;
            if (!double.TryParse(text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
            {
                throw new InvalidOperationException("连接短管外径 D 必须是数字。");
            }

            return value;
        }

        private int SupportCount()
        {
            if (SupportCombo.SelectedIndex < 0)
            {
                throw new InvalidOperationException("请选择支撑组数。");
            }

            return ConicalVentCapCatalog.MinSupportCount + SupportCombo.SelectedIndex;
        }

        private ConicalVentCapParameters Parameters()
        {
            return new ConicalVentCapParameters
            {
                DiameterMm = Diameter(),
                WallThicknessMm = Number(ThicknessText, "板厚"),
                SupportCount = SupportCount(),
                HeadingDegrees = Number(HeadingText, "旋转角")
            };
        }

        private EngineeringPlan Plan()
        {
            return ConicalVentCapCalculator.Calculate(Parameters());
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
                ConicalVentCapParameters parameters = Parameters();
                string error;
                if (!ConicalVentCapCatalog.Validate(parameters, out error))
                {
                    SpecificationText.Text = error;
                    return;
                }

                EngineeringPlan plan = ConicalVentCapCalculator.Calculate(parameters);
                ConicalVentCapDimensions dimensions = ConicalVentCapCatalog.Dimensions(parameters.DiameterMm);
                SpecificationText.Text = ConicalVentCapCalculator.Describe(plan, dimensions, parameters);
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
                EngineeringPlacementTool.Begin("左键点取风帽底部接口平面中心。");
                Status("请点取风帽底部接口中心。", false);
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
                Status("请先点取风帽底部接口中心。", true);
                return;
            }

            preview.Invalidate();
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            Status("正在生成锥形风帽预览…", false);
            var watch = Stopwatch.StartNew();
            try
            {
                EngineeringPlan plan = Plan();
                preview.Show(EngineeringSolidFactory.Build(plan, origin.Value));
                elapsed = WriteDuration.Format(watch.Elapsed.TotalMilliseconds);
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "预览已生成，共 " + plan.PartCount + " 个实体；用时 " + elapsed + "。";
                Status("锥形风帽预览已更新。", false);
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
                PreviewText.Text = "尚未点取风帽底部接口中心。";
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
                PreviewText.Text = "已确认生成一个锥形风帽；用时 " + elapsed + "。";
                Status("锥形风帽已生成。", false);
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
