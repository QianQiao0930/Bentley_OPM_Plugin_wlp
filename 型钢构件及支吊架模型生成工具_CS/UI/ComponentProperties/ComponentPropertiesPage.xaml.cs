using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class PropertyRow
    {
        public string Label { get; set; }
        public string Value { get; set; }
    }

    internal partial class ComponentPropertiesPage : UserControl, IWorkspacePage
    {
        private ComponentSnapshot snapshot;
        private bool active;
        private int requestVersion;

        public string PageId { get { return "component-properties"; } }
        public string PageTitle { get { return "构件特性查询"; } }
        public string PageSubtitle { get { return "点取构件并读取 EC 属性与几何信息"; } }
        public FrameworkElement View { get { return this; } }

        internal ComponentPropertiesPage()
        {
            InitializeComponent();
            ComponentLocateTool.ElementPicked += OnElementPicked;
            ComponentLocateTool.SelectionEnded += OnSelectionEnded;
        }

        public void OnActivated() { active = true; }
        public void OnDeactivated()
        {
            active = false;
            requestVersion++;
            ComponentLocateTool.End();
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            ComponentLocateTool.ElementPicked -= OnElementPicked;
            ComponentLocateTool.SelectionEnded -= OnSelectionEnded;
        }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (Session.Instance.GetActiveDgnModel() == null)
                    throw new InvalidOperationException("请先打开 DGN 模型。");
                ComponentLocateTool.Begin();
                SetStatus("将光标悬停在构件上，左键单击读取；可连续点取，右键结束。", false);
            }
            catch (Exception ex) { SetStatus("无法开始点取：" + ex.Message, true); }
        }

        private void Stop_Click(object sender, RoutedEventArgs e)
        {
            ComponentLocateTool.End();
            SetStatus("已结束点取命令。", false);
        }

        private void OnSelectionEnded()
        {
            if (active) SetStatus("已结束点取命令。", false);
        }

        private void OnElementPicked(ulong id)
        {
            int version = ++requestVersion;
            // Run after the locate callback has returned; never retain a Bentley element here.
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || version != requestVersion) return;
                try
                {
                    snapshot = ComponentPropertyReader.Read(id);
                    SelectionText.Text = "元素 " + id.ToString(CultureInfo.InvariantCulture) +
                        (string.IsNullOrEmpty(snapshot.ClassName) ? "" : "  ·  " + snapshot.ClassName);
                    RefreshRows();
                    SetStatus(string.IsNullOrEmpty(snapshot.ReadWarning)
                        ? "已读取构件特性。可继续点取其他构件。" : snapshot.ReadWarning,
                        !string.IsNullOrEmpty(snapshot.ReadWarning));
                }
                catch (Exception ex) { SetStatus("构件查询失败：" + ex.Message, true); }
            }));
        }

        private void CopyResults_Click(object sender, RoutedEventArgs e)
        {
            var rows = ResultItems.ItemsSource as IEnumerable<PropertyRow>;
            if (rows == null) return;
            var text = new StringBuilder();
            foreach (PropertyRow row in rows)
                text.Append(row.Label).Append('\t').Append(row.Value).AppendLine();
            try
            {
                Clipboard.SetText(text.ToString());
                SetStatus("当前查询结果已复制到剪贴板。", false);
            }
            catch (Exception ex) { SetStatus("复制失败：" + ex.Message, true); }
        }

        private void Unit_SelectionChanged(object sender, SelectionChangedEventArgs e) { RefreshRows(); }
        private void View_Changed(object sender, RoutedEventArgs e) { RefreshRows(); }

        private void RefreshRows()
        {
            if (ResultItems == null || snapshot == null) return;
            var rows = new List<PropertyRow>();
            Add(rows, "元素 ID", snapshot.ElementId.ToString(CultureInfo.InvariantCulture));
            Add(rows, "EC Schema", snapshot.Schema);
            Add(rows, "EC 类", snapshot.ClassName);
            Add(rows, "EC 实例 ID", snapshot.InstanceId);
            Add(rows, "读取提示", snapshot.ReadWarning);
            CopyResultsButton.IsEnabled = true;
            if (AllPropertiesCheck != null && AllPropertiesCheck.IsChecked == true)
            {
                foreach (var pair in snapshot.AllProperties.OrderBy(p => p.Key, StringComparer.OrdinalIgnoreCase))
                    Add(rows, pair.Key, pair.Value);
                ResultItems.ItemsSource = rows;
                return;
            }

            string unit = "auto";
            var selected = UnitCombo == null ? null : UnitCombo.SelectedItem as ComboBoxItem;
            if (selected != null) unit = selected.Tag as string ?? "auto";
            double? rawLength = ComponentPropertyCalculator.Number(snapshot.Properties, "LENGTH");
            double? unitProbe = rawLength ?? ComponentPropertyCalculator.Number(snapshot.Properties, "OUTSIDE_DIAMETER")
                ?? ComponentPropertyCalculator.Number(snapshot.Properties, "NOMINAL_DIAMETER");
            double scale = ComponentPropertyCalculator.LengthScale(unitProbe,
                rawLength.HasValue ? snapshot.LengthMm : null, unit);
            Add(rows, "属性长度单位", scale == 1000 ? "米" : "毫米");
            Add(rows, "判断方式", unit == "auto" ? "自动标定或数值兜底；请核对原值" : "手动指定");

            AddProperty(rows, "管线号", "LINENUMBER");
            AddProperty(rows, "构件名称", "COMPONENT_NAME");
            AddProperty(rows, "名称", "NAME");
            AddProperty(rows, "公称尺寸", "NOMINAL_SIZE");
            AddProperty(rows, "规格 / 管道等级", "SPECIFICATION");
            AddProperty(rows, "材质", "MATERIAL");
            AddProperty(rows, "材料标记", "MATERIAL_MARK");
            AddProperty(rows, "牌号", "GRADE");
            AddProperty(rows, "保温材料", "INSULATION");
            AddProperty(rows, "管段编号", "SPOOL_ID");
            double? nominal = AddLength(rows, "公称直径", "NOMINAL_DIAMETER", scale);
            if (!nominal.HasValue) AddLength(rows, "公称直径（端部）", "NOMINAL_DIAMETER_RUN_END", scale);
            double? outside = AddLength(rows, "外径", "OUTSIDE_DIAMETER", scale);
            AddLength(rows, "壁厚", "WALL_THICKNESS", scale);
            double? insulation = AddLength(rows, "保温厚度", "INSULATION_THICKNESS", scale);
            AddLength(rows, "属性长度", "LENGTH", scale);
            AddLength(rows, "属性标高", "ELEVATION", scale);
            if (outside.HasValue)
            {
                if (insulation.HasValue) Add(rows, "保温后外径", Mm(outside.Value + 2 * insulation.Value));
                int? dn = ComponentPropertyCalculator.NearestDn(outside);
                if (dn.HasValue) Add(rows, "外径反查", "DN" + dn.Value);
            }
            Add(rows, "几何来源", snapshot.GeometrySource);
            Add(rows, "中心线标高", Mm(snapshot.CenterZMm));
            if (snapshot.CenterZMm.HasValue && outside.HasValue)
            {
                double bottom = snapshot.CenterZMm.Value - outside.Value / 2;
                Add(rows, "管底标高", Mm(bottom));
                if (insulation.HasValue) Add(rows, "保温层底标高", Mm(bottom - insulation.Value));
            }
            Add(rows, "几何长度", Mm(snapshot.LengthMm));
            if (snapshot.StartX.HasValue)
            {
                Add(rows, "起点", Point(snapshot.StartX, snapshot.StartY, snapshot.StartZ));
                Add(rows, "终点", Point(snapshot.EndX, snapshot.EndY, snapshot.EndZ));
                Add(rows, "走向", ComponentPropertyCalculator.Orientation(snapshot));
            }
            else if (snapshot.RangeXmm.HasValue)
                Add(rows, "包围盒尺寸", Point(snapshot.RangeXmm, snapshot.RangeYmm, snapshot.RangeZmm) + " mm");
            ResultItems.ItemsSource = rows;
        }

        private void AddProperty(List<PropertyRow> rows, string label, string key)
        {
            string value;
            if (snapshot.Properties.TryGetValue(key, out value)) Add(rows, label, value);
        }
        private double? AddLength(List<PropertyRow> rows, string label, string key, double scale)
        {
            double? raw = ComponentPropertyCalculator.Number(snapshot.Properties, key);
            if (raw.HasValue) Add(rows, label, Mm(raw.Value * scale) + "（原值 " + raw.Value.ToString("G", CultureInfo.InvariantCulture) + "）");
            return raw.HasValue ? raw * scale : null;
        }
        private static void Add(List<PropertyRow> rows, string label, string value)
        {
            if (!string.IsNullOrWhiteSpace(value)) rows.Add(new PropertyRow { Label = label, Value = value });
        }
        private static string Mm(double? value)
        {
            return value.HasValue ? value.Value.ToString("F1", CultureInfo.InvariantCulture) + " mm" : null;
        }
        private static string Point(double? x, double? y, double? z)
        {
            return x.Value.ToString("F1", CultureInfo.InvariantCulture) + ", " +
                y.Value.ToString("F1", CultureInfo.InvariantCulture) + ", " +
                z.Value.ToString("F1", CultureInfo.InvariantCulture);
        }
        private static void SetStatus(string message, bool error)
        {
            if (MainWindow.Current != null) MainWindow.Current.SetStatus(message, error);
        }
    }
}
