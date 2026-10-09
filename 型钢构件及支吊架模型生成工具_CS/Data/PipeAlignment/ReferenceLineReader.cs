using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>只读直线端点，不构造 OpenPlant 修改对象。</summary>
    internal static class ReferenceLineReader
    {
        internal static PipeInfo ReadIfLine(LocatedElement located)
        {
            if (located == null) throw new ArgumentNullException("located");
            var active = Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel();
            var model = located.ModelRef == null ? active : located.ModelRef.GetDgnModel();
            if (model == null || !model.Is3d) throw new InvalidOperationException("请选择三维模型中的基准。");
            ulong id = located.ElementId;
            var element = model.FindElementById(new ElementId(ref id));
            if (element == null || !element.IsValid) throw new InvalidOperationException("基准元素已失效。");
            if (!(element is LineElement)) return null;
            var curves = CurvePathQuery.ElementToCurveVector(element);
            DSegment3d segment;
            DPoint3d start, end;
            if (curves == null || curves.Count != 1 || !curves.GetPrimitive(0).TryGetLine(out segment)
                || !curves.GetPrimitive(0).GetStartEnd(out start, out end))
                throw new InvalidOperationException("请选择单根水平直线。");
            if (located.IsFromReference())
            {
                var attachment = located.ModelRef.AsDgnAttachment();
                if (attachment == null) throw new InvalidOperationException("参考直线缺少附件坐标关系。");
                int depth = 0;
                while (attachment != null)
                {
                    if (++depth > 32) throw new InvalidOperationException("参考附件嵌套过深。");
                    DTransform3d transform;
                    attachment.GetTransformToParent(out transform, true);
                    start = transform.MultiplyPoint(start.X, start.Y, start.Z);
                    end = transform.MultiplyPoint(end.X, end.Y, end.Z);
                    attachment = attachment.GetParentDgnAttachment();
                }
            }
            var units = DgnUnitServiceFactory.ForModel(active);
            if (!units.IsAvailable) throw new InvalidOperationException("无法取得模型单位。");
            return new PipeInfo { IsReferenceLine = true, ElementId = id, Source = located,
                ClassName = "REFERENCE_LINE", PipeNumber = "水平直线 " + id,
                IsReadOnly = true, IsFromReference = located.IsFromReference(), AxisSource = "直线端点",
                Axis = new PipeAxis(units.UorToMillimeter(start.X), units.UorToMillimeter(start.Y), units.UorToMillimeter(start.Z),
                    units.UorToMillimeter(end.X), units.UorToMillimeter(end.Y), units.UorToMillimeter(end.Z)) };
        }
    }
}
