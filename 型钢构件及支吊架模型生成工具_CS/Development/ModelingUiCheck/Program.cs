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
                string project=Path.GetFullPath(args[0]),output=Path.Combine(project,"Development/ModelingUiCheck/previews");Directory.CreateDirectory(output);
                var root=Load(Path.Combine(project,"UI/WorkspaceView.xaml"));((FrameworkElement)root.FindName("HeaderRow")).Visibility=Visibility.Collapsed;((RowDefinition)root.FindName("HeaderRowDef")).MinHeight=0;
                var host=(ContentControl)root.FindName("PageHost");
                var pages=new[]{Tuple.Create("steel-sections",(UserControl)new SteelSectionPage()),Tuple.Create("steel-handrail",(UserControl)new HandrailPage()),Tuple.Create("tank-spiral-stair",(UserControl)new SpiralStairPage()),Tuple.Create("tank-ladder",(UserControl)new TankLadderPage()),Tuple.Create("wall-ladder",(UserControl)new WallLadderPage()),Tuple.Create("magnetic-level-gauge",(UserControl)new MagneticGaugePage()),Tuple.Create("pipe-alignment",(UserControl)new PipeAlignmentPage()),Tuple.Create("tank-manhole",(UserControl)new TankManholePage()),Tuple.Create("solid-nozzle",(UserControl)new NozzlePage()),Tuple.Create("square-manhole",(UserControl)new SquareManholePage()),Tuple.Create("fire-cabinet",(UserControl)new FireCabinetPage()),Tuple.Create("hose-cabinet",(UserControl)new HoseCabinetPage())};
                foreach(var pair in pages)
                {
                    var page=pair.Item2;host.Content=page;Arrange(root);Seed(page);Arrange(root);
                    Check(page.ActualWidth==398,"400外框 "+pair.Item1);Check(host.Margin.Left==0,"原型外边距 "+pair.Item1);Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==46,"46底栏 "+pair.Item1);
                    var chrome=Children<PrototypeChrome>(page).Single();Check(chrome.ActualHeight==95,"32+63标题 "+pair.Item1);
                    Save(root,Path.Combine(output,pair.Item1+"-400-880.png"));
                    var confirm=page.FindName("ConfirmButton") as Button;
                    if(confirm!=null){var point=confirm.TranslatePoint(new Point(),root);Check(point.Y+confirm.ActualHeight<=833.1,"确认初始可见 "+pair.Item1);Check(point.X+confirm.ActualWidth<=399.1,"确认右边界 "+pair.Item1);}
                    var scroll=Children<ScrollViewer>(page).FirstOrDefault(s=>s.VerticalScrollBarVisibility==ScrollBarVisibility.Auto&&s.HorizontalScrollBarVisibility==ScrollBarVisibility.Disabled);
                    if(scroll!=null){double y=confirm==null?0:confirm.TranslatePoint(new Point(),root).Y;scroll.ScrollToBottom();Arrange(root);if(confirm!=null)Check(Math.Abs(confirm.TranslatePoint(new Point(),root).Y-y)<.01,"滚动不移动操作区 "+pair.Item1);Save(root,Path.Combine(output,pair.Item1+"-parameters-bottom.png"));scroll.ScrollToTop();Arrange(root);}
                    foreach(var button in Children<Button>(page).Where(b=>b.IsVisible&&b.ActualWidth>30)){var pos=button.TranslatePoint(new Point(),root);Check(pos.X+button.ActualWidth<=400.1,"操作按钮不超右边界 "+pair.Item1+button.Content);}
                    var tabs=page.FindName("PageTabs") as TabControl;
                    if(tabs!=null){tabs.SelectedIndex=1;Arrange(root);Check(((DataGrid)page.FindName("SummaryGrid")).Columns.Count==5,"消防全部统计列 "+pair.Item1); Check(((DataGrid)page.FindName("SummaryGrid")).Columns.Sum(c=>c.MinWidth)>((DataGrid)page.FindName("SummaryGrid")).ActualWidth,"统计列保持可读宽度并横向滚动 "+pair.Item1);Save(root,Path.Combine(output,pair.Item1+"-statistics-400-880.png"));tabs.SelectedIndex=0;Arrange(root);}
                    foreach(double scale in new[]{1d,1.25,1.5,2}){var bmp=new RenderTargetBitmap((int)(400*scale),(int)(880*scale),96*scale,96*scale,PixelFormats.Pbgra32);bmp.Render(root);Check(bmp.PixelHeight==(int)(880*scale),"DPI "+pair.Item1+scale);}
                    Console.WriteLine(pair.Item1+": 400x880, original controls and fixed actions rendered.");
                }
                TankLadderFixtures.CheckLifecycle((TankLadderPage)pages.First(p=>p.Item1=="tank-ladder").Item2,()=>Arrange(root),Check);
                WallLadderFixtures.CheckLifecycle((WallLadderPage)pages.First(p=>p.Item1=="wall-ladder").Item2,()=>Arrange(root),Check);
                MagneticGaugeFixtures.CheckLifecycle((MagneticGaugePage)pages.First(p=>p.Item1=="magnetic-level-gauge").Item2,()=>Arrange(root),Check);
                var align=pages.First(p=>p.Item1=="pipe-alignment").Item2;Check(((RadioButton)align.FindName("SingleScope")).Visibility==Visibility.Collapsed,"隐藏的只移动选中范围保持隐藏");
                host.Content=new UserControl();root.Measure(new Size(560,720));root.Arrange(new Rect(0,0,560,720));root.UpdateLayout();Check(host.Margin==new Thickness(14,4,10,10),"未改支吊架恢复原外边距");Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==36,"未改模块原底栏");
                Console.WriteLine("PASS: "+checks+" 十二页布局/固定操作/消防页签/DPI展示检查。");return 0;
            }catch(Exception e){Console.Error.WriteLine(e);return 1;}
        }
        private static void Seed(UserControl page)
        {
            var summary = page.FindName("SummaryGrid") as DataGrid;
            if(summary != null) summary.ItemsSource = new[] { new StatisticsFixture { Specification="550×160×1200", BoxModel="XMDDG12", ExtinguisherModel="MFZ/ABC4", BoxCount=2, CabinetCount=2, ExtinguisherCount=4, InteriorModelCount=4, ActualExtinguisherCount=4 } };
            foreach(var combo in Children<ComboBox>(page))
            {
                if(combo.Items.Count==0)
                {
                    string label="展示选型";
                    if(combo.Name=="FamilyCombo")label="等边角钢";if(combo.Name=="ProfileCombo")label="L100x100x10";if(combo.Name=="ModeCombo")label="外角点";
                    if(combo.Name=="DirectionCombo")label="顺时针";if(combo.Name=="ConnectionCombo")label="类型1 · 顶面焊接";if(combo.Name=="SideCombo")label="路径左侧";if(combo.Name=="ClosureCombo")label="两端闭合";
                    if(combo.Name=="RatingCombo")label="CL150";if(combo.Name=="ScheduleCombo")label="STD";if(combo.Name=="DnCombo")label="DN100";
                    if(combo.Name=="TypeCombo")label="干粉灭火器";if(combo.Name=="CapacityCombo")label="4 kg";if(combo.Name=="BoxCombo")label="XMDDG12";
                    combo.Items.Add(label);
                }
                if(combo.SelectedIndex<0)combo.SelectedIndex=0;
            }
            var section=page.FindName("ProfilePreview") as UI.ProfilePreviewControl;
            if(section!=null)
            {
                var points=new[]{new Point(0,0),new Point(100,0),new Point(100,10),new Point(10,10),new Point(10,100),new Point(0,100),new Point(0,0)};
                section.Mode=new ModeData{Id="fixture",Label="展示角钢",Segments=Enumerable.Range(0,6).Select(i=>new SegmentData{IsArc=false,X0=points[i].X,Y0=points[i].Y,X1=points[i+1].X,Y1=points[i+1].Y,Xm=0,Ym=0}).ToArray()};
            }
        }
        public sealed class StatisticsFixture
        {
            public string Specification { get; set; } public string BoxModel { get; set; } public string ExtinguisherModel { get; set; }
            public int BoxCount { get; set; } public int CabinetCount { get; set; } public int ExtinguisherCount { get; set; } public int InteriorModelCount { get; set; } public int ActualExtinguisherCount { get; set; }
        }
        private static void Arrange(FrameworkElement root){root.Measure(new Size(400,880));root.Arrange(new Rect(0,0,400,880));root.UpdateLayout();root.Dispatcher.Invoke(()=>{},DispatcherPriority.Background);root.UpdateLayout();}
        private static void Save(FrameworkElement root,string path){var bmp=new RenderTargetBitmap(400,880,96,96,PixelFormats.Pbgra32);bmp.Render(root);var png=new PngBitmapEncoder();png.Frames.Add(BitmapFrame.Create(bmp));using(var file=File.Create(path))png.Save(file);}
        private static System.Collections.Generic.IEnumerable<T> Children<T>(DependencyObject parent)where T:DependencyObject{if(parent is T)yield return (T)parent;for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++)foreach(var child in Children<T>(VisualTreeHelper.GetChild(parent,i)))yield return child;}
        private static UserControl Load(string path){var doc=XDocument.Load(path);XNamespace x="http://schemas.microsoft.com/winfx/2006/xaml";doc.Root.Attribute(x+"Class").Remove();doc.Root.Attribute(x+"ClassModifier").Remove();foreach(var e in doc.Descendants()){foreach(var a in e.Attributes().Where(a=>a.Name.LocalName=="Click").ToArray())a.Remove();if(e.Name.LocalName=="ResourceDictionary"&&e.Attribute("Source")!=null)e.Attribute("Source").Value=new Uri(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path),e.Attribute("Source").Value))).AbsoluteUri;}using(var reader=doc.CreateReader())return (UserControl)XamlReader.Load(reader);}
    }
}
