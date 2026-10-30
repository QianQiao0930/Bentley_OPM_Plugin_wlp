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
    CheckPreferences();HomePreferenceFixture.Seed();var page=new HomePage();NativePanelLayout.Apply(page);
    var root=LoadWorkspace(Path.Combine(project,"UI","WorkspaceView.xaml"));
    ((FrameworkElement)root.FindName("HeaderRow")).Visibility=Visibility.Collapsed;((RowDefinition)root.FindName("HeaderRowDef")).MinHeight=0;
    ((ContentControl)root.FindName("PageHost")).Content=page;
    page.SelectionChanged+=selected=>((Button)root.FindName("HomeEnterButton")).IsEnabled=selected;
    page.StatusRequested+=(text,error)=>((TextBlock)root.FindName("StatusText")).Text=text;
    Arrange(root,400,880);
    Check(((TextBlock)page.FindName("TotalText")).Text=="35","真实模块数量");
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
    HomePreferenceFixture.Reload();Check(((ToggleButton)new HomePage().FindName("CompactToggle")).IsChecked==true,"重新加载磁盘偏好恢复简约模式");
    Click(page,"SupportTab");Arrange(root,400,880);Check(((FrameworkElement)page.FindName("ModelingSection")).Visibility==Visibility.Collapsed,"分类过滤");
    Save(root,Path.Combine(output,"home-support-400-880.png"),400,880);
    Click(page,"StatsTab");Arrange(root,400,880);
    var queryList=(ItemsControl)page.FindName("StatsList");
    Check(queryList.Items.Count==3,"查询分类包含三个入口");
    search.Text="直线坐标";Arrange(root,400,880);Check(queryList.Items.Count==1,"直线坐标模块可搜索");
    Descendant<Button>(queryList.ItemContainerGenerator.ContainerFromIndex(0)).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
    requested=null;page.EnterSelected();Check(requested=="line-coordinates","直线坐标导航PageId");
    Save(root,Path.Combine(output,"home-line-coordinates-400-880.png"),400,880);search.Clear();
    Click(page,"FavTab");Arrange(root,400,880);Check(((ItemsControl)page.FindName("SupportList")).Items.Count==1,"星级收藏过滤");
    Click(page,"AllTab");Click(page,"DetailToggle");Click(page,"FrequentSort");Arrange(root,400,880);Check(page.ShowRanks,"频次模式显示排行");Check(Descendants<Border>(((ItemsControl)page.FindName("ModelingList")).ItemContainerGenerator.ContainerFromIndex(0)).First(border=>border.Name=="RankBadge").Visibility==Visibility.Visible,"频次卡片真实排行可见");Save(root,Path.Combine(output,"home-frequency-400-880.png"),400,880);
    Click(page,"NameSort");Arrange(root,400,880);Check(((ComboBox)page.FindName("SortBox")).SelectedIndex==3,"名称排序UI");
    CheckRecent(page,root,output);NativePanelLayoutChecks.Verify(root,page,Check);
    Arrange(root,400,600);Save(root,Path.Combine(output,"home-native-panel-400-600.png"),400,600);Arrange(root,400,880);
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
  private static void CheckPreferences()
  {
   Check(HomePreferences.FilePath.StartsWith(AppDomain.CurrentDomain.BaseDirectory,StringComparison.OrdinalIgnoreCase),"偏好检查必须使用隔离路径");
   HomePreferenceFixture.Write("{\"Version\":1,\"Features\":{\"legacy-module\":{\"Stars\":4,\"TotalUseCount\":17}}}");
   Check(!HomePreferences.ReadView().Compact&&HomePreferences.ReadView().PinStars,"旧偏好缺省正常模式和星标置顶");
   HomePreferences.SaveView(true,1,HomeCategories.Support,false);HomePreferenceFixture.Reload();
   var view=HomePreferences.ReadView();Check(view.Compact&&view.SortMode==1&&view.CategoryTab==HomeCategories.Support&&!view.PinStars,"四项选择真实写盘重载");
   Check(HomePreferences.RecordFor("legacy-module").Stars==4&&HomePreferences.RecordFor("legacy-module").TotalUseCount==17,"保存界面选择保留旧模块星标和统计");
   HomePreferences.Reset();HomePreferenceFixture.Reload();Check(HomePreferences.ReadView().Compact&&HomePreferences.RecordFor("legacy-module")==null,"重置统计保留显示模式");
   HomePreferenceFixture.Write("{\"View\":{\"Compact\":true,\"SortMode\":99,\"CategoryTab\":\"obsolete\"},\"Features\":null}");
   view=HomePreferences.ReadView();Check(view.Compact&&view.SortMode==0&&view.CategoryTab=="all"&&view.PinStars,"非法排序和分类回落，缺省置顶开启");
   foreach(string json in new[]{"{\"View\":null}","null","broken json"})
   {HomePreferenceFixture.Write(json);view=HomePreferences.ReadView();Check(!view.Compact&&view.SortMode==0&&view.CategoryTab=="all"&&view.PinStars,"空或损坏偏好容错 "+json);}
  }
  private static void CheckRecent(HomePage page,FrameworkElement root,string output)
  {
   Click(page,"RecentSort");Arrange(root,400,880);
   var list=(ItemsControl)page.FindName("SortedList");
   Check(list.Items.Count==35,"最近列表包含全部可用模块");
   Check(list.Items.Cast<HomeCardItem>().Select(item=>item.PageId).Distinct().Count()==35,"最近列表每模块仅出现一次");
   foreach(string name in new[]{"RecentSection","ModelingSection","SupportSection","StatsSection","PlannedSection"})
    Check(((FrameworkElement)page.FindName(name)).Visibility==Visibility.Collapsed,"最近模式隐藏旧分区 "+name);
   var ids=list.Items.Cast<HomeCardItem>().Select(item=>item.PageId).ToArray();
   Check(Array.IndexOf(ids,"component-properties")<Array.IndexOf(ids,"tank-manhole")&&Array.IndexOf(ids,"tank-manhole")<Array.IndexOf(ids,"q1-small-pipe-support"),"查询、建模、支吊架按时间交叉排列");
   Check(ids[0]=="pipe-clamp","全局最近保留星标置顶规则");
   var pin=(ToggleButton)page.FindName("PinToggle");pin.IsChecked=false;Click(page,"PinToggle");
   HomePreferences.RecordFor("tank-manhole").LastUsedUtc=DateTime.UtcNow.ToString("o");page.Refresh();Arrange(root,400,880);
   Check(((HomeCardItem)list.Items[0]).PageId=="tank-manhole","关闭置顶后严格按最近时间排列");
   Click(page,"CompactToggle");Arrange(root,400,880);
   Check(list.ItemTemplate==page.FindResource("CompactCardTemplate"),"全局列表支持简约模式");
   Save(root,Path.Combine(output,"home-recent-compact-400-880.png"),400,880);
   Click(page,"SupportTab");Arrange(root,400,880);Check(list.Items.Count==18,"全局最近尊重显式分类筛选");
   HomePreferenceFixture.Reload();var restored=new HomePage();
   Check(((ToggleButton)restored.FindName("CompactToggle")).IsChecked==true&&((ToggleButton)restored.FindName("RecentSort")).IsChecked==true&&((ToggleButton)restored.FindName("SupportTab")).IsChecked==true&&((ToggleButton)restored.FindName("PinToggle")).IsChecked==false,"重新创建页面恢复所有开关");
   Click(page,"AllTab");var search=(TextBox)page.FindName("SearchBox");search.Text="Q2";Arrange(root,400,880);Check(list.Items.Count==1,"全局最近支持编号搜索");search.Clear();
   Click(page,"DetailToggle");Arrange(root,400,880);Save(root,Path.Combine(output,"home-recent-detail-400-880.png"),400,880);
   var card=Descendants<Button>(list.ItemContainerGenerator.ContainerFromIndex(0)).First(button=>button.Name=="CardFace");card.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
   string requested=null;page.FeatureRequested+=id=>requested=id;page.EnterSelected();Check(requested==((HomeCardItem)list.Items[0]).PageId,"全局列表仍可选择进入");
   var reset=Descendants<Button>(page).First(button=>button.ToolTip!=null&&button.ToolTip.ToString().StartsWith("重置筛选与排序"));reset.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));Arrange(root,400,880);
   HomePreferenceFixture.Reload();restored=new HomePage();Check(((ToggleButton)restored.FindName("AllTab")).IsChecked==true&&((ToggleButton)restored.FindName("DefaultSort")).IsChecked==true&&((ToggleButton)restored.FindName("PinToggle")).IsChecked==true,"重置筛选后保存默认选择");
   Check(((FrameworkElement)page.FindName("SortedSection")).Visibility==Visibility.Collapsed&&((ItemsControl)page.FindName("ModelingList")).Items.Count==14,"切回默认恢复分类");
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
