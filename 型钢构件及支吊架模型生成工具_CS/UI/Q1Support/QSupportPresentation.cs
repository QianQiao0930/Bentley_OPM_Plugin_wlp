using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace SteelSectionProbe
{
    /// <summary>从原页面的选型摘要读取显示字段，不参与领域参数和建模。</summary>
    internal sealed class QSupportResultConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            string text = value as string ?? "";
            string[] parts = text.Split('\n')[0].Split(new[] { " · " }, StringSplitOptions.None);
            bool valid = parts.Length == 3 && parts[0].StartsWith("子项 ", StringComparison.Ordinal);
            string key = parameter as string;
            if (key == "ErrorVisibility") return valid ? Visibility.Collapsed : Visibility.Visible;
            if (!valid) return "—";
            if (key == "Subitem") return parts[0].Substring(3);
            if (key == "Angle") return parts[1];
            return parts[2].Replace("允许荷载 ", "");
        }
        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) { throw new NotSupportedException(); }
    }

    internal sealed class QSupportLayoutConverter : IMultiValueConverter
    {
        public object Convert(object[] values, Type targetType, object parameter, CultureInfo culture)
        {
            int index = values[0] is int ? (int)values[0] : 0;
            return "T" + (index + 1) + " · " + (values[1] is bool && (bool)values[1] ? "左侧" : "右侧");
        }
        public object[] ConvertBack(object value, Type[] targetTypes, object parameter, CultureInfo culture) { throw new NotSupportedException(); }
    }

    internal sealed class QSupportRangeConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            double number;
            if (!double.TryParse(value as string, NumberStyles.Float, CultureInfo.CurrentCulture, out number) &&
                !double.TryParse(value as string, NumberStyles.Float, CultureInfo.InvariantCulture, out number)) return 0d;
            return double.IsNaN(number) || double.IsInfinity(number) ? 0d : Math.Max(0, Math.Min(1000, number));
        }
        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) { throw new NotSupportedException(); }
    }

    /// <summary>随系列、类型和镜像变化的二维选型示意；不绘制或改写宿主模型。</summary>
    internal sealed class QSupportSchematic : FrameworkElement
    {
        public static readonly DependencyProperty SeriesProperty = DependencyProperty.Register("Series", typeof(int), typeof(QSupportSchematic), new FrameworkPropertyMetadata(0, FrameworkPropertyMetadataOptions.AffectsRender));
        public static readonly DependencyProperty LayoutProperty = DependencyProperty.Register("Layout", typeof(int), typeof(QSupportSchematic), new FrameworkPropertyMetadata(0, FrameworkPropertyMetadataOptions.AffectsRender));
        public static readonly DependencyProperty MirroredProperty = DependencyProperty.Register("Mirrored", typeof(bool), typeof(QSupportSchematic), new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.AffectsRender));
        public int Series { get { return (int)GetValue(SeriesProperty); } set { SetValue(SeriesProperty, value); } }
        public int Layout { get { return (int)GetValue(LayoutProperty); } set { SetValue(LayoutProperty, value); } }
        public bool Mirrored { get { return (bool)GetValue(MirroredProperty); } set { SetValue(MirroredProperty, value); } }
        protected override void OnRender(DrawingContext drawing)
        {
            base.OnRender(drawing);
            var grid = new Pen(new SolidColorBrush(Color.FromRgb(238, 242, 247)), 0.5);
            for (int n = 0; n <= 112; n += 8) drawing.DrawLine(grid, new Point(n, 0), new Point(n, ActualHeight));
            for (int n = 0; n <= ActualHeight; n += 8) drawing.DrawLine(grid, new Point(0, n), new Point(112, n));
            drawing.PushTransform(new TranslateTransform(Mirrored ? 112 : 0, 0));
            drawing.PushTransform(new ScaleTransform(Mirrored ? -1 : 1, 1));
            var steel = new Pen(new SolidColorBrush(Color.FromRgb(14, 159, 154)), 3);
            var big = new Pen(new SolidColorBrush(Color.FromRgb(91, 107, 123)), 1.4);
            var small = new Pen(new SolidColorBrush(Color.FromRgb(31, 111, 235)), 1.4);
            var dimension = new Pen(new SolidColorBrush(Color.FromRgb(232, 163, 23)), 1);
            if (Series == 0)
            {
                bool above = Layout == 1 || Layout == 2;
                double bigY = above ? 71 : 25, smallY = above ? 25 : 71;
                drawing.DrawEllipse(new SolidColorBrush(Color.FromRgb(241, 244, 247)), big, new Point(56, bigY), 15, 15);
                if (Layout < 2) drawing.DrawRoundedRectangle(new SolidColorBrush(Color.FromRgb(234, 242, 255)), small, new Rect(39, smallY - 6, 34, 12), 1, 1);
                else drawing.DrawEllipse(new SolidColorBrush(Color.FromRgb(234, 242, 255)), small, new Point(62, smallY), 9, 9);
                drawing.DrawLine(steel, new Point(78, 15), new Point(78, 84));
                drawing.DrawLine(steel, new Point(78, 84), new Point(39, 84));
                drawing.DrawLine(dimension, new Point(22, 25), new Point(22, 71));
                foreach (double y in new[] { 25d, 71d }) drawing.DrawLine(dimension, new Point(18, y), new Point(26, y));
            }
            else
            {
                drawing.DrawLine(steel, new Point(15, 64), new Point(100, 64));
                drawing.DrawLine(steel, new Point(15, 64), new Point(15, 72));
                double bigX = Layout == 0 ? 56 : 30;
                if (Layout == 3) drawing.DrawRoundedRectangle(Brushes.White, big, new Rect(bigX - 9, 22, 18, 47), 2, 2);
                else drawing.DrawEllipse(Brushes.White, big, new Point(bigX, 48), 15, 15);
                if (Layout == 0) drawing.DrawEllipse(new SolidColorBrush(Color.FromRgb(234, 242, 255)), small, new Point(20, 56), 7, 7);
                if (Layout >= 2)
                {
                    drawing.DrawRoundedRectangle(new SolidColorBrush(Color.FromRgb(234, 242, 255)), small, new Rect(80, 29, 13, 42), 2, 2);
                    drawing.DrawRectangle(new SolidColorBrush(Color.FromRgb(14, 159, 154)), null, new Rect(76, 48, 4, 15));
                }
                else drawing.DrawEllipse(new SolidColorBrush(Color.FromRgb(234, 242, 255)), small, new Point(87, 56), 7, 7);
                drawing.DrawLine(dimension, new Point(bigX, 82), new Point(87, 82));
                foreach (double x in new[] { bigX, 87d }) drawing.DrawLine(dimension, new Point(x, 78), new Point(x, 86));
            }
            drawing.Pop(); drawing.Pop();
            var label = new FormattedText(Series == 0 ? "H" : "L", CultureInfo.InvariantCulture, FlowDirection.LeftToRight, new Typeface("Consolas"), 9, new SolidColorBrush(Color.FromRgb(181, 122, 0)), VisualTreeHelper.GetDpi(this).PixelsPerDip);
            drawing.DrawText(label, Series == 0 ? new Point(Mirrored ? 91 : 12, 42) : new Point(57, 84));
        }
    }
}
