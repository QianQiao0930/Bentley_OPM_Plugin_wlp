using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET.Elements;
namespace SteelSectionProbe
{
    internal sealed class LocatedElement {internal double HeightMm=3000;}
    internal static class WallLadderReader
    {
        internal static bool Fail;
        internal static WallLadderSelection Read(LocatedElement located)
        {if(Fail)throw new InvalidOperationException("模拟竖直线拒绝");return new WallLadderSelection { HeightMm=located.HeightMm,BasePointMm=new WallLadderPoint(100,200,300) };}
    }
    internal static class WallLadderLocateTool
    {
        internal static bool IsActive;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static void Begin(){IsActive=true;}
        internal static void End(){if(!IsActive)return;IsActive=false;if(Ended!=null)Ended();}
        internal static void Pick(){if(Picked!=null)Picked(new LocatedElement());}
    }
    internal static class WallLadderBuilder
    {
        internal static bool Fail;
        internal static int Calls;
        internal static Element[] Last;
        internal static Element[] Build(WallLadderPlan p,WallLadderPoint origin)
        {Calls++;if(Fail)throw new InvalidOperationException("模拟圆弧扫掠失败");Last=p.Parameters.CageEnabled?new[]{new Element(),new Element()}:new[]{new Element()};return Last;}
    }
    internal static class WallLadderFixtures
    {
        internal static void CheckLifecycle(WallLadderPage page,Action arrange,Action<bool,string> check)
        {
            var confirm=(Button)page.FindName("ConfirmButton");var update=(Button)page.FindName("UpdateButton");var width=(TextBox)page.FindName("WidthText");var cage=(CheckBox)page.FindName("CageCheck");
            page.OnActivated();Click(page,"开始点取");WallLadderLocateTool.Pick();arrange();
            check(confirm.IsEnabled&&WallLadderBuilder.Last.Length==2&&WallLadderBuilder.Last.All(e=>e.Written),"墙梯点取生成两个块");
            check(((TextBlock)page.FindName("HeightText")).Text=="3000 mm"&&((TextBlock)page.FindName("SpecificationText")).Text.Contains("75×12"),"墙梯读取线高及真实选型");
            var old=WallLadderBuilder.Last;width.Text="420";check(!confirm.IsEnabled&&update.Content.ToString().Contains("●")&&old.All(e=>e.Written),"墙梯参数变化保留旧预览禁止确认");
            WallLadderBuilder.Fail=true;update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(!confirm.IsEnabled&&old.All(e=>e.Written),"墙梯扫掠失败保留旧块");WallLadderBuilder.Fail=false;
            update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(confirm.IsEnabled&&old.All(e=>!e.Written)&&!update.Content.ToString().Contains("●"),"墙梯更新成功清除黑点");
            old=WallLadderBuilder.Last;cage.IsChecked=false;update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(WallLadderBuilder.Last.Length==1&&old.All(e=>!e.Written),"墙梯关闭护笼回收两个旧块");
            var formal=WallLadderBuilder.Last;confirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));Click(page,"取消预览");check(formal.All(e=>e.Written),"墙梯确认后不删正式模型");
            int calls=WallLadderBuilder.Calls;WallLadderLocateTool.Pick();Click(page,"取消预览");arrange();check(WallLadderBuilder.Calls==calls,"墙梯取消阻止队列回调");
            WallLadderReader.Fail=true;WallLadderLocateTool.Pick();arrange();check(WallLadderBuilder.Calls==calls&&!confirm.IsEnabled,"墙梯非法辅助线不建模");WallLadderReader.Fail=false;
            WallLadderLocateTool.Pick();page.OnDeactivated();arrange();check(WallLadderBuilder.Calls==calls&&!WallLadderLocateTool.IsActive,"墙梯退出阻止队列回调");
            page.OnActivated();Click(page,"开始点取");WallLadderLocateTool.Pick();arrange();old=WallLadderBuilder.Last;Click(page,"结束点取");check(old.All(e=>!e.Written)&&!confirm.IsEnabled,"墙梯结束清理预览");
            page.OnWorkspaceClosing();page.OnWorkspaceClosing();check(formal.All(e=>e.Written),"墙梯重复关闭保留正式模型");
        }
        private static void Click(UserControl page,string text){Buttons(page).Single(b=>b.Content.ToString()==text).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));}
        private static System.Collections.Generic.IEnumerable<Button> Buttons(DependencyObject p)
        {if(p is Button)yield return (Button)p;for(int i=0;i<System.Windows.Media.VisualTreeHelper.GetChildrenCount(p);i++)foreach(var b in Buttons(System.Windows.Media.VisualTreeHelper.GetChild(p,i)))yield return b;}
    }
}
