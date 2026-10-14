using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
namespace SteelSectionProbe
{
    internal static class MagneticGaugePlacementTool
    {
        internal static bool IsActive;
        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;
        internal static void Begin(){IsActive=true;}
        internal static void End(){if(!IsActive)return;IsActive=false;if(Ended!=null)Ended();}
        internal static void Pick(){if(Picked!=null)Picked(new DPoint3d(100,200,300));}
    }
    internal static class MagneticGaugeBuilder
    {
        internal static bool Fail;
        internal static int Calls;
        internal static Element Last;
        internal static Element Build(MagneticGaugePlan p,DPoint3d origin)
        {Calls++;if(Fail)throw new InvalidOperationException("模拟液位计构造失败");Last=new Element();return Last;}
    }
    internal static class MagneticGaugeFixtures
    {
        internal static void CheckLifecycle(MagneticGaugePage page,Action arrange,Action<bool,string> check)
        {
            var confirm=(Button)page.FindName("ConfirmButton");var update=(Button)page.FindName("UpdateButton");var spacing=(TextBox)page.FindName("SpacingText");
            check(((TextBlock)page.FindName("SpecificationText")).Text.Contains("365"),"磁翻板真实默认摘要");
            page.OnActivated();Click(page,"开始点取");MagneticGaugePlacementTool.Pick();arrange();check(confirm.IsEnabled&&MagneticGaugeBuilder.Last.Written,"液位计点取预览");
            var old=MagneticGaugeBuilder.Last;spacing.Text="1500";check(!confirm.IsEnabled&&update.Content.ToString().Contains("●")&&old.Written,"液位计参数失效与黑点");
            MagneticGaugeBuilder.Fail=true;update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(!confirm.IsEnabled&&old.Written,"液位计构造失败保留预览");MagneticGaugeBuilder.Fail=false;
            update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(confirm.IsEnabled&&!old.Written&&!update.Content.ToString().Contains("●"),"液位计更新替换成功");
            old=MagneticGaugeBuilder.Last;int calls=MagneticGaugeBuilder.Calls;spacing.Text="349";update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));check(!confirm.IsEnabled&&old.Written&&MagneticGaugeBuilder.Calls==calls,"L1越界阻止建模与确认");
            spacing.Text="1400";update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));var formal=MagneticGaugeBuilder.Last;confirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));Click(page,"取消预览");check(formal.Written,"液位计确认后保留块");
            calls=MagneticGaugeBuilder.Calls;MagneticGaugePlacementTool.Pick();Click(page,"取消预览");arrange();check(calls==MagneticGaugeBuilder.Calls,"液位计取消阻止延迟回调");
            MagneticGaugePlacementTool.Pick();page.OnDeactivated();arrange();check(calls==MagneticGaugeBuilder.Calls&&!MagneticGaugePlacementTool.IsActive,"液位计离开阻止队列回调");
            page.OnActivated();Click(page,"开始点取");MagneticGaugePlacementTool.Pick();arrange();old=MagneticGaugeBuilder.Last;Click(page,"结束点取");check(!old.Written&&!confirm.IsEnabled,"液位计结束清理未确认块");
            page.OnWorkspaceClosing();page.OnWorkspaceClosing();check(formal.Written,"液位计重复关闭保留正式块");
        }
        private static void Click(UserControl page,string text){Buttons(page).Single(b=>b.Content.ToString()==text).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));}
        private static System.Collections.Generic.IEnumerable<Button> Buttons(DependencyObject p)
        {if(p is Button)yield return (Button)p;for(int i=0;i<System.Windows.Media.VisualTreeHelper.GetChildrenCount(p);i++)foreach(var b in Buttons(System.Windows.Media.VisualTreeHelper.GetChild(p,i)))yield return b;}
    }
}
