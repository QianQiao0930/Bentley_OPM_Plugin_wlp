using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>不缓存 Element；应用前按所属模型及 ID 重读。</summary>
    internal sealed class LineCoordinateSelection
    {
        internal DgnModel Model;
        internal ulong ElementId;
        internal bool Is3d;
        internal double UorPerMm;
        internal LineCoordinates Coordinates;
    }

    internal static class LineCoordinateReader
    {
        internal static LineCoordinateSelection Read(LocatedElement located)
        {
            if (located == null || located.ModelRef == null) throw new InvalidOperationException("没有选中的直线段。");
            if (located.ModelRef.IsDgnAttachment) throw new InvalidOperationException("参考文件中的线段不能修改，请选择活动模型中的直线。");
            var model = located.ModelRef.GetDgnModel();
            using (var element = FindWritable(model, located.ElementId))
            {
                double scale = model.GetModelInfo().UorPerMeter / 1000.0;
                if (!LineCoordinateCalculator.Finite(scale) || scale <= 0) throw new InvalidOperationException("模型单位无效。");
                return new LineCoordinateSelection { Model = model, ElementId = located.ElementId,
                    Is3d = model.Is3d, UorPerMm = scale, Coordinates = ReadCoordinates(element, scale) };
            }
        }

        internal static Element FindWritable(DgnModel model, ulong id)
        {
            var active = Session.Instance.GetActiveDgnModel();
            if (active == null) throw new InvalidOperationException("请先打开 DGN 模型。");
            if (model == null || !ReferenceEquals(model, active))
                throw new InvalidOperationException("所选线段不属于当前活动模型，请重新点取。");
            if (model.IsReadOnly || model.GetDgnFile().IsReadOnly)
                throw new InvalidOperationException("当前模型或文件是只读的，不能修改线段。");
            var element = model.FindElementById(new ElementId(ref id));
            try
            {
                if (element == null || !element.IsValid || element.IsDeleted)
                    throw new InvalidOperationException("所选线段已删除或失效，请重新点取。");
                if (!(element is LineElement) || element.ElementType != MSElementType.Line ||
                    element.IsComplexComponent || element.ParentElement != null)
                    throw new InvalidOperationException("只支持独立直线段，不支持折线、复杂链或块内子线段。");
                if (element.IsEffectivelyLocked(true, false))
                    throw new InvalidOperationException("所选线段或所在图层已锁定，不能修改。");
                return element;
            }
            catch { if (element != null) element.Dispose(); throw; }
        }

        internal static LineCoordinates ReadCoordinates(Element element, double scale)
        {
            DPoint3d start, end;
            ReadEndpoints(element, out start, out end);
            return new LineCoordinates(new LineCoordinatePoint(start.X / scale, start.Y / scale, start.Z / scale),
                new LineCoordinatePoint(end.X / scale, end.Y / scale, end.Z / scale));
        }

        internal static void ReadEndpoints(Element element, out DPoint3d start, out DPoint3d end)
        {
            var path = CurvePathQuery.ElementToCurveVector(element);
            DSegment3d segment;
            start = end = DPoint3d.FromXYZ(0, 0, 0);
            if (path == null || path.GetBoundaryType() != CurveVector.BoundaryType.Open || path.Count != 1 ||
                !path.GetPrimitive(0).TryGetLine(out segment) || !path.GetPrimitive(0).GetStartEnd(out start, out end))
                throw new InvalidOperationException("只支持一条直线段，不支持折线或曲线。");
        }
    }
}
