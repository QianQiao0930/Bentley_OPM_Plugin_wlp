using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 模型边界的生成结果；外观模型缺失会明确交给页面和统计。
    /// </summary>
    internal sealed class FireCabinetBuildResult
    {
        internal Element Cell
        {
            get; set;
        }
        internal int InteriorModelCount
        {
            get; set;
        }
        internal string Warning
        {
            get; set;
        }
    }

    /// <summary>
    /// 迁移原箱体、翻盖、把手及标识，保留真实圆角和整体单元。
    /// </summary>
    internal static class FireCabinetBuilder
    {
        internal static FireCabinetBuildResult Build(FireCabinetPlan plan, DPoint3d origin)
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
            {
                throw new InvalidOperationException("灭火器箱需要三维活动模型。");
            }

            var frame = new FireCabinetFrame(origin, model.GetModelInfo().UorPerMeter / 1000, plan.Parameters.HeadingDegrees);
            FireCabinetPreset box = plan.Box;
            double left = -box.WidthMm / 2;
            double right = box.WidthMm / 2;
            double thickness = FireCabinetCatalog.WallThicknessMm;
            double bodyTop = box.HeightMm - thickness + 0.5;
            double lidBottom = box.HeightMm - box.LidHeightMm;
            SolidKernelEntity body = RoundedBox(frame, left, 0, 0, right, box.DepthMm, bodyTop, 20);
            SolidPrimitiveFactory.Subtract(ref body, new[]
            {
                RoundedBox(frame, left + thickness, thickness, thickness, right - thickness,
                    box.DepthMm - thickness, bodyTop + 1, 18)
            }, "灭火器箱内腔");
            SolidKernelEntity lid = RoundedBox(frame, left - 3, -3, lidBottom, right + 3,
                box.DepthMm + 3, box.HeightMm, 20);
            SolidPrimitiveFactory.Subtract(ref lid, new[]
            {
                RoundedBox(frame, left - 1, -1, lidBottom - 1, right + 1, box.DepthMm + 1,
                    box.HeightMm - thickness, 18)
            }, "翻盖内腔");
            SolidPrimitiveFactory.Union(ref body, new[] { lid }, "箱体与翻盖");
            uint red = FireExtinguisherBuilder.Color(new[] { 204, 9, 6 });
            var children = new List<Element> { SolidPrimitiveFactory.Element(body, red) };
            double gripBottom = lidBottom + (box.LidHeightMm - 12) / 2;
            children.Add(Box(frame, left - 15, box.DepthMm / 2 - 40, gripBottom, left - 3, box.DepthMm / 2 + 40, gripBottom + 12, red));
            children.Add(Box(frame, right + 3, box.DepthMm / 2 - 40, gripBottom, right + 15, box.DepthMm / 2 + 40, gripBottom + 12, red));
            AddLabels(children, frame, box);
            var result = new FireCabinetBuildResult();
            if (plan.Interior == null)
            {
                result.Warning = "箱腔容不下标准外观模型，已生成空箱；配置数量仍为两具。";
            }
            else
            {
                try
                {
                    var extinguishers = new List<Element>();
                    foreach (double sign in new[] { -1.0, 1.0 })
                    {
                        var innerFrame = new FireCabinetFrame(frame.Point(sign * plan.HalfSeparationMm,
                            box.DepthMm / 2, thickness), frame.Scale, plan.Parameters.HeadingDegrees);
                        extinguishers.Add(FireExtinguisherBuilder.Build(plan.Interior, innerFrame));
                    }

                    children.AddRange(extinguishers);
                    result.InteriorModelCount = 2;
                }
                catch (Exception exception)
                {
                    result.Warning = "箱内外观模型生成失败，已生成空箱：" + exception.Message;
                }
            }

            result.Cell = new CellHeaderElement(model, FireCabinetCatalog.CellName, origin, DMatrix3d.Identity, children);
            return result;
        }

        private static SolidKernelEntity RoundedBox(FireCabinetFrame frame, double left, double front,
            double bottom, double right, double rear, double top, double radius)
        {
            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            Action<double, double, double, double> line = (x1, y1, x2, y2) => profile.Add(
                CurvePrimitive.CreateLine(new DSegment3d(frame.Point(x1, y1, bottom), frame.Point(x2, y2, bottom))));
            Action<double, double, double> arc = (x, y, startAngle) => profile.Add(CurvePrimitive.CreateArc(
                new DEllipse3d(frame.Point(x, y, bottom), frame.Vector(radius, 0, 0), frame.Vector(0, radius, 0),
                    Angle.FromRadians(startAngle), Angle.FromRadians(Math.PI / 2))));
            line(left + radius, front, right - radius, front);
            arc(right - radius, front + radius, -Math.PI / 2);
            line(right, front + radius, right, rear - radius);
            arc(right - radius, rear - radius, 0);
            line(right - radius, rear, left + radius, rear);
            arc(left + radius, rear - radius, Math.PI / 2);
            line(left, rear - radius, left, front + radius);
            arc(left + radius, front + radius, Math.PI);
            return SolidPrimitiveFactory.Prism(profile, frame.Point(left + radius, front, bottom), frame.Vector(0, 0, top - bottom));
        }

        private static Element Box(FireCabinetFrame frame, double x1, double y1, double z1,
            double x2, double y2, double z2, uint color)
        {
            var body = SolidPrimitiveFactory.PolygonPrism(new[] { frame.Point(x1, y1, z1), frame.Point(x2, y1, z1),
                frame.Point(x2, y2, z1), frame.Point(x1, y2, z1) }, frame.Vector(0, 0, z2 - z1));
            return SolidPrimitiveFactory.Element(body, color);
        }

        private static void AddLabels(List<Element> children, FireCabinetFrame frame, FireCabinetPreset box)
        {
            double height = Math.Max(18, Math.Min(box.HeightMm * 0.1, 38));
            string english = "Fire Extinguisher Cabinet";
            double englishHeight = Math.Max(10, Math.Min(height * 0.55, box.WidthMm * 0.82 / (english.Length * 0.65)));
            children.Add(Text(english, frame, 0, -0.2, box.HeightMm * 0.62 + height * 1.65, englishHeight, true));
            children.Add(Text("灭火器箱", frame, 0, -0.2, box.HeightMm * 0.62, height, true));
            children.Add(Text("火警电话", frame, 0, -0.2, box.HeightMm * 0.16, Math.Max(12, Math.Min(height * 0.55, 20)), true));
            children.Add(Text("消防器材，严禁挪用", frame, 0, box.DepthMm / 2, box.HeightMm + 0.2,
                Math.Max(11, Math.Min(20, box.WidthMm / 12)), false));
        }

        internal static Element Text(string label, FireCabinetFrame frame, double x, double y, double z,
            double height, bool front)
        {
            var orientation = DMatrix3d.FromColumns(frame.Direction(1, 0, 0),
                front ? frame.Direction(0, 0, 1) : frame.Direction(0, 1, 0),
                front ? frame.Direction(0, -1, 0) : frame.Direction(0, 0, 1));
            return ModelTextFactory.Create(Session.Instance.GetActiveDgnModel(), label,
                frame.Point(x, y, z), orientation, height, frame.Scale,
                FireExtinguisherBuilder.Color(new[] { 255, 220, 0 }));
        }
    }
}
