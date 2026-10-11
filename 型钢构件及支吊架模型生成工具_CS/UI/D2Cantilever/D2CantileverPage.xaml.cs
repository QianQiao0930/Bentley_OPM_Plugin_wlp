using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class D2CantileverPage : UserControl, IWorkspacePage
    {
        private readonly D2CantileverPreviewSession preview = new D2CantileverPreviewSession();
        private PipeClampSelection line;
        private bool active, ready, locating, dirty;
        public string PageId { get { return "d2-cantilever"; } }
        public string PageTitle { get { return "悬臂架"; } }
        public string PageSubtitle { get { return "D2 端焊 · D3 侧焊 · G11 混凝土生根"; } }
        public FrameworkElement View { get { return this; } }
        internal D2CantileverPage()
        {
            InitializeComponent();
            KindCombo.ItemsSource = new[] { "D2 端焊悬臂架", "D3 侧焊悬臂架", "G11 混凝土上生根的悬臂架" };
            KindCombo.SelectedIndex = 0;
            TypeCombo.ItemsSource = new[] { "类型 1：单侧悬臂", "类型 2：双侧悬臂" };
            TypeCombo.SelectedIndex = 0;
            VariantCombo.ItemsSource = new[] { "A", "B", "C", "D", "E", "F", "G", "H", "J" };
            PlateSubtypeCombo.ItemsSource = new[] { "A", "B", "C", "D" };
            VariantCombo.SelectedIndex = 0; PlateSubtypeCombo.SelectedIndex = 0;
            ready = true; UpdateSection();
            PageLastInput.Restore(this, PageId, "KindCombo", "TypeCombo", "VariantCombo", "BText", "NameText",
                "ReverseCheck", "KeepLineCheck", "PlateCheck", "PlateSubtypeCombo", "PlateOffsetText");
        }
        public void OnActivated()
        {
            active = true; BracketLocateTool.Picked += OnPicked; BracketLocateTool.Ended += OnEnded;
        }
        public void OnDeactivated() { Close(); }
        public void OnWorkspaceClosing() { Close(); }
        private int revision;
        private void Close()
        {
            PageLastInput.Save(this, PageId, "KindCombo", "TypeCombo", "VariantCombo", "BText", "NameText",
                "ReverseCheck", "KeepLineCheck", "PlateCheck", "PlateSubtypeCombo", "PlateOffsetText");
            revision++; active = false; BracketLocateTool.Picked -= OnPicked; BracketLocateTool.Ended -= OnEnded;
            if (locating) BracketLocateTool.End(); locating = false;
            try { preview.Cancel(); } catch (Exception ex) { Status(ex.Message, true); }
            line = null; dirty = false; ConfirmButton.IsEnabled = false; PreviewUpdateHint.Set(UpdateButton, false);
        }
        private string Kind
        {
            get
            {
                switch (KindCombo.SelectedIndex)
                {
                    case 1:
                        return "D3";
                    case 2:
                        return "G11";
                    default:
                        return "D2";
                }
            }
        }
        private char Variant { get { return D2CantileverCatalog.KeysFor(Kind)[Math.Max(0, VariantCombo.SelectedIndex)]; } }
        private void Kind_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!ready) return;
            ready = false;
            try
            {
                VariantCombo.ItemsSource = D2CantileverCatalog.KeysFor(Kind).ToCharArray();
                VariantCombo.SelectedIndex = 0;
                TypeCombo.ItemsSource = Kind == "G11" ? new[]
                {
                    "类型 1：侧面锚固",
                    "类型 2：上置连接段",
                    "类型 3：下置连接段",
                    "类型 4：楼板顶面锚固",
                    "类型 5：楼板底面锚固"
                } : new[] { "类型 1：单侧悬臂", "类型 2：双侧悬臂" };
                TypeCombo.SelectedIndex = 0;
                if (NameText.Text == "D2" || NameText.Text == "D3" || NameText.Text == "G11") NameText.Text = Kind;
            }
            finally { ready = true; }
            revision++;
            ConfirmButton.IsEnabled = false; dirty = false; PreviewUpdateHint.Set(UpdateButton, false);
            try { preview.Cancel(); line = null; }
            catch (Exception ex) { dirty = true; PreviewUpdateHint.Set(UpdateButton, true); Status(ex.Message, true); }
            PreviewText.Text = "请选择水平辅助线。";
            UpdateSection();
            if (locating) { BracketLocateTool.End(); locating = false; }
        }
        private void UpdateSection()
        {
            bool sideWelded = Kind == "D3";
            TypePanel.Visibility = Kind != "D2" ? Visibility.Visible : Visibility.Collapsed;
            PlatePanel.Visibility = Kind == "D2" ? Visibility.Visible : Visibility.Collapsed;
            LineHintText.Text = sideWelded ? "辅助线长为 L；截面以角钢外角点或槽钢上翼缘角点定位。" :
                "辅助线起点为生根端，终点为悬臂末端；线长为 L，标高为构件顶面。";
            BHintText.Text = sideWelded && TypeCombo.SelectedIndex == 1 ? "B ≤1000；L/2−B ≥150 mm" : "B ≤1000；L−B ≥150 mm";
            BText.ToolTip = sideWelded && TypeCombo.SelectedIndex == 1 ? "已有钢结构中心至任一侧荷载中心的距离；钢结构位于辅助线中点。" : "生根处至荷载中心的距离。";
            SectionText.Text = "构件 A：" + D2CantileverCatalog.Require(Kind, Variant).Section;
            if (Kind == "G11")
            {
                LineHintText.Text = "辅助线起点为悬臂起点，线长为 L，标高为构件顶面。";
                BHintText.Text = "B ≤1000 mm，且 B ≤L";
                G11CantileverVariant variant = G11CantileverCatalog.Require(Variant);
                G2AnchorItem bolt = G2AnchorCatalog.Require(Variant.ToString());
                SectionText.Text += "；2×M" + bolt.BoltDiameterMm + "×" + bolt.BoltLengthMm +
                    "；S=" + variant.BoltSpacingMm + " mm；C=" + variant.ConcreteEdgeDistanceMm + " mm";
                SectionText.ToolTip = "C 为第二根锚栓至混凝土边缘的距离；类型 2、3 连接段两端各留 75 mm。";
            }
            else
            {
                SectionText.ToolTip = null;
            }

            PlateSubtypeCombo.IsEnabled = PlateCheck.IsChecked == true;
            PlateOffsetText.IsEnabled = PlateCheck.IsChecked == true;
        }
        private void Parameter_Changed(object sender, RoutedEventArgs e)
        {
            if (!ready) return;
            UpdateSection(); Changed();
        }
        private void Changed()
        {
            revision++;
            if (line == null) return;
            dirty = true; ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            PreviewText.Text = "参数已变更，请更新预览后再确定生成。";
        }
        private static double Number(string text, string name)
        {
            double value;
            if (!double.TryParse(text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
                throw new InvalidOperationException(name + "应为数字。");
            return value;
        }
        private D2CantileverParameters Parameters()
        {
            return new D2CantileverParameters
            {
                Kind = Kind,
                Type = Kind != "D2" ? Math.Max(0, TypeCombo.SelectedIndex) + 1 : 1,
                Subtype = Variant,
                LoadDistanceMm = Number(BText.Text, "荷载距离 B"),
                Name = NameText.Text,
                Reverse = ReverseCheck.IsChecked == true,
                KeepAuxiliaryLine = KeepLineCheck.IsChecked == true,
                AddPlate = Kind == "D2" && PlateCheck.IsChecked == true,
                PlateSubtype = "ABCD"[Math.Max(0, PlateSubtypeCombo.SelectedIndex)].ToString(),
                PlateOffsetMm = Kind == "D2" && PlateCheck.IsChecked == true ? Number(PlateOffsetText.Text, "端板外移") : 0
            };
        }
        private static double Length(PipeClampSelection value)
        { return Math.Sqrt(value.AxisX * value.AxisX + value.AxisY * value.AxisY + value.AxisZ * value.AxisZ); }
        private static void ValidateLine(PipeClampSelection value)
        {
            if (value.IsPipe || !value.IsAuxiliaryLine)
                throw new InvalidOperationException("请选择绘制好的水平辅助直线。");
            double horizontal = Math.Sqrt(value.AxisX * value.AxisX + value.AxisY * value.AxisY);
            if (horizontal < 1e-9 || Math.Abs(value.AxisZ) > 1)
                throw new InvalidOperationException("辅助线应水平，两端高差不得超过 1 mm。");
        }
        private void Regenerate()
        {
            if (line == null) return;
            dirty = true; ConfirmButton.IsEnabled = false; PreviewUpdateHint.Set(UpdateButton, true);
            try
            {
                ValidateLine(line);
                var p = Parameters();
                double heading = Math.Atan2(p.Reverse ? -line.AxisY : line.AxisY,
                    p.Reverse ? -line.AxisX : line.AxisX) * 180 / Math.PI;
                var plan = D2CantileverCalculator.Calculate(p, Length(line), heading);
                preview.Show(plan, line); dirty = false; PreviewUpdateHint.Set(UpdateButton, false);
                ConfirmButton.IsEnabled = true;
                PreviewText.Text = "预览：" + plan.Number + " · L " + plan.LengthMm.ToString("0.#") + " mm" +
                    (plan.VerticalLoadKn.HasValue ? "\n允许荷载：垂直 " + plan.VerticalLoadKn.Value.ToString("0.#") +
                        " kN" + (plan.HorizontalLoadKn.HasValue ? "；水平 " + plan.HorizontalLoadKn.Value.ToString("0.#") + " kN" : "") :
                        "\n该 B 档位未给出允许荷载值，请核对选型。");
                Status(Kind + " 悬臂架预览已生成。", false);
            }
            catch (Exception ex)
            {
                ConfirmButton.IsEnabled = false; PreviewText.Text = "预览未更新：" + ex.Message;
                Status(ex.Message, true);
            }
        }
        private void OnPicked(LocatedElement located)
        {
            if (!active || !locating || located == null) return;
            int ticket = revision;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || !locating || ticket != revision) return;
                try
                {
                    ConfirmButton.IsEnabled = false; preview.Cancel(); dirty = false;
                    line = PipeClampReader.Read(located.ModelRef, located.ElementId,
                        located.ClickX, located.ClickY, located.ClickZ);
                    ValidateLine(line);
                    KeepLineCheck.IsEnabled = !line.IsFromReference;
                    if (line.IsFromReference) KeepLineCheck.IsChecked = true;
                    Regenerate();
                }
                catch (Exception ex)
                {
                    line = null; dirty = false; ConfirmButton.IsEnabled = false;
                    PreviewUpdateHint.Set(UpdateButton, false); PreviewText.Text = "点取失败：" + ex.Message;
                    Status("点取失败：" + ex.Message, true);
                }
            }), DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            revision++; locating = false; try { preview.Cancel(); } catch (Exception ex) { Status(ex.Message, true); }
            line = null; dirty = false; ConfirmButton.IsEnabled = false;
            PreviewText.Text = "已结束点取。"; PreviewUpdateHint.Set(UpdateButton, false);
        }
        private void Pick_Click(object sender, RoutedEventArgs e)
        { try { BracketLocateTool.Begin("请选择水平悬臂辅助线，线长为 L；左键生成悬臂架预览，右键退出。"); locating = true; } catch (Exception ex) { Status(ex.Message, true); } }
        private void End_Click(object sender, RoutedEventArgs e) { BracketLocateTool.End(); }
        private void Update_Click(object sender, RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                revision++; preview.Cancel(); line = null; dirty = false; ConfirmButton.IsEnabled = false;
                PreviewUpdateHint.Set(UpdateButton, false); PreviewText.Text = "已取消预览。"; Status("已取消预览。", false);
            }
            catch (Exception ex) { Status(ex.Message, true); }
        }
        private void Confirm_Click(object sender, RoutedEventArgs e)
        {
            if (dirty || !ConfirmButton.IsEnabled) { Status("请先成功更新预览。", true); return; }
            ConfirmButton.IsEnabled = false;
            Status("正在写入 " + Kind + " 清单…", false);

            try
            {
                bool delete = line != null && line.IsAuxiliaryLine && !line.IsFromReference &&
                    KeepLineCheck.IsChecked != true;
                ulong id = line == null ? 0 : line.ElementId;
                string writeElapsed = WriteDuration.Measure(preview.Confirm);
                if (delete) try { DeleteLine(id); }
                    catch (Exception ex)
                    {
                        Status(Kind + " 已生成，但辅助线未删除：" + ex.Message + "；写入耗时 " + writeElapsed + "。", true);
                        PreviewText.Text = Kind + " 已生成；写入耗时 " + writeElapsed + "。辅助线未删除：" + ex.Message;
                        revision++; line = null; dirty = false; PreviewUpdateHint.Set(UpdateButton, false); return;
                    }
                revision++; line = null; dirty = false; ConfirmButton.IsEnabled = false; PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "已确认生成并写入清单，可继续点取下一条辅助线。";
                PreviewText.Text += " 写入耗时 " + writeElapsed + "。";
                Status(Kind + " 悬臂架已生成；写入耗时 " + writeElapsed + "。", false);
            }
            catch (Exception ex)
            {
                ConfirmButton.IsEnabled = preview.HasPreview;
                Status("确认失败：" + ex.Message, true);
            }
        }
        private static void DeleteLine(ulong id)
        {
            var model = Session.Instance.GetActiveDgnModel();
            var element = model == null ? null : model.FindElementById(new ElementId(ref id));
            if (element == null || !element.IsValid) return;
            var com = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference
                .GetElementByID64(checked((long)id));
            if (com == null || com.Type != Bentley.Interop.MicroStationDGN.MsdElementType.Line)
                throw new InvalidOperationException("所选辅助线不再是普通直线，未删除。");
            var status = element.DeleteFromModel();
            if (status != StatusInt.Success) throw new InvalidOperationException("辅助线删除失败：" + status);
        }
        private static void Status(string message, bool error)
        { if (MainWindow.Current != null) MainWindow.Current.SetStatus(message, error); }
    }
}
