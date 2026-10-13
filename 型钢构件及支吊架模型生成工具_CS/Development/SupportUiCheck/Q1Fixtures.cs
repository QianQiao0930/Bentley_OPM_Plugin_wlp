using System; using System.Windows; using System.Windows.Controls; namespace SteelSectionProbe {
    internal partial class Q1SupportPage : UserControl
    {
        internal Q1SupportPage()
        {
            InitializeComponent();
            SmallDnCombo.ItemsSource = new[] { "DN15 | 1/2\"", "DN80 | 3\"", "DN100 | 4\"" };
            SmallDnCombo.SelectedIndex = 1;
            SpecificationText.Text = "子项 C · ∠100×10 · 允许荷载 3 kN";
        }
        private void Series_Changed(object sender, RoutedEventArgs e)
        {
            if (Q2Panel == null) return;
            Q2Panel.Visibility = SeriesCombo.SelectedIndex == 1 ? Visibility.Visible : Visibility.Collapsed;
            DistanceLabel.Text = SeriesCombo.SelectedIndex == 1 ? "两管中心间距 L（mm，最大1000）" : "小管与大管中心间距 H（mm，最大1000）";
            int type = TypeCombo.SelectedIndex; TypeCombo.Items.Clear();
            foreach (string text in SeriesCombo.SelectedIndex == 1 ? new[] { "类型1 · 水平大管，两侧水平小管", "类型2 · 水平大管，单侧水平小管", "类型3 · 水平大管，单侧立管", "类型4 · 立管支撑立管" } : new[] { "类型1 · 小管在下，两管垂直", "类型2 · 小管在上，两管垂直", "类型3 · 小管在上，两管平行（带垫板）", "类型4 · 小管在下，两管平行（带垫板）" }) TypeCombo.Items.Add(text);
            TypeCombo.SelectedIndex = Math.Max(0,type); Parameter_Changed(sender, e);
        }
        private void Parameter_Changed(object sender, RoutedEventArgs e)
        {
            if (AngleButton == null) return;
            AngleButton.Visibility = SeriesCombo.SelectedIndex == 1 && TypeCombo.SelectedIndex == 3 ? Visibility.Visible : Visibility.Collapsed;
            ConfirmButton.IsEnabled = false;
        }
        private void AxisOffset_Changed(object sender, RoutedEventArgs e) { if (ConfirmButton != null) ConfirmButton.IsEnabled = false; }
        private void Pick_Click(object sender, RoutedEventArgs e) { }
        private void End_Click(object sender, RoutedEventArgs e) { }
        private void Update_Click(object sender, RoutedEventArgs e) { }
        private void Angle_Click(object sender, RoutedEventArgs e) { }
        private void Slide_Click(object sender, RoutedEventArgs e) { }
        private void ApplyOffset_Click(object sender, RoutedEventArgs e) { }
        private void Confirm_Click(object sender, RoutedEventArgs e) { }
    }

}