using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 水龙柜局部坐标建模助手。圆柱、圆环使用真实曲面，螺旋使用连续三次样条。
    /// </summary>
    internal sealed class HoseCabinetGeometry
    {
        internal FireCabinetFrame Frame
        {
            get;
        }
        internal uint Red { get; } = FireExtinguisherBuilder.Color(new[] { 204, 9, 6 });
        internal uint Brass { get; } = FireExtinguisherBuilder.Color(new[] { 192, 148, 69 });
        internal uint Steel { get; } = FireExtinguisherBuilder.Color(new[] { 174, 180, 186 });
        internal uint Rubber { get; } = FireExtinguisherBuilder.Color(new[] { 35, 39, 43 });
        internal uint Hose { get; } = FireExtinguisherBuilder.Color(new[] { 64, 70, 76 });

        internal HoseCabinetGeometry(FireCabinetFrame frame)
        {
            Frame = frame;
        }

        internal SolidKernelEntity BoxBody(double x1, double y1, double z1, double x2, double y2, double z2)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[] { Frame.Point(x1, y1, z1), Frame.Point(x2, y1, z1),
                Frame.Point(x2, y2, z1), Frame.Point(x1, y2, z1) }, Frame.Vector(0, 0, z2 - z1));
        }

        internal Element Box(double x1, double y1, double z1, double x2, double y2, double z2, uint color)
        {
            return SolidPrimitiveFactory.Element(BoxBody(x1, y1, z1, x2, y2, z2), color);
        }

        internal SolidKernelEntity CylinderBody(double x1, double y1, double z1,
            double x2, double y2, double z2, double radius)
        {
            return SolidPrimitiveFactory.Cylinder(Frame.Point(x1, y1, z1), Frame.Point(x2, y2, z2), radius * Frame.Scale);
        }

        internal Element Cylinder(double x1, double y1, double z1, double x2, double y2, double z2, double radius, uint color)
        {
            return SolidPrimitiveFactory.Element(CylinderBody(x1, y1, z1, x2, y2, z2, radius), color);
        }

        internal Element TubeX(double x1, double x2, double y, double z, double outer, double inner, uint color)
        {
            var body = CylinderBody(x1, y, z, x2, y, z, outer);
            SolidPrimitiveFactory.Subtract(ref body, new[] { CylinderBody(x1 - 1, y, z, x2 + 1, y, z, inner) }, "DN25 空心接口");
            return SolidPrimitiveFactory.Element(body, color);
        }

        internal Element HexX(double x1, double x2, double y, double z, double radius, double bore, uint color)
        {
            var points = new List<DPoint3d>();
            for (int index = 0; index < 6; index++)
            {
                double angle = index * Math.PI / 3;
                points.Add(Frame.Point(x1, y + radius * Math.Cos(angle), z + radius * Math.Sin(angle)));
            }
            var body = SolidPrimitiveFactory.PolygonPrism(points, Frame.Vector(x2 - x1, 0, 0));
            SolidPrimitiveFactory.Subtract(ref body, new[] { CylinderBody(x1 - 1, y, z, x2 + 1, y, z, bore) }, "六角接头内孔");
            return SolidPrimitiveFactory.Element(body, color);
        }

        internal Element Torus(double x, double y, double z, double major, double minor, bool axisY, uint color)
        {
            var primitive = SolidPrimitive.CreateDgnTorusPipe(new DgnTorusPipeDetail(Frame.Point(x, y, z),
                axisY ? Frame.Direction(1, 0, 0) : Frame.Direction(0, 1, 0), Frame.Direction(0, 0, 1),
                major * Frame.Scale, minor * Frame.Scale, 2 * Math.PI, true));
            Element element = DraftingElementSchema.ToElement(Session.Instance.GetActiveDgnModel(), primitive, null);
            if (element == null)
            {
                throw new InvalidOperationException("接口或卷盘圆环生成失败。");
            }
            var properties = new ElementPropertiesSetter();
            properties.SetColor(color);
            if (!properties.Apply(element))
            {
                throw new InvalidOperationException("圆环颜色设置失败。");
            }
            return element;
        }

        /// <summary>
        /// 绕 Y 轴的螺旋卷绕，或绕 X 轴的螺纹；每段用解析切向构造三次贝塞尔。
        /// </summary>
        internal Element Helix(double x, double y, double z, double radius, double travel,
            int turns, double tubeRadius, bool axisY, uint color)
        {
            HoseHelixPath data = HoseHelixCalculator.Calculate(x, y, z, radius, travel, turns, axisY);
            var poles = new List<DPoint3d>();
            foreach (double[] point in data.Poles)
            {
                poles.Add(Frame.Point(point));
            }
            var spline = MSBsplineCurve.CreateFromPoles(poles, null, data.Knots, 4, false, false);
            if (spline == null)
            {
                throw new InvalidOperationException("卷绕软管或螺纹样条生成失败。");
            }
            var path = CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateBsplineCurve(spline));
            var profile = CurveVector.CreateDisk(DEllipse3d.FromCenterRadiusNormal(poles[0], tubeRadius * Frame.Scale,
                Frame.Direction(data.StartTangent[0], data.StartTangent[1], data.StartTangent[2])), CurveVector.BoundaryType.Outer);
            return SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Sweep(profile, path), color);
        }

        internal Element Cell(string name, List<Element> parts)
        {
            return new CellHeaderElement(Session.Instance.GetActiveDgnModel(), name, Frame.Point(0, 0, 0), DMatrix3d.Identity, parts);
        }
    }
}
