using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace SteelSectionProbe
{
    /// <summary>原型页面的窗口导航与数值步进，仅编辑原输入控件。</summary>
    internal partial class Q1SupportPage
    {
        private void BackHome_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.ShowHome(); }
        private void TitleDrag_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.OriginalSource is System.Windows.Controls.Primitives.ButtonBase) return;
            MainWindow.Current?.BeginTitleDrag();
        }
        private void MinimizeUi_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.MinimizeFromHome(); }
        private void CloseUi_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.Close(); }
        private void StepUi_Click(object sender, RoutedEventArgs e)
        {
            var button = (Button)sender;
            string[] command = ((string)button.Tag).Split(':');
            var input = (TextBox)FindName(command[0]);
            if (!input.IsEnabled) return;
            double value;
            if (!double.TryParse(input.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(input.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out value)) return;
            if (double.IsNaN(value) || double.IsInfinity(value)) return;
            value += double.Parse(command[1], CultureInfo.InvariantCulture);
            // 与直接输入相同：由原 TextChanged 处理失效、校验和预览提示。
            input.Text = value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
