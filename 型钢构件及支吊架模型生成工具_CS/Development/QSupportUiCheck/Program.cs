using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using System.Xml.Linq;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool pass, string label) { checks++; if (!pass) throw new Exception(label); }
        [STAThread] private static int Main(string[] args)
        {
            try
            {
                string project = Path.GetFullPath(args[0]);
                string output = Path.Combine(project, "Development/QSupportUiCheck/previews"); Directory.CreateDirectory(output);
                var root = Load(Path.Combine(project, "UI/WorkspaceView.xaml"));
                ((FrameworkElement)root.FindName("HeaderRow")).Visibility = Visibility.Collapsed;
                ((RowDefinition)root.FindName("HeaderRowDef")).MinHeight = 0;
                var page = new Q1SupportPage(); NativePanelLayout.Apply(page); ((ContentControl)root.FindName("PageHost")).Content = page;
                Arrange(root);
                Check(page.ActualWidth == 398, "固定400外框");
                Check(((FrameworkElement)page.FindName("ModuleHeader")).ActualHeight == 63, "原型63模块头");
                Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight == 46, "46共享底栏");
                Check(((FrameworkElement)root.FindName("PageHost")).Margin.Left == 0, "无旧模块外边距");
                Check(((Button)root.FindName("HomeEnterButton")).Visibility == Visibility.Collapsed, "模块不显示首页进入按钮");
                foreach (string name in new[] { "SeriesCombo", "TypeCombo", "SmallDnCombo", "HeightText", "Q2ItemCombo", "BearingCombo", "MirrorCheck", "SpecificationText", "AxisOffsetText", "AxisPositionText", "PreviewText", "AngleButton", "UpdateButton", "ConfirmButton" }) Check(page.FindName(name) != null, "原控件契约 " + name);
                foreach (string name in new[] { "ModuleHeader", "ParameterScroll", "PreviewDock", "SelectionResult", "ConfirmButton" })
                {
                    var node = (FrameworkElement)page.FindName(name); var point = node.TranslatePoint(new Point(), root);
                    Console.WriteLine(name + " x=" + point.X + " y=" + point.Y + " w=" + node.ActualWidth + " h=" + node.ActualHeight);
                }
                var dock = (FrameworkElement)page.FindName("PreviewDock"); double dockY = dock.TranslatePoint(new Point(), root).Y; Check(dock.ActualHeight == 302,"原型302固定操作区");
                var scroll = (ScrollViewer)page.FindName("ParameterScroll"); scroll.ScrollToBottom(); Arrange(root);
                Check(dock.TranslatePoint(new Point(), root).Y == dockY, "参数滚动不移动操作区");
                Save(root, Path.Combine(output, "q1-result-400-880.png")); scroll.ScrollToTop(); Arrange(root); Save(root, Path.Combine(output, "q1-400-880.png"));
                var input = (TextBox)page.FindName("HeightText");
                var increment = Children<Button>(page).First(b => (b.Tag as string) == "HeightText:50");
                increment.RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); Check(input.Text == "550", "数值步进编辑原输入");
                var mirror = (CheckBox)page.FindName("MirrorCheck"); mirror.IsChecked = true; Arrange(root); Save(root, Path.Combine(output, "q1-mirror-400-880.png"));
                ((ComboBox)page.FindName("SeriesCombo")).SelectedIndex = 1;
                ((ComboBox)page.FindName("TypeCombo")).SelectedIndex = 3; ((ComboBox)page.FindName("Q2ItemCombo")).SelectedIndex = 1;
                ((TextBlock)page.FindName("SpecificationText")).Text = "子项 B · ∠75×7 · 允许荷载 1 kN";
                Arrange(root); Check(((FrameworkElement)page.FindName("AngleButton")).Visibility == Visibility.Visible, "Q2类型4角度入口");
                Check(((FrameworkElement)page.FindName("Q2Panel")).Visibility == Visibility.Visible, "Q2附加选型");
                Check(((ComboBox)page.FindName("BearingCombo")).ActualWidth > 300, "窄版完整选型宽度");
                scroll.ScrollToTop(); Arrange(root); Save(root, Path.Combine(output, "q2-type4-400-880.png"));
                NativePanelLayoutChecks.Verify(root,page,Check);foreach (double dpi in new[] { 1d, 1.25, 1.5, 2 })
                {
                    Arrange(root); var confirm = (Button)page.FindName("ConfirmButton"); var pos = confirm.TranslatePoint(new Point(), root);
                    Check(pos.Y + confirm.ActualHeight < 833, "确认不被底栏遮挡 " + dpi);
                    var bitmap = new RenderTargetBitmap((int)(400 * dpi), (int)(880 * dpi), 96 * dpi, 96 * dpi, PixelFormats.Pbgra32); bitmap.Render(root);
                    Check(bitmap.PixelHeight == (int)(880 * dpi), "DPI逻辑尺寸 " + dpi);
                }
                var result = new QSupportResultConverter();
                Check((string)result.Convert("子项 B · ∠75×7 · 允许荷载 1 kN", typeof(string), "Angle", null) == "∠75×7", "选型展示消费原摘要");
                Check((Visibility)result.Convert("中心间距无效", typeof(Visibility), "ErrorVisibility", null) == Visibility.Visible, "错误摘要保持可见");
                ((ContentControl)root.FindName("PageHost")).Content = new UserControl(); root.Measure(new Size(560,720)); root.Arrange(new Rect(0,0,560,720)); root.UpdateLayout();
                Check(((FrameworkElement)root.FindName("PageHost")).Margin == new Thickness(14,4,10,10), "其他模块原布局保留");
                Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight == 36, "其他模块原底栏保留");
                Console.WriteLine("PASS: " + checks + " Q1/Q2原型展示、固定操作区和DPI检查。"); return 0;
            }
            catch (Exception e) { Console.Error.WriteLine(e); return 1; }
        }
        private static void Arrange(FrameworkElement root) { root.Measure(new Size(400,880)); root.Arrange(new Rect(0,0,400,880)); root.UpdateLayout(); root.Dispatcher.Invoke(() => { }, DispatcherPriority.Background); root.UpdateLayout(); }
        private static void Save(FrameworkElement root,string path) { var bmp = new RenderTargetBitmap(400,880,96,96,PixelFormats.Pbgra32); bmp.Render(root); var png = new PngBitmapEncoder(); png.Frames.Add(BitmapFrame.Create(bmp)); using (var file = File.Create(path)) png.Save(file); }
        private static System.Collections.Generic.IEnumerable<T> Children<T>(DependencyObject parent) where T : DependencyObject
        { if(parent is T) yield return (T)parent; for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++) foreach(var child in Children<T>(VisualTreeHelper.GetChild(parent,i))) yield return child; }
        private static UserControl Load(string path)
        {
            var doc = XDocument.Load(path); XNamespace x = "http://schemas.microsoft.com/winfx/2006/xaml"; doc.Root.Attribute(x+"Class").Remove(); doc.Root.Attribute(x+"ClassModifier").Remove();
            foreach (var element in doc.Descendants())
            {
                foreach (var a in element.Attributes().Where(a => a.Name.LocalName == "Click").ToArray()) a.Remove();
                if (element.Name.LocalName == "ResourceDictionary" && element.Attribute("Source") != null) element.Attribute("Source").Value = new Uri(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path),element.Attribute("Source").Value))).AbsoluteUri;
            }
            using(var reader=doc.CreateReader()) return (UserControl)XamlReader.Load(reader);
        }
    }
}
