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
    internal static class LineCoordinatePipeTool
    {
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive;
        internal static void Begin() { IsActive = true; }
        internal static void End() { if (!IsActive) return; IsActive = false; var ended = Ended; if (ended != null) ended(); }
        internal static void Pick(LocatedElement located) { End(); var picked = Picked; if (picked != null) picked(located); }
    }
    internal static class LineCoordinatePipeReader
    {
        // 替身：真实读取走 PipeElementReader EC 管线，检查里直接回放考察数据。
        internal static LinePipeSurvey NextPipe;
        internal static LinePipeSurvey Read(LocatedElement located) { return NextPipe; }
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

            // —— 04 快速对齐：四个方向按钮只填充草稿，应用修改才写回 ——
            Click(page, "AlignVerticalStartButton");
            check(Get<TextBox>(page, "EndXText").Text == Get<TextBox>(page, "StartXText").Text
                && Get<TextBox>(page, "EndYText").Text == Get<TextBox>(page, "StartYText").Text
                && Get<TextBox>(page, "EndZText").Text == "6000" && Get<TextBox>(page, "StartXText").Text == "1000.0001234567", "按起点对齐竖直线填充");
            Click(page, "ApplyButton");
            check(Math.Abs(Session.Instance.Active.Lines[42].Path[0].Segment.End.X - 1000000.1234567) < 1e-6
                && Session.Instance.Active.Lines[42].Path[0].Segment.End.Y == -2000000
                && Session.Instance.Active.Lines[42].Path[0].Segment.End.Z == 6000000, "竖直线真实写入");
            check(!Get<Button>(page, "ApplyButton").IsEnabled, "应用后同值禁用");
            Click(page, "AlignHorizontalEndButton");
            check(Get<TextBox>(page, "StartZText").Text == "6000", "按终点对齐水平线填充");
            Click(page, "ReloadButton");
            check(Get<TextBox>(page, "StartZText").Text == "0" && !Get<Button>(page, "ApplyButton").IsEnabled, "重新读取丢弃对齐草稿");

            // 对齐到管道：先把假模型重置回斜线（上面的竖直线 Apply 已真实写模），再重新读取。
            Session.Instance.Active.Lines[42].Path[0].Segment = new DSegment3d(DPoint3d.FromXYZ(1000000.1234567, -2000000, 0), DPoint3d.FromXYZ(4000000, 5000000, 6000000));
            Click(page, "ReloadButton");
            // 水平管：轴线高 5000、外径 200.7 → 管底 4899.65 → 向下取整 4899。
            LineCoordinatePipeReader.NextPipe = new LinePipeSurvey
            {
                AxisStartX = 0, AxisStartY = 0, AxisStartZ = 5000,
                AxisEndX = 8000, AxisEndY = 0, AxisEndZ = 5000,
                OutsideDiameterMm = 200.7, PickX = 3600.5, PickY = 1777.25, PickZ = 4895, PipeNumber = "P-1001"
            };
            Click(page, "AlignPipeButton"); LineCoordinatePipeTool.Pick(located); Flush(page);
            check(MainWindow.Current.Error && MainWindow.Current.Status.Contains("既不是水平线也不是竖直线"), "斜线对齐管道拒绝");
            Get<TextBox>(page, "StartZText").Text = "2000"; Get<TextBox>(page, "EndZText").Text = "2000";
            Click(page, "AlignPipeButton"); LineCoordinatePipeTool.Pick(located); Flush(page);
            check(Get<TextBox>(page, "StartZText").Text == "4899" && Get<TextBox>(page, "EndZText").Text == "4899"
                && Get<TextBox>(page, "StartXText").Text == "1000.0001234567" && !MainWindow.Current.Error, "水平线贴管底标高，X/Y 保持");
            Click(page, "ReloadButton");
            Click(page, "AlignVerticalStartButton");
            Click(page, "AlignPipeButton"); LineCoordinatePipeTool.Pick(located); Flush(page);
            check(Get<TextBox>(page, "StartXText").Text == "3600.5" && Get<TextBox>(page, "EndXText").Text == "3600.5"
                && Get<TextBox>(page, "StartYText").Text == "1777.25" && Get<TextBox>(page, "EndYText").Text == "1777.25"
                && Get<TextBox>(page, "StartZText").Text == "0" && Get<TextBox>(page, "EndZText").Text == "4899", "竖直线移到点取位置下方");
            Click(page, "ApplyButton");
            check(Math.Abs(Session.Instance.Active.Lines[42].Path[0].Segment.End.X - 3600500) < 0.01
                && Math.Abs(Session.Instance.Active.Lines[42].Path[0].Segment.End.Y - 1777250) < 0.01
                && Math.Abs(Session.Instance.Active.Lines[42].Path[0].Segment.End.Z - 4899000) < 1e-6, "竖直线对齐真实写入");
            Click(page, "ReloadButton");
            // 模型此刻是竖直线（两端 XY 相同），先把终点 X 拉开再做水平线，避免零长度草稿。
            Get<TextBox>(page, "EndXText").Text = "4600";
            Get<TextBox>(page, "StartZText").Text = "2000"; Get<TextBox>(page, "EndZText").Text = "2000";
            LineCoordinatePipeReader.NextPipe = new LinePipeSurvey
            {
                AxisStartX = 500, AxisStartY = 500, AxisStartZ = 2000,
                AxisEndX = 500, AxisEndY = 500, AxisEndZ = 9000,
                OutsideDiameterMm = 200.7, PickX = 500, PickY = 500
            };
            Click(page, "AlignPipeButton"); LineCoordinatePipeTool.Pick(located); Flush(page);
            check(MainWindow.Current.Error && MainWindow.Current.Status.Contains("水平管"), "水平线拒绝立管");
            Click(page, "ReloadButton");
            var bare = new LineCoordinatesPage(); bare.OnActivated();
            Click(bare, "AlignPipeButton");
            check(MainWindow.Current.Error && MainWindow.Current.Status.Contains("请先点取直线"), "未点取直线拒绝对齐管道");
            bare.OnWorkspaceClosing();
            return page;
        }
    }
}
