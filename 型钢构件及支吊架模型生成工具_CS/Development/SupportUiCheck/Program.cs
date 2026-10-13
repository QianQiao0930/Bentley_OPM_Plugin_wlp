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
                string project=Path.GetFullPath(args[0]),output=Path.Combine(project,"Development/SupportUiCheck/previews");Directory.CreateDirectory(output);
                var root=Load(Path.Combine(project,"UI/WorkspaceView.xaml"));((FrameworkElement)root.FindName("HeaderRow")).Visibility=Visibility.Collapsed;((RowDefinition)root.FindName("HeaderRowDef")).MinHeight=0;
                var host=(ContentControl)root.FindName("PageHost");
                var pages=new[]{Tuple.Create("pipe-clamp",(UserControl)new PipeClampPage()),Tuple.Create("q1-small-pipe-support",(UserControl)new Q1SupportPage()),Tuple.Create("elbow-trunnion",(UserControl)new ElbowTrunnionPage()),Tuple.Create("g2-anchor-plate",(UserControl)new G2AnchorPage()),Tuple.Create("vertical-pipe-support",(UserControl)new VerticalPipeSupportPage()),Tuple.Create("cold-riser-guide",(UserControl)new ColdRiserGuidePage()),Tuple.Create("n1-cantilever",(UserControl)new N1CantileverPage()),Tuple.Create("n2-cantilever",(UserControl)new N2CantileverPage()),Tuple.Create("n3-single-bracket",(UserControl)new BracketPage(false)),Tuple.Create("n4-double-bracket",(UserControl)new BracketPage(true)),Tuple.Create("d2-cantilever",(UserControl)new D2CantileverPage()),Tuple.Create("triangle-bracket",(UserControl)new TriangleBracketPage()),Tuple.Create("l-bracket",(UserControl)new LBracketPage()),Tuple.Create("portal-frame",(UserControl)new PortalFramePage()),Tuple.Create("t-frame",(UserControl)new TFramePage()),Tuple.Create("pad-plate",(UserControl)new PadPlatePage()),Tuple.Create("n8-connection-plate",(UserControl)new N8Page())};
                foreach(var pair in pages)
                {
                    var page=pair.Item2;host.Content=page;Arrange(root);Seed(page);Arrange(root);
                    Check(page.ActualWidth==398,"400外框 "+pair.Item1);Check(host.Margin.Left==0,"原型外边距 "+pair.Item1);Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==46,"46底栏 "+pair.Item1);
                    if(pair.Item1!="q1-small-pipe-support"){var chrome=Children<PrototypeChrome>(page).Single();Check(chrome.ActualHeight==95,"32+63标题 "+pair.Item1);} else Check(((FrameworkElement)page.FindName("ModuleHeader")).ActualHeight==63,"Q1/Q2原模块头");
                    Save(root,Path.Combine(output,pair.Item1+"-400-880.png"));
                    var confirm=page.FindName("ConfirmButton") as Button;
                    if(confirm!=null){var point=confirm.TranslatePoint(new Point(),root);Check(point.Y+confirm.ActualHeight<=833.1,"确认初始可见 "+pair.Item1);Check(point.X+confirm.ActualWidth<=399.1,"确认右边界 "+pair.Item1);}
                    var scroll=Children<ScrollViewer>(page).FirstOrDefault(s=>s.VerticalScrollBarVisibility==ScrollBarVisibility.Auto&&s.HorizontalScrollBarVisibility==ScrollBarVisibility.Disabled);
                    if(scroll!=null){double y=confirm==null?0:confirm.TranslatePoint(new Point(),root).Y;scroll.ScrollToBottom();Arrange(root);if(confirm!=null)Check(Math.Abs(confirm.TranslatePoint(new Point(),root).Y-y)<.01,"滚动不移动操作区 "+pair.Item1);Save(root,Path.Combine(output,pair.Item1+"-parameters-bottom.png"));scroll.ScrollToTop();Arrange(root);}
                    foreach(var button in Children<Button>(page).Where(b=>b.IsVisible&&b.ActualWidth>30)){var pos=button.TranslatePoint(new Point(),root);Check(pos.X+button.ActualWidth<=400.1,"操作按钮不超右边界 "+pair.Item1+button.Content);}
                    var tabs=page.FindName("PageTabs") as TabControl;
                    if(tabs!=null){tabs.SelectedIndex=1;Arrange(root);Check(((DataGrid)page.FindName("SummaryGrid")).Columns.Count==5,"消防全部统计列 "+pair.Item1); Check(((DataGrid)page.FindName("SummaryGrid")).Columns.Sum(c=>c.MinWidth)>((DataGrid)page.FindName("SummaryGrid")).ActualWidth,"统计列保持可读宽度并横向滚动 "+pair.Item1);Save(root,Path.Combine(output,pair.Item1+"-statistics-400-880.png"));tabs.SelectedIndex=0;Arrange(root);}
                    string[] variants=pair.Item1=="pipe-clamp"?new[]{"A1Panel","A2Panel","A22Panel","A24Panel","E1Panel","K1Panel","T4Panel","L2Panel","U3Panel"}:pair.Item1=="vertical-pipe-support"?new[]{"TrunnionPanel","EarPlatePanel"}:new string[0];
                    foreach(string variant in variants)
                    {
                        ShowPanels(page,variants,variant);Arrange(root);if(confirm!=null){var cp=confirm.TranslatePoint(new Point(),root);Check(cp.Y+confirm.ActualHeight<=833.1,"分型确认可见 "+variant);}
                        if(variant=="U3Panel")
                        {
                            var kind=(ComboBox)page.FindName("KindCombo");kind.Items.Clear();kind.Items.Add("U3 带承重块的U形螺栓（1/2″~6″）");kind.SelectedIndex=0;Arrange(root);
                        }
                        Save(root,Path.Combine(output,pair.Item1+"-"+variant+".png"));
                        if(variant=="U3Panel"&&scroll!=null)
                        {
                            double before=confirm.TranslatePoint(new Point(),root).Y;
                            scroll.ScrollToBottom();Arrange(root);
                            Check(Math.Abs(confirm.TranslatePoint(new Point(),root).Y-before)<.01,"U3参数滚动不移动确认按钮");
                            Save(root,Path.Combine(output,"pipe-clamp-U3-bottom.png"));
                            scroll.ScrollToTop();Arrange(root);
                        }
                    }
                    if(pair.Item1=="q1-small-pipe-support")
                    { ((ComboBox)page.FindName("SeriesCombo")).SelectedIndex=1;((ComboBox)page.FindName("TypeCombo")).SelectedIndex=3;Arrange(root);Check(((FrameworkElement)page.FindName("AngleButton")).Visibility==Visibility.Visible,"Q2类型4保留角度入口");Save(root,Path.Combine(output,"q2-type4.png")); }
                    if(page is BracketPage)
                    {
                        bool isDouble=pair.Item1=="n4-double-bracket";
                        var chrome=Children<PrototypeChrome>(page).Single();Check(chrome.Code==(isDouble?"N4":"N3"),"共享N3/N4动态代号");
                        Check(((FrameworkElement)page.FindName("SinglePreweldPanel")).Visibility==
                            (isDouble?Visibility.Collapsed:Visibility.Visible),"仅N3显示单架预焊件参数");
                        Check(((TextBlock)page.FindName("HeightLabelText")).Text==
                            "H：两块连接板中心距（mm）","N3/N4标注H中心距");
                        if(!isDouble)
                        {
                            var toggle=(CheckBox)page.FindName("N3ShowPreweldCheck");
                            var input=(TextBox)page.FindName("N3PreweldText");
                            Check(toggle.IsChecked!=true&&input.Text=="100"&&!input.IsEnabled,"N3占位默认关闭、记忆长度100");
                            toggle.IsChecked=true;Arrange(root);
                            Check(input.IsEnabled,"N3勾选可输入D");
                            ((TextBlock)page.FindName("EText")).Text="支架 L = 辅助线 1200 − 占位 D 100 = 1100 mm\n横担长度 1084 mm − H 390 mm = E 694 mm（最小 150 mm）";
                            scroll.ScrollToBottom();Arrange(root);
                            Check(confirm.TranslatePoint(new Point(),root).Y+confirm.ActualHeight<=833.1,"N3占位参数展开确认仍可见");
                            Save(root,Path.Combine(output,"n3-preweld-enabled.png"));
                            toggle.IsChecked=false;scroll.ScrollToTop();Arrange(root);
                        }
                    }
                    foreach(double scale in new[]{1d,1.25,1.5,2}){var bmp=new RenderTargetBitmap((int)(400*scale),(int)(880*scale),96*scale,96*scale,PixelFormats.Pbgra32);bmp.Render(root);Check(bmp.PixelHeight==(int)(880*scale),"DPI "+pair.Item1+scale);}
                    Console.WriteLine(pair.Item1+": 400x880, original controls and fixed actions rendered.");
                }
                host.Content=new UserControl();root.Measure(new Size(560,720));root.Arrange(new Rect(0,0,560,720));root.UpdateLayout();Check(host.Margin==new Thickness(14,4,10,10),"未改支吊架恢复原外边距");Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==36,"未改模块原底栏");
                Console.WriteLine("PASS: "+checks+" 17个支吊架入口布局/固定操作/分型/DPI展示检查。");return 0;
            }catch(Exception e){Console.Error.WriteLine(e);return 1;}
        }
        private static void Seed(UserControl page)
        {
            foreach(var combo in Children<ComboBox>(page))
            {
                if(combo.Items.Count==0)
                {
                    string label="A · 子项 A";
                    if(combo.Name.Contains("Dn") || combo.Name.Contains("DN"))label="DN100";
                    if(combo.Name=="KindCombo")label=page is PipeClampPage?"A1 · U型管卡":page is VerticalPipeSupportPage?"F6 · 单耳轴":page is ColdRiserGuidePage?"类型1 · 带构件A":"类型1";
                    if(combo.Name=="SeriesCombo")label="L7 · 保冷立管导向";
                    if(combo.Name=="MountCombo")label="安装面 · 竖直";
                    if(combo.Name=="MaterialCombo")label="C1 · 碳钢";
                    if(combo.Name=="SubtypeCombo" || combo.Name=="VariantCombo")label="A";
                    if(combo.Name=="EndTypeCombo")label="A · 方形端板";
                    if(combo.Name=="FamilyCombo")label="等边角钢";if(combo.Name=="ProfileCombo")label="L100x100x10";if(combo.Name=="ModeCombo")label="外角点";
                    if(combo.Name=="DirectionCombo")label="顺时针";if(combo.Name=="ConnectionCombo")label="类型1 · 顶面焊接";if(combo.Name=="SideCombo")label="路径左侧";if(combo.Name=="ClosureCombo")label="两端闭合";
                    if(combo.Name=="RatingCombo")label="CL150";if(combo.Name=="ScheduleCombo")label="STD";if(combo.Name=="DnCombo")label="DN100";
                    if(combo.Name=="TypeCombo")label="类型1";if(combo.Name=="CapacityCombo")label="4 kg";if(combo.Name=="BoxCombo")label="XMDDG12";
                    combo.Items.Add(label);
                }
                if(combo.SelectedIndex<0)combo.SelectedIndex=0;
            }
            if(page is BracketPage)
            {
                ((TextBlock)page.FindName("InstructionText")).Text="绘制水平辅助线后点取；修改参数须更新预览。";
                ((TextBlock)page.FindName("PreviewInstructionText")).Text="点取水平辅助线，更新预览后确认；右键结束并取消未确认预览。";
                ((TextBox)page.FindName("HeightText")).Text="500";
                foreach(string name in new[]{"L2Text","L3Text","L4Text","EquipmentOdText"}) ((TextBox)page.FindName(name)).Text=name=="EquipmentOdText"?"5000":"1000";
            }
            if(page is PipeClampPage)
            {
                ((ComboBox)page.FindName("U3ItemCombo")).Items.Clear();((ComboBox)page.FindName("U3ItemCombo")).Items.Add("G · 承重/导向 · 两螺母一边一个");((ComboBox)page.FindName("U3ItemCombo")).SelectedIndex=0;
                ((ComboBox)page.FindName("U3MaterialCombo")).Items.Clear();((ComboBox)page.FindName("U3MaterialCombo")).Items.Add("S1 · 不锈钢管 / EPDM · ≤120°C");((ComboBox)page.FindName("U3MaterialCombo")).SelectedIndex=0;
                foreach(string n in new[]{"U3SteelText","U3TopText","U3WallText","U3RubberText"})((TextBox)page.FindName(n)).Text=n=="U3SteelText"?"10":n=="U3TopText"?"25":n=="U3WallText"?"6":"3";
                ((TextBlock)page.FindName("U3SpecText")).Text="U3-G-DN100-S1 / 承重/导向，两螺母一边一个，净间隙3 mm / 承重块100×50×10 / 06Cr19Ni10 / 长边沿立管焊接，焊高6 mm / EPDM3 mm，管温≤120°C";
            }
            if(page is PipeClampPage) ShowPanels(page,new[]{"A1Panel","A2Panel","A22Panel","A24Panel","E1Panel","K1Panel","T4Panel","L2Panel","U3Panel"},"A1Panel");
            if(page is VerticalPipeSupportPage) ShowPanels(page,new[]{"TrunnionPanel","EarPlatePanel"},"TrunnionPanel");
        }
        private static void ShowPanels(UserControl page,string[] names,string visible)
        { foreach(string name in names) { var node=page.FindName(name) as FrameworkElement; if(node!=null)node.Visibility=name==visible?Visibility.Visible:Visibility.Collapsed; } }
        private static void Arrange(FrameworkElement root){root.Measure(new Size(400,880));root.Arrange(new Rect(0,0,400,880));root.UpdateLayout();root.Dispatcher.Invoke(()=>{},DispatcherPriority.Background);root.UpdateLayout();}
        private static void Save(FrameworkElement root,string path){var bmp=new RenderTargetBitmap(400,880,96,96,PixelFormats.Pbgra32);bmp.Render(root);var png=new PngBitmapEncoder();png.Frames.Add(BitmapFrame.Create(bmp));using(var file=File.Create(path))png.Save(file);}
        private static System.Collections.Generic.IEnumerable<T> Children<T>(DependencyObject parent)where T:DependencyObject{if(parent is T)yield return (T)parent;for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++)foreach(var child in Children<T>(VisualTreeHelper.GetChild(parent,i)))yield return child;}
        private static UserControl Load(string path){var doc=XDocument.Load(path);XNamespace x="http://schemas.microsoft.com/winfx/2006/xaml";doc.Root.Attribute(x+"Class").Remove();doc.Root.Attribute(x+"ClassModifier").Remove();foreach(var e in doc.Descendants()){foreach(var a in e.Attributes().Where(a=>a.Name.LocalName=="Click").ToArray())a.Remove();if(e.Name.LocalName=="ResourceDictionary"&&e.Attribute("Source")!=null)e.Attribute("Source").Value=new Uri(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path),e.Attribute("Source").Value))).AbsoluteUri;}using(var reader=doc.CreateReader())return (UserControl)XamlReader.Load(reader);}
    }
}
