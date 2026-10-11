using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 将独立外观配方转成原生实体；不写入模型，返回命名嵌套单元。
    /// </summary>
    internal static class FireExtinguisherBuilder
    {
        internal static Element Build(FireExtinguisherRecipe recipe, FireCabinetFrame frame)
        {
            var model = Session.Instance.GetActiveDgnModel();
            var children = new List<Element>();
            foreach (FireGeometryPart part in recipe.Parts)
            {
                try
                {
                    SolidPrimitive primitive = Primitive(part, frame);
                    if (primitive == null)
                    {
                        throw new InvalidOperationException("原生实体创建失败。");
                    }

                    Element element = DraftingElementSchema.ToElement(model, primitive, null);
                    if (element == null)
                    {
                        throw new InvalidOperationException("实体转换失败。");
                    }

                    var setter = new ElementPropertiesSetter();
                    setter.SetColor(Color(part.Color));
                    if (!setter.Apply(element))
                    {
                        throw new InvalidOperationException("构件颜色设置失败。");
                    }

                    children.Add(element);
                }
                catch (Exception exception)
                {
                    throw new InvalidOperationException("灭火器构件“" + part.Name + "”生成失败：" + exception.Message, exception);
                }
            }

            return new CellHeaderElement(model, recipe.CellName, frame.Point(0, 0, 0), DMatrix3d.Identity, children);
        }

        internal static uint Color(int[] rgb)
        {
            return DgnColorMap.CreateElementColor(new RgbColorDef((byte)rgb[0], (byte)rgb[1], (byte)rgb[2]),
                null, null, Session.Instance.GetActiveDgnFile());
        }

        private static SolidPrimitive Primitive(FireGeometryPart part, FireCabinetFrame frame)
        {
            switch (part.Kind)
            {
                case "cone":
                    return Cone(part, frame);
                case "box":
                    return TiltedBox(part, frame);
                case "torus":
                    return SolidPrimitive.CreateDgnTorusPipe(new DgnTorusPipeDetail(frame.Point(part.Center),
                        frame.Direction(1, 0, 0), frame.Direction(0, 0, 1), part.MajorRadiusMm * frame.Scale,
                        part.MinorRadiusMm * frame.Scale, 2 * Math.PI, true));
                case "rounded_bottle":
                    return Bottle(part, frame);
                case "hose":
                    return Hose(part, frame);
                default:
                    throw new InvalidOperationException("未知灭火器几何配方：" + part.Kind);
            }
        }

        private static SolidPrimitive Cone(FireGeometryPart part, FireCabinetFrame frame)
        {
            double dx = part.End[0] - part.Start[0];
            double dy = part.End[1] - part.Start[1];
            double dz = part.End[2] - part.Start[2];
            double length = Math.Sqrt(dx * dx + dy * dy + dz * dz);
            if (length < 1e-9)
            {
                throw new InvalidOperationException("圆锥轴线无效。");
            }
            dx /= length;
            dy /= length;
            dz /= length;
            double vx = Math.Abs(dz) > 0.9 ? 1 : -dy;
            double vy = Math.Abs(dz) > 0.9 ? 0 : dx;
            double vz = 0;
            // 对近竖轴的圆锥也投影至轴线法平面。
            double dot = vx * dx + vy * dy + vz * dz;
            vx -= dot * dx;
            vy -= dot * dy;
            vz -= dot * dz;
            double perpendicularLength = Math.Sqrt(vx * vx + vy * vy + vz * vz);
            vx /= perpendicularLength;
            vy /= perpendicularLength;
            vz /= perpendicularLength;
            return SolidPrimitive.CreateDgnCone(new DgnConeDetail(frame.Point(part.Start), frame.Point(part.End),
                frame.Direction(vx, vy, vz), frame.Direction(dy * vz - dz * vy, dz * vx - dx * vz, dx * vy - dy * vx),
                part.StartRadiusMm * frame.Scale, part.EndRadiusMm * frame.Scale, true));
        }

        private static SolidPrimitive TiltedBox(FireGeometryPart part, FireCabinetFrame frame)
        {
            double tilt = part.TiltDegrees * Math.PI / 180;
            double cosine = Math.Cos(tilt);
            double sine = Math.Sin(tilt);
            double[] size = part.Size;
            double[] center = part.Center;
            double x = center[0] - (size[0] * cosine + size[2] * sine) / 2;
            double y = center[1] - size[1] / 2;
            double z = center[2] - (-size[0] * sine + size[2] * cosine) / 2;
            return SolidPrimitive.CreateDgnBox(new DgnBoxDetail(frame.Point(x, y, z),
                frame.Point(x + size[2] * sine, y, z + size[2] * cosine),
                frame.Direction(cosine, 0, -sine), frame.Direction(0, 1, 0),
                size[0] * frame.Scale, size[1] * frame.Scale, size[0] * frame.Scale, size[1] * frame.Scale, true));
        }

        private static SolidPrimitive Bottle(FireGeometryPart part, FireCabinetFrame frame)
        {
            double radius = part.RadiusMm;
            double fillet = part.FilletMm;
            double bottom = part.BottomMm;
            double top = part.TopMm;
            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(frame.Point(0, 0, bottom), frame.Point(radius - fillet, 0, bottom))));
            profile.Add(CurvePrimitive.CreateArc(new DEllipse3d(frame.Point(radius - fillet, 0, bottom + fillet),
                frame.Vector(fillet, 0, 0), frame.Vector(0, 0, fillet), Angle.FromRadians(-Math.PI / 2), Angle.FromRadians(Math.PI / 2))));
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(frame.Point(radius, 0, bottom + fillet), frame.Point(radius, 0, top - fillet))));
            profile.Add(CurvePrimitive.CreateArc(new DEllipse3d(frame.Point(radius - fillet, 0, top - fillet),
                frame.Vector(fillet, 0, 0), frame.Vector(0, 0, fillet), Angle.FromRadians(0), Angle.FromRadians(Math.PI / 2))));
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(frame.Point(radius - fillet, 0, top), frame.Point(0, 0, top))));
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(frame.Point(0, 0, top), frame.Point(0, 0, bottom))));
            return SolidPrimitive.CreateDgnRotationalSweep(new DgnRotationalSweepDetail(profile,
                new DRay3d(frame.Point(0, 0, 0), frame.Direction(0, 0, 1)), Angle.FromRadians(2 * Math.PI), true));
        }

        private static SolidPrimitive Hose(FireGeometryPart part, FireCabinetFrame frame)
        {
            var sections = new CurveVector[part.Points.Length];
            for (int index = 0; index < sections.Length; index++)
            {
                double[] before = part.Points[Math.Max(0, index - 1)];
                double[] after = part.Points[Math.Min(sections.Length - 1, index + 1)];
                double dx = after[0] - before[0];
                double dz = after[2] - before[2];
                double length = Math.Sqrt(dx * dx + dz * dz);
                if (length <= 1e-9)
                {
                    throw new InvalidOperationException("软管中心线有重复点。");
                }
                sections[index] = CurveVector.Create(CurveVector.BoundaryType.Outer);
                sections[index].Add(CurvePrimitive.CreateArc(new DEllipse3d(frame.Point(part.Points[index]),
                    frame.Vector(0, part.RadiusMm, 0), frame.Vector(-dz / length * part.RadiusMm, 0, dx / length * part.RadiusMm),
                    Angle.FromRadians(0), Angle.FromRadians(2 * Math.PI))));
            }

            return SolidPrimitive.CreateDgnRuledSweep(new DgnRuledSweepDetail(sections, true));
        }
    }
}
