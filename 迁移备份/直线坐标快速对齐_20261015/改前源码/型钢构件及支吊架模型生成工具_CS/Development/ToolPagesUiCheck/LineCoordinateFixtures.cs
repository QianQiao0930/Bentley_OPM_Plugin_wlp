using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    // 使用真实页面、Reader、Editor；只有宿主 API 与点取派发是隔离替身。
    internal static class LineCoordinateLocateTool
    {
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive;
        internal static int Installs;
        internal static void Begin() { if (!IsActive) Installs++; IsActive = true; }
        internal static void End() { if (!IsActive) return; IsActive = false; var ended = Ended; if (ended != null) ended(); }
        internal static void Pick(LocatedElement located) { End(); var picked = Picked; if (picked != null) picked(located); }
    }
    internal static class LineCoordinateUiChecks
    {
        internal static LocatedElement Setup(bool is3d)
        {
            var model = new DgnModel { Is3d = is3d }; Session.Instance.Active = model;
            ulong id = 42; var path = new CurveVector(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(DPoint3d.FromXYZ(1000000.1234567, -2000000, 0), DPoint3d.FromXYZ(4000000, 5000000, is3d ? 6000000 : 0))));
            model.Lines.Add(id, new LineElement { Model = model, ElementId = new ElementId(ref id), Path = path });
            return new LocatedElement { ModelRef = model, ElementId = id, ClickX = 0, ClickY = 0, ClickZ = 0 };
        }
        private static T Get<T>(LineCoordinatesPage page, string name) where T : class { return (T)page.FindName(name); }
        private static void Click(LineCoordinatesPage page, string name) { Get<Button>(page, name).RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); }
        private static void Flush(LineCoordinatesPage page) { page.Dispatcher.Invoke(() => { }, DispatcherPriority.Background); }
        internal static LineCoordinatesPage Run(Action<bool, string> check)
        {
            LicenseService.IsActivated = true;
            var page = new LineCoordinatesPage(); page.OnActivated();
            check(!Get<Button>(page, "ApplyButton").IsEnabled && !Get<Grid>(page, "StartFields").IsEnabled, "未点取禁编辑/应用");
            var located = Setup(true);
            Click(page, "PickButton"); Click(page, "PickButton"); check(LineCoordinateLocateTool.Installs == 1, "重复开始点取幂等");
            LineCoordinateLocateTool.Pick(located); Flush(page);
            check(Get<TextBox>(page, "StartXText").Text == LineCoordinateCalculator.Format(1000.0001234567), "点取完整精度");
            check(!Get<Button>(page, "StopButton").IsEnabled && !Get<Button>(page, "ApplyButton").IsEnabled, "点取后自动结束/原值禁应用");
            Get<TextBox>(page, "EndZText").Text = "6500.25";
            check(Get<Button>(page, "ApplyButton").IsEnabled, "编辑有效值启用应用");
            check(Session.Instance.Active.Lines[42].Path[0].Segment.End.Z == 6000000, "编辑输入不自动写模型");
            Get<TextBox>(page, "EndZText").Text = "NaN"; check(!Get<Button>(page, "ApplyButton").IsEnabled, "非法输入禁应用");
            Click(page, "ReloadButton"); check(Get<TextBox>(page, "EndZText").Text == "6000", "重新读取丢弃草稿");
            Get<TextBox>(page, "EndZText").Text = "6500.25"; Click(page, "ApplyButton");
            check(Session.Instance.Active.Lines[42].Path[0].Segment.End.Z == 6500250 && !Get<Button>(page, "ApplyButton").IsEnabled, "真实Editor应用并回读");
            check(MainWindow.Current.Status.Contains("写入耗时") && !MainWindow.Current.Error, "写入计时状态");
            check(Session.Instance.Active.Lines[42].Path[0].Segment.Start.X == 1000000.1234567, "修改一轴保留其他精度");
            Get<TextBox>(page, "StartYText").Text = "99";
            TransactionManager.RaiseUndo(); check(!Get<Grid>(page, "StartFields").IsEnabled, "撤销/重做失效旧快照");
            LineCoordinateLocateTool.Pick(located); page.OnDeactivated(); Flush(page);
            check(Get<TextBox>(page, "StartXText").Text == "", "离开页面阻止延迟点取");
            page.OnActivated(); Click(page, "PickButton"); LineCoordinateLocateTool.Pick(located); Click(page, "StopButton"); Flush(page);
            check(Get<TextBox>(page, "StartXText").Text == "", "结束阻止排队读取");
            LineCoordinateLocateTool.Pick(located); Flush(page); Get<TextBox>(page, "StartYText").Text = "99";
            page.OnDeactivated(); check(Session.Instance.Active.Lines[42].Path[0].Segment.Start.Y == -2000000, "离开丢弃草稿不写模型");
            page.OnWorkspaceClosing(); page.OnWorkspaceClosing();
            var twoD = new LineCoordinatesPage(); twoD.OnActivated(); located = Setup(false); LineCoordinateLocateTool.Pick(located); Flush(twoD);
            check(Get<TextBox>(twoD, "StartZText").IsReadOnly && Get<TextBox>(twoD, "EndZText").IsReadOnly, "二维Z只读"); twoD.OnWorkspaceClosing();
            page = new LineCoordinatesPage(); page.OnActivated(); located = Setup(true); LineCoordinateLocateTool.Pick(located); Flush(page);
            Get<TextBox>(page, "EndXText").Text = "4500";
            Session.Instance.Active.Lines[42].Path[0].Segment = new DSegment3d(DPoint3d.FromXYZ(5, 0, 0), DPoint3d.FromXYZ(10, 0, 0));
            Click(page, "ApplyButton"); check(MainWindow.Current.Error && MainWindow.Current.Status.Contains("其他操作"), "外部改线阻止覆盖");
            check(Get<TextBox>(page, "EndXText").Text == "4500", "应用失败保留草稿");
            page.OnWorkspaceClosing();
            page = new LineCoordinatesPage(); page.OnActivated(); located = Setup(true); LineCoordinateLocateTool.Pick(located); Flush(page);
            return page;
        }
    }
}
