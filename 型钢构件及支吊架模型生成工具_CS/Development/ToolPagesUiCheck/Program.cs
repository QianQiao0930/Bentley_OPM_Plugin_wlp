using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
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
        private static void Check(bool pass,string label){checks++;if(!pass)throw new Exception(label);}
        [STAThread] private static int Main(string[] args)
        {
            try
            {
                string project=Path.GetFullPath(args[0]), output=Path.Combine(project,"Development/ToolPagesUiCheck/previews");Directory.CreateDirectory(output);
                var root=Load(Path.Combine(project,"UI/WorkspaceView.xaml"));
                ((FrameworkElement)root.FindName("HeaderRow")).Visibility=Visibility.Collapsed;((RowDefinition)root.FindName("HeaderRowDef")).MinHeight=0;
                var host=(ContentControl)root.FindName("PageHost");
                var query=new ComponentPropertiesPage();
                ((TextBox)query.FindName("SelectionText")).Text="管道 P-1001 · DN100 · PIPE";
                var results=(DataGrid)query.FindName("ResultItems");results.ItemsSource=new[]{new PropertyFixture{Label="公称直径",Value="DN100"},new PropertyFixture{Label="管道号",Value="P-1001"},new PropertyFixture{Label="构件类型",Value="PIPE"},new PropertyFixture{Label="几何信息",Value="这是用于检查长属性自动换行的示例文本，不读取用户模型。"}};
                var stats=new SupportStatisticsPage();((TextBlock)stats.FindName("TotalText")).Text="12 套";((TextBlock)stats.FindName("CountText")).Text="整组12条 · 构件48条 · 材料8项";((TextBlock)stats.FindName("FileText")).Text="示例文件.dgn · 读取时间：展示夹具";
                ((DataGrid)stats.FindName("TypeGrid")).ItemsSource=new[]{new StatisticsFixture{SupportType="Q1 大管支撑小管",AssemblyCount=4,AssemblyTags="Q1-1-C-DN100-DN80-500"}};
                foreach(var pair in new[]{Tuple.Create("component-properties",(UserControl)query),Tuple.Create("support-statistics",(UserControl)stats),Tuple.Create("activation",(UserControl)new ActivationPage()),Tuple.Create("about",(UserControl)new AboutPage())})
                {
                    var page=pair.Item2;host.Content=page;
                    if(page is ActivationPage activation)activation.OnActivated();
                    ((TextBlock)root.FindName("StatusText")).Text="状态消息支持两行显示：读取当前 DGN 的构件属性与支吊架材料清单，详细内容可悬停查看。";
                    Arrange(root);Check(page.ActualWidth==398,"400外框 "+pair.Item1);Check(host.Margin.Left==0,"原型零外边距 "+pair.Item1);Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==46,"46底栏 "+pair.Item1);
                    var chrome=Children<PrototypeChrome>(page).Single();Check(chrome.ActualHeight==95,"32+63模块头 "+pair.Item1);
                    var status=(TextBlock)root.FindName("StatusText");Check(status.FontSize==10.5&&status.TextWrapping==TextWrapping.Wrap&&status.MaxHeight==28,"双行小字体 "+pair.Item1);Check(status.ActualHeight==28,"长消息双行 "+pair.Item1);
                    Check(((Button)root.FindName("HomeEnterButton")).Visibility==Visibility.Collapsed,"模块无首页进入按钮 "+pair.Item1);
                    Save(root,Path.Combine(output,pair.Item1+"-400-880.png"));
                    foreach(double scale in new[]{1d,1.25,1.5,2}){var bmp=new RenderTargetBitmap((int)(400*scale),(int)(880*scale),96*scale,96*scale,PixelFormats.Pbgra32);bmp.Render(root);Check(bmp.PixelHeight==(int)(880*scale),"DPI "+pair.Item1+scale);}
                    foreach(var button in Children<Button>(page).Where(b=>b.IsVisible)){var p=button.TranslatePoint(new Point(),root);Check(p.X+button.ActualWidth<=400.1,"按钮右边界 "+pair.Item1+button.Content);}
                }
                Check(results.Columns.Count==2,"查询结果全部列保留");Check(((DataGrid)stats.FindName("SupportGrid")).Columns.Count==6,"支吊架全部列保留");Check(((DataGrid)stats.FindName("MaterialGrid")).Columns.Count==6,"材料全部列保留");
                var act=new ActivationPage();host.Content=act;act.OnActivated();act.FindName("ActivationCodeText");var input=(TextBox)act.FindName("ActivationCodeText");input.Text="无效展示输入";act.OnDeactivated();Check(input.Text=="","真实页面离开清理授权输入");
                LicenseService.IsLicensingEnabled=false;var unlicensed=new AboutPage();host.Content=unlicensed;Arrange(root);Check(((FrameworkElement)unlicensed.FindName("LicensingCard")).Visibility==Visibility.Collapsed,"无授权版作者页隐藏授权卡片");Save(root,Path.Combine(output,"about-unlicensed-400-880.png"));
                host.Content=new UserControl();root.Measure(new Size(560,720));root.Arrange(new Rect(0,0,560,720));root.UpdateLayout();Check(host.Margin==new Thickness(14,4,10,10),"未改模块恢复原外边距");Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==36,"未改模块原底栏");
                host.Content=new UserControl{Tag="home"};Arrange(root);var homeStatus=(TextBlock)root.FindName("StatusText");Check(homeStatus.FontSize==10.5&&homeStatus.ActualHeight==28,"首页双行状态");Save(root,Path.Combine(output,"footer-two-lines-400-880.png"));
                Console.WriteLine("PASS: "+checks+" 工具页布局、展示、双行状态和DPI检查。");return 0;
            }catch(Exception e){Console.Error.WriteLine(e);return 1;}
        }
        public sealed class PropertyFixture{public string Label{get;set;}public string Value{get;set;}}
        public sealed class StatisticsFixture{public string SupportType{get;set;}public int AssemblyCount{get;set;}public string AssemblyTags{get;set;}}
        private static void Arrange(FrameworkElement root){root.Measure(new Size(400,880));root.Arrange(new Rect(0,0,400,880));root.UpdateLayout();root.Dispatcher.Invoke(()=>{},DispatcherPriority.Background);root.UpdateLayout();}
        private static void Save(FrameworkElement root,string path){var bmp=new RenderTargetBitmap(400,880,96,96,PixelFormats.Pbgra32);bmp.Render(root);var png=new PngBitmapEncoder();png.Frames.Add(BitmapFrame.Create(bmp));using(var file=File.Create(path))png.Save(file);}
        private static System.Collections.Generic.IEnumerable<T> Children<T>(DependencyObject parent)where T:DependencyObject{if(parent is T)yield return (T)parent;for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++)foreach(var child in Children<T>(VisualTreeHelper.GetChild(parent,i)))yield return child;}
        private static UserControl Load(string path){var doc=XDocument.Load(path);XNamespace x="http://schemas.microsoft.com/winfx/2006/xaml";doc.Root.Attribute(x+"Class").Remove();doc.Root.Attribute(x+"ClassModifier").Remove();foreach(var e in doc.Descendants()){foreach(var a in e.Attributes().Where(a=>a.Name.LocalName=="Click").ToArray())a.Remove();if(e.Name.LocalName=="ResourceDictionary"&&e.Attribute("Source")!=null)e.Attribute("Source").Value=new Uri(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path),e.Attribute("Source").Value))).AbsoluteUri;}using(var reader=doc.CreateReader())return (UserControl)XamlReader.Load(reader);}
    }
}
