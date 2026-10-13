using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace SteelSectionProbe
{
    /// <summary>已改造工具页共用的原型标题栏；导航沿用工作区生命周期。</summary>
    internal partial class PrototypeChrome : UserControl
    {
        public static readonly DependencyProperty TitleProperty = DependencyProperty.Register("Title", typeof(string), typeof(PrototypeChrome), new PropertyMetadata(""));
        public static readonly DependencyProperty CaptionProperty = DependencyProperty.Register("Caption", typeof(string), typeof(PrototypeChrome), new PropertyMetadata(""));
        public static readonly DependencyProperty CodeProperty = DependencyProperty.Register("Code", typeof(string), typeof(PrototypeChrome), new PropertyMetadata(""));
        public static readonly DependencyProperty IconProperty = DependencyProperty.Register("Icon", typeof(Geometry), typeof(PrototypeChrome), new PropertyMetadata(null));
        public string Title { get { return (string)GetValue(TitleProperty); } set { SetValue(TitleProperty, value); } }
        public string Caption { get { return (string)GetValue(CaptionProperty); } set { SetValue(CaptionProperty, value); } }
        public string Code { get { return (string)GetValue(CodeProperty); } set { SetValue(CodeProperty, value); } }
        public Geometry Icon { get { return (Geometry)GetValue(IconProperty); } set { SetValue(IconProperty, value); } }
        public PrototypeChrome() { InitializeComponent(); }
        private void Home_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.ShowHome(); }
        private void Minimize_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.MinimizeFromHome(); }
        private void Close_Click(object sender, RoutedEventArgs e) { MainWindow.Current?.Close(); }
        private void Title_MouseLeftButtonDown(object sender, MouseButtonEventArgs e) { MainWindow.Current?.BeginTitleDrag(); }
    }
}
