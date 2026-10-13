using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace Bentley.GeometryNET
{
    internal struct DPoint3d
    {
        internal double X, Y, Z;
        internal DPoint3d(double x, double y, double z) { X = x; Y = y; Z = z; }
    }
}
namespace SteelSectionProbe
{
    // Isolated page fixtures: no DGN, native geometry or user-preference file access.
    internal static class PageLastInput
    {
        internal static void Restore(UserControl page, string id, params string[] fields) { }
        internal static void Save(UserControl page, string id, params string[] fields) { }
    }
    internal static class TankLadderPlacementTool
    {
        internal static bool IsActive;
        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;
        internal static void Begin() { IsActive = true; }
        internal static void End() { if (!IsActive) return; IsActive = false; if (Ended != null) Ended(); }
        internal static void Pick() { if (Picked != null) Picked(new DPoint3d(100, 200, 300)); }
    }
    internal static class TankLadderBuilder
    {
        internal static bool Fail;
        internal static int Calls;
        internal static Element Last;
        internal static Element Build(TankLadderPlan plan, DPoint3d origin)
        {
            Calls++;
            if (Fail) throw new InvalidOperationException("模拟原生构造失败");
            Last = new Element(); return Last;
        }
    }
    internal static class TankLadderFixtures
    {
        internal static void CheckLifecycle(TankLadderPage page, Action arrange, Action<bool, string> check)
        {
            var confirm = (Button)page.FindName("ConfirmButton");
            var update = (Button)page.FindName("UpdateButton");
            var height = (TextBox)page.FindName("HeightText");
            check(((TextBlock)page.FindName("SpecificationText")).Text.Contains("17"), "爬梯真实参数摘要");
            page.OnActivated();
            Click(page, "开始点取"); TankLadderPlacementTool.Pick(); arrange();
            check(confirm.IsEnabled && TankLadderBuilder.Last.Written, "点取后生成可确认预览");
            var old = TankLadderBuilder.Last; height.Text = "2100";
            check(!confirm.IsEnabled && update.Content.ToString().Contains("●") && old.Written, "参数变化禁止确认且保留旧预览");
            TankLadderBuilder.Fail = true; update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            check(!confirm.IsEnabled && old.Written && update.Content.ToString().Contains("●"), "更新失败保留预览和黑点");
            TankLadderBuilder.Fail = false; update.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            check(confirm.IsEnabled && !old.Written && !update.Content.ToString().Contains("●"), "更新成功替换旧预览并清除黑点");
            var formal = TankLadderBuilder.Last; confirm.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            Click(page, "取消预览"); check(formal.Written && !confirm.IsEnabled, "确认后取消不删正式模型");
            int calls = TankLadderBuilder.Calls;
            TankLadderPlacementTool.Pick(); Click(page, "取消预览"); arrange();
            check(TankLadderBuilder.Calls == calls, "取消阻止延迟点取生成");
            TankLadderPlacementTool.Pick(); page.OnDeactivated(); arrange();
            check(TankLadderBuilder.Calls == calls && !TankLadderPlacementTool.IsActive, "退出阻止延迟回调并结束工具");
            page.OnActivated(); Click(page, "开始点取"); TankLadderPlacementTool.Pick(); arrange();
            var pending = TankLadderBuilder.Last; Click(page, "结束点取");
            check(!pending.Written && !confirm.IsEnabled && !update.Content.ToString().Contains("●"), "结束点取清理未确认预览");
            page.OnWorkspaceClosing(); page.OnWorkspaceClosing(); check(formal.Written, "重复关闭保留正式元素");
        }
        private static void Click(UserControl page, string content)
        { Buttons(page).Single(button => button.Content.ToString() == content).RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); }
        private static System.Collections.Generic.IEnumerable<Button> Buttons(DependencyObject parent)
        {
            if (parent is Button) yield return (Button)parent;
            for (int i = 0; i < System.Windows.Media.VisualTreeHelper.GetChildrenCount(parent); i++)
                foreach (var button in Buttons(System.Windows.Media.VisualTreeHelper.GetChild(parent, i))) yield return button;
        }
    }
}
