using System;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class LicenseService { internal static bool IsActivated = true; }
    internal static class Program
    {
        private static int checks;
        private static void Check(bool value, string label) { checks++; if (!value) throw new Exception(label); }
        private static void Reject(Action action, string reason)
        {
            try { action(); } catch (InvalidOperationException ex) { Check(ex.Message.Contains(reason), "拒绝原因：" + ex.Message); return; }
            throw new Exception("操作没有拒绝：" + reason);
        }
        private static LineCoordinates Coordinates(double x, double y, double z)
        {
            return new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(x, y, z));
        }
        private static LocatedElement Setup(double uorPerMeter = 1000000, bool is3d = true)
        {
            var model = new DgnModel { Is3d = is3d }; model.Info.UorPerMeter = uorPerMeter; Session.Instance.Active = model;
            ulong id = 42; var path = new CurveVector(CurveVector.BoundaryType.Open);
            double scale = uorPerMeter / 1000;
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(DPoint3d.FromXYZ(0, 0, 0), DPoint3d.FromXYZ(1000 * scale, 0, 0))));
            model.Lines.Add(id, new LineElement { Model = model, ElementId = new ElementId(ref id), Path = path });
            TransactionManager.IsUndoInProgress = false; TransactionManager.CancelFails = false;
            TransactionManager.Closes = TransactionManager.Cancels = 0; LicenseService.IsActivated = true;
            return new LocatedElement { ModelRef = model, ElementId = id, ClickX = 0, ClickY = 0, ClickZ = 0 };
        }
        private static void Main()
        {
            Check(LineCoordinateCalculator.Length(Coordinates(3, 4, 12)) == 13, "三维长度");
            Reject(() => LineCoordinateCalculator.Validate(Coordinates(0, 0, 0), true, 0), "重合");
            Reject(() => LineCoordinateCalculator.Validate(Coordinates(0.0001, 0, 0), true, 0.001), "分辨率");
            Reject(() => LineCoordinateCalculator.Validate(Coordinates(1, 0, 1), false, 0), "二维");
            foreach (string bad in new[] { "", "NaN", "Infinity", "1e999", "abc", "1,000" }) Reject(() => LineCoordinateCalculator.Parse(bad, "X"), bad == "NaN" || bad == "Infinity" || bad == "1e999" ? "有限" : "有效");
            foreach (var culture in new[] { "zh-CN", "en-US", "de-DE" })
            {
                CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo(culture);
                foreach (double number in new[] { 0d, -1.2345678901234567, 1234567890.1234567, 1e-12 })
                    Check(LineCoordinateCalculator.Parse(LineCoordinateCalculator.Format(number), "X") == number, "往返精度 " + culture);
            }
            CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("zh-CN");
            Check(LineCoordinateCalculator.Finite(LineCoordinateCalculator.Length(Coordinates(1e200, 1e200, 1e200))), "长度不发生平方溢出");

            foreach (double scale in new[] { 1000d, 1000000d, 1000000000d })
            {
                var located = Setup(scale); var selected = LineCoordinateReader.Read(located); var model = Session.Instance.Active;
                Check(selected.Coordinates.End.X == 1000, "UOR单位读取");
                string metadata = model.Lines[42].Metadata;
                var target = new LineCoordinates(new LineCoordinatePoint(-1500.123456789, 2200, -350), new LineCoordinatePoint(6000, 1234.5, 500));
                var result = LineCoordinateEditor.Apply(selected, target);
                Check(LineCoordinateCalculator.Same(result.Coordinates, target, 1e-9), "XYZ写入往返");
                Check(model.Lines.Count == 1 && result.ElementId == 42 && model.Lines[42].Metadata == metadata, "保留ID与属性");
                Check(model.WriteCount == 1 && TransactionManager.Closes == 2 && TransactionManager.Cancels == 0, "独立撤销事务");
                Check(model.Lines[42].Path.GetPrimitive(0).Segment.End.Y == target.End.Y * (scale / 1000), "实际存储UOR");
                Reject(() => LineCoordinateEditor.Apply(result, target), "没有变化");
            }
            var pick = Setup(is3d: false); var selection = LineCoordinateReader.Read(pick);
            Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(50, 0, 1)), "二维");
            Check(LineCoordinateEditor.Apply(selection, Coordinates(50, 30, 0)).Coordinates.End.Y == 30, "二维XY可修改");

            foreach (double raw in new[] { 1.2345678901234567, 1234567890.1234567, -98765432.1234567, 0.0000000123456789 })
            {
                pick = Setup(); var model = Session.Instance.Active;
                model.Lines[42].Path[0].Segment = new DSegment3d(DPoint3d.FromXYZ(raw, raw, raw), DPoint3d.FromXYZ(1000000, 2000000, 3000000));
                selection = LineCoordinateReader.Read(pick);
                var target = new LineCoordinates(selection.Coordinates.Start, new LineCoordinatePoint(selection.Coordinates.End.X, selection.Coordinates.End.Y, 3500));
                LineCoordinateEditor.Apply(selection, target);
                Check(model.Lines[42].Path[0].Segment.Start.X == raw && model.Lines[42].Path[0].Segment.Start.Y == raw && model.Lines[42].Path[0].Segment.Start.Z == raw, "未修改轴保留原UOR精度");
            }

            pick = Setup(); selection = LineCoordinateReader.Read(pick); var current = Session.Instance.Active;
            current.IsReadOnly = true; Reject(() => LineCoordinateReader.Read(pick), "只读"); current.IsReadOnly = false;
            current.File.IsReadOnly = true; Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "只读"); current.File.IsReadOnly = false;
            current.Lines[42].Locked = true; Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "锁定"); current.Lines[42].Locked = false;
            current.Lines[42].ElementType = MSElementType.LineString; Reject(() => LineCoordinateReader.Read(pick), "折线"); current.Lines[42].ElementType = MSElementType.Line;
            current.Lines[42].Path.Add(CurvePrimitive.CreateLine(new DSegment3d())); Reject(() => LineCoordinateReader.Read(pick), "折线"); current.Lines[42].Path.RemoveAt(1);
            current.Lines[42].Path[0].IsLine = false; Reject(() => LineCoordinateReader.Read(pick), "曲线"); current.Lines[42].Path[0].IsLine = true;
            current.Lines[42].IsComplexComponent = true; Reject(() => LineCoordinateReader.Read(pick), "子线段"); current.Lines[42].IsComplexComponent = false;
            current.Lines[42].ParentElement = new Element(); Reject(() => LineCoordinateReader.Read(pick), "子线段"); current.Lines[42].ParentElement = null;
            var attachment = new DgnModelRef { Model = current, IsDgnAttachment = true };
            Reject(() => LineCoordinateReader.Read(new LocatedElement { ModelRef = attachment, ElementId = 42 }), "参考");
            Session.Instance.Active = new DgnModel(); Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "活动模型"); Session.Instance.Active = current;
            current.Info.UorPerMeter *= 2; Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "单位"); current.Info.UorPerMeter /= 2;
            var replacement = new CurveVector(CurveVector.BoundaryType.Open); replacement.Add(CurvePrimitive.CreateLine(new DSegment3d(DPoint3d.FromXYZ(10, 0, 0), DPoint3d.FromXYZ(20, 0, 0))));
            current.Lines[42].Path = replacement; Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "其他操作");
            current.Lines.Clear(); Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "失效");

            foreach (string failure in new[] { "Edit", "Replace", "Throw", "Readback" })
            {
                pick = Setup(); selection = LineCoordinateReader.Read(pick); current = Session.Instance.Active;
                current.EditFails = failure == "Edit"; current.ReplaceFails = failure == "Replace";
                current.ReplaceThrows = failure == "Throw"; current.BadReadback = failure == "Readback";
                Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(500, 20, 30)), failure == "Edit" ? "几何" : failure == "Replace" ? "写入失败" : failure == "Throw" ? "异常" : "不一致");
                Check(LineCoordinateCalculator.Same(LineCoordinateReader.Read(pick).Coordinates, selection.Coordinates, 0), "失败回退原坐标 " + failure);
            }
            pick = Setup(); selection = LineCoordinateReader.Read(pick); TransactionManager.IsUndoInProgress = true;
            Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "撤销"); TransactionManager.IsUndoInProgress = false;
            LicenseService.IsActivated = false; Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "激活"); LicenseService.IsActivated = true;
            Session.Instance.Active.ReplaceFails = true; TransactionManager.CancelFails = true;
            Reject(() => LineCoordinateEditor.Apply(selection, Coordinates(1, 2, 3)), "回退失败");

            // —— 快速对齐与对齐到管道（纯计算层）——
            LineCoordinates horizontalSample() { return new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(5000, 0, 0)); }
            LineCoordinates verticalSample() { return new LineCoordinates(new LineCoordinatePoint(700, 900, 0), new LineCoordinatePoint(700, 900, 4100)); }
            var slope = new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(3000, 4000, 5000));
            var anchored = LinePipeAlign.AlignVertical(slope, true);
            Check(anchored.End.X == 0 && anchored.End.Y == 0 && anchored.End.Z == 5000, "按起点对齐竖直线");
            anchored = LinePipeAlign.AlignVertical(slope, false);
            Check(anchored.Start.X == 3000 && anchored.Start.Y == 4000 && anchored.Start.Z == 0, "按终点对齐竖直线");
            anchored = LinePipeAlign.AlignHorizontal(slope, true);
            Check(anchored.End.Z == 0 && anchored.End.X == 3000 && anchored.End.Y == 4000, "按起点对齐水平线");
            anchored = LinePipeAlign.AlignHorizontal(slope, false);
            Check(anchored.Start.Z == 5000 && anchored.Start.X == 0, "按终点对齐水平线");
            Reject(() => LinePipeAlign.AlignVertical(new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(0, 0, 0)), true), "无法对齐");
            Check(LinePipeAlign.IsHorizontal(new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(1000, 0, 0.001))), "水平容差边界");
            Check(!LinePipeAlign.IsHorizontal(new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(1000, 0, 0.002))), "超出容差非水平");
            Check(LinePipeAlign.IsVertical(new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(0.001, 0, 1000))), "竖直容差边界");
            Check(LinePipeAlign.IsHorizontal(horizontalSample()) && LinePipeAlign.IsVertical(verticalSample()), "样本方向自检");

            var horizontalPipe = new LinePipeSurvey
            {
                AxisStartX = 0, AxisStartY = 0, AxisStartZ = 5000,
                AxisEndX = 8000, AxisEndY = 0, AxisEndZ = 5000,
                OutsideDiameterMm = 200.7, PickX = 3600.5, PickY = 1777.25, PickZ = 4895, PipeNumber = "P-1001"
            };
            Check(Math.Abs(LinePipeAlign.PipeBottomElevationMm(horizontalPipe) - 4899.65) < 1e-9, "水平管底标高");
            var riserPipe = new LinePipeSurvey
            {
                AxisStartX = 500, AxisStartY = 500, AxisStartZ = 2000,
                AxisEndX = 500, AxisEndY = 500, AxisEndZ = 9000,
                OutsideDiameterMm = 200.7, PickX = 500, PickY = 500
            };
            Check(Math.Abs(LinePipeAlign.PipeBottomElevationMm(riserPipe) - 1899.65) < 1e-9, "立管低端为底");
            Reject(() => LinePipeAlign.PipeBottomElevationMm(new LinePipeSurvey()), "外径");
            string summary;
            var horizontalLine = new LineCoordinates(new LineCoordinatePoint(1200, 800, 2000), new LineCoordinatePoint(4800, 800, 2000));
            var pipeTarget = LinePipeAlign.ToPipe(horizontalLine, horizontalPipe, true, out summary);
            Check(pipeTarget.Start.Z == 4899 && pipeTarget.End.Z == 4899 && pipeTarget.Start.X == 1200 && pipeTarget.End.Y == 800, "水平线贴管底标高向下取整");
            Check(summary.Contains("4899"), "摘要含管底标高");
            pipeTarget = LinePipeAlign.ToPipe(verticalSample(), horizontalPipe, true, out summary);
            Check(pipeTarget.Start.X == 3600.5 && pipeTarget.Start.Y == 1777.25 && pipeTarget.End.X == 3600.5 && pipeTarget.End.Y == 1777.25,
                "竖直线两端移到点取位置");
            Check(pipeTarget.Start.Z == 0 && pipeTarget.End.Z == 4899, "竖直线终点贴管底标高，起点保持");
            Reject(() => LinePipeAlign.ToPipe(slope, horizontalPipe, true, out summary), "既不是水平线也不是竖直线");
            Reject(() => LinePipeAlign.ToPipe(horizontalLine, riserPipe, true, out summary), "水平管");
            Reject(() => LinePipeAlign.ToPipe(horizontalLine, new LinePipeSurvey(), true, out summary), "外径");
            Reject(() => LinePipeAlign.ToPipe(horizontalLine, horizontalPipe, false, out summary), "二维");
            Reject(() => LinePipeAlign.ToPipe(horizontalLine, new LinePipeSurvey { OutsideDiameterMm = 200, PickX = double.NaN }, true, out summary), "点取");
            Reject(() => LinePipeAlign.ToPipe(new LineCoordinates(new LineCoordinatePoint(0, 0, 0), new LineCoordinatePoint(0, 0, 0)), horizontalPipe, true, out summary), "无法对齐");

            Console.WriteLine("PASS: " + checks + " 直线坐标、单位、精度、类型/权限、并发改动、事务失败回退与快速对齐/管道对齐检查。API替身不代表宿主实测。");
        }
    }
}
