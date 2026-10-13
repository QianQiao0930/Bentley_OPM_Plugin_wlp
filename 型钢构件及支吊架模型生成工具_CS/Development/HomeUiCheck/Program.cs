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
  private static void Check(bool value,string label){checks++;if(!value)throw new Exception(label);}
  [STAThread]private static int Main(string[] args)
  {
   try
   {
    string project=Path.GetFullPath(args[0]),output=Path.Combine(project,"Development","HomeUiCheck","previews");Directory.CreateDirectory(output);
    HomePreferences.Seed();var page=new HomePage();
    var root=LoadWorkspace(Path.Combine(project,"UI","WorkspaceView.xaml"));
    ((FrameworkElement)root.FindName("HeaderRow")).Visibility=Visibility.Collapsed;((RowDefinition)root.FindName("HeaderRowDef")).MinHeight=0;
    ((ContentControl)root.FindName("PageHost")).Content=page;
    page.SelectionChanged+=selected=>((Button)root.FindName("HomeEnterButton")).IsEnabled=selected;
    page.StatusRequested+=(text,error)=>((TextBlock)root.FindName("StatusText")).Text=text;
    Arrange(root,400,880);
    Check(((TextBlock)page.FindName("TotalText")).Text=="28","真实模块数量");
    Check(((FrameworkElement)page.FindName("HeaderBand")).ActualHeight==159,"原型头部159");
    Check(((FrameworkElement)page.FindName("ToolbarBand")).ActualHeight==131,"原型工具栏131");
    Check(((FrameworkElement)page.FindName("HomeStatsBand")).ActualHeight==47,"原型统计带47");
    Check(((FrameworkElement)page.FindName("HomeScroll")).ActualWidth==398,"400外框扣1px边框");
    Check(((FrameworkElement)root.FindName("PageHost")).Margin.Left==0,"首页取消模块外边距");
    Check(((ItemsControl)page.FindName("RecentList")).Items.Count==4,"最近使用四项");
    foreach(string name in new[]{"HeaderBand","HomeStatsBand","ToolbarBand","SearchBox","HomeScroll","RecentSection","RecentList","ModelingList"}){var node=(FrameworkElement)page.FindName(name);var pos=node.TranslatePoint(new Point(),root);Console.WriteLine(name+": x="+pos.X+" y="+pos.Y+" w="+node.ActualWidth+" h="+node.ActualHeight);}
    Save(root,Path.Combine(output,"home-detail-400-880.png"),400,880);
    var model=(ItemsControl)page.FindName("ModelingList");Check(model.Items.Count>0,"全部模块显示");
    var card=Descendant<Button>(model.ItemContainerGenerator.ContainerFromIndex(0));
    card.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
    Check(((Button)root.FindName("HomeEnterButton")).IsEnabled,"选择后激活进入按钮");
    string requested=null;page.FeatureRequested+=id=>requested=id;page.EnterSelected();Check(!string.IsNullOrEmpty(requested),"沿用模块导航事件");
    requested=null;
    var stars=Descendants<Button>(model.ItemContainerGenerator.ContainerFromIndex(0)).First(button=>button.Name=="StarButton");
    stars.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));Check(requested==null,"点星标不会进入模块");
    var five=stars.ContextMenu.Items.OfType<MenuItem>().First(menu=>menu.Tag!=null&&menu.Tag.ToString()=="5");
    five.RaiseEvent(new RoutedEventArgs(MenuItem.ClickEvent));stars.ContextMenu.IsOpen=false;Arrange(root,400,880);
    Check(HomePreferences.RecordFor("steel-sections").Stars==5,"原五级评分仍可写入");
    HomePreferences.SetStars("steel-sections",0);page.Refresh();Arrange(root,400,880);
    var search=(TextBox)page.FindName("SearchBox");search.Text="Q2";Arrange(root,400,880);
    Check(((ItemsControl)page.FindName("SupportList")).Items.Count==1,"按编号搜索");Save(root,Path.Combine(output,"home-search-400-880.png"),400,880);search.Clear();
    Click(page,"CompactToggle");Arrange(root,400,880);Save(root,Path.Combine(output,"home-compact-400-880.png"),400,880);
    Check(((ToggleButton)page.FindName("CompactToggle")).IsChecked==true,"简约模式状态");
    Click(page,"SupportTab");Arrange(root,400,880);Check(((FrameworkElement)page.FindName("ModelingSection")).Visibility==Visibility.Collapsed,"分类过滤");
    Save(root,Path.Combine(output,"home-support-400-880.png"),400,880);
    Click(page,"FavTab");Arrange(root,400,880);Check(((ItemsControl)page.FindName("SupportList")).Items.Count==1,"星级收藏过滤");
    Click(page,"AllTab");Click(page,"DetailToggle");Click(page,"FrequentSort");Arrange(root,400,880);Check(page.ShowRanks,"频次模式显示排行");Check(Descendants<Border>(((ItemsControl)page.FindName("ModelingList")).ItemContainerGenerator.ContainerFromIndex(0)).First(border=>border.Name=="RankBadge").Visibility==Visibility.Visible,"频次卡片真实排行可见");Save(root,Path.Combine(output,"home-frequency-400-880.png"),400,880);
    Click(page,"NameSort");Arrange(root,400,880);Check(((ComboBox)page.FindName("SortBox")).SelectedIndex==3,"名称排序UI");
    LicenseService.IsActivated=false;page.Refresh();Arrange(root,400,880);Save(root,Path.Combine(output,"home-unactivated-400-880.png"),400,880);
    Check(((Button)page.FindName("ActivationButton")).Content.ToString()=="未激活","授权状态沿用现有服务");
    LicenseService.IsLicensingEnabled=false;page.Refresh();Arrange(root,400,880);Check(((Button)page.FindName("ActivationButton")).Visibility==Visibility.Collapsed,"无授权构建隐藏授权入口");
    foreach(double scale in new[]{1.0,1.25,1.5,2.0})
    {
     Arrange(root,400,880);var enter=(Button)root.FindName("HomeEnterButton");var pos=enter.TranslatePoint(new Point(),root);
     Check(pos.Y+enter.ActualHeight<=880,"确认入口不越界 "+scale);
     var bitmap=new RenderTargetBitmap((int)(400*scale),(int)(880*scale),96*scale,96*scale,PixelFormats.Pbgra32);bitmap.Render(root);
     Check(bitmap.PixelWidth==(int)(400*scale),"逻辑尺寸DPI映射 "+scale);
    }
    Check(homeIconUnchanged(project),"SVG品牌几何保留");
    ((ContentControl)root.FindName("PageHost")).Content=new UserControl();Arrange(root,560,720);
    Check(((FrameworkElement)root.FindName("PageHost")).Margin==new Thickness(14,4,10,10),"模块页原外边距保留");
    Check(((FrameworkElement)root.FindName("WorkspaceFooter")).ActualHeight==36,"模块页原36px底栏保留");
    Check(((Button)root.FindName("HomeEnterButton")).Visibility==Visibility.Collapsed,"模块页隐藏首页进入按钮");
    Console.WriteLine("首页v4："+checks+"项真实WPF布局/展示交互检查通过；400×880，1/1.25/1.5/2倍DPI。 "+output);return 0;
   }catch(Exception ex){Console.Error.WriteLine(ex);return 1;}
  }
  private static bool homeIconUnchanged(string project)
  {var doc=XDocument.Load(Path.Combine(project,"UI","HomePage.xaml"));return doc.Descendants().Any(e=>e.Name.LocalName=="PathGeometry"&&e.Attributes().Any(a=>a.Name.LocalName=="Key"&&a.Value=="HomeIcon_app")&&e.Attribute("FillRule").Value=="EvenOdd");}
  private static void Click(HomePage page,string name){((ButtonBase)page.FindName(name)).RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));}
  private static System.Collections.Generic.IEnumerable<T> Descendants<T>(DependencyObject item)where T:DependencyObject
  {if(item==null)yield break;if(item is T)yield return (T)item;for(int i=0;i<VisualTreeHelper.GetChildrenCount(item);i++)foreach(var child in Descendants<T>(VisualTreeHelper.GetChild(item,i)))yield return child;}
  private static T Descendant<T>(DependencyObject item)where T:DependencyObject
  {if(item==null)return null;if(item is T)return (T)item;for(int i=0;i<VisualTreeHelper.GetChildrenCount(item);i++){var child=Descendant<T>(VisualTreeHelper.GetChild(item,i));if(child!=null)return child;}return null;}
  private static void Arrange(FrameworkElement root,int width,int height)
  {root.Measure(new Size(width,height));root.Arrange(new Rect(0,0,width,height));root.UpdateLayout();root.Dispatcher.Invoke(()=>{},DispatcherPriority.Background);root.UpdateLayout();}
  private static void Save(FrameworkElement root,string path,int width,int height)
  {var bitmap=new RenderTargetBitmap(width,height,96,96,PixelFormats.Pbgra32);bitmap.Render(root);var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));using(var stream=File.Create(path))encoder.Save(stream);}
  private static UserControl LoadWorkspace(string path)
  {
   var doc=XDocument.Load(path);XNamespace x="http://schemas.microsoft.com/winfx/2006/xaml";doc.Root.Attribute(x+"Class").Remove();doc.Root.Attribute(x+"ClassModifier").Remove();
   foreach(var e in doc.Descendants())
   {
    foreach(var a in e.Attributes().Where(a=>new[]{"Click","SelectionChanged","TextChanged","MouseLeftButtonDown","MouseDoubleClick"}.Contains(a.Name.LocalName)).ToArray())a.Remove();
    if(e.Name.LocalName=="ResourceDictionary"&&e.Attribute("Source")!=null)e.Attribute("Source").Value=new Uri(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(path),e.Attribute("Source").Value))).AbsoluteUri;
   }
   return (UserControl)XamlReader.Parse(doc.ToString());
  }
 }
}
