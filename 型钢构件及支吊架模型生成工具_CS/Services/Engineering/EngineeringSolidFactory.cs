using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 把毫米实体的 <see cref="EngineeringPlan"/> 转成 Bentley 原生实体，并封装为一个普通单元。
    /// 只创建内存中的实体，不写模型；预览与确认由页面/预览会话统一管理。
    /// </summary>
    internal static class EngineeringSolidFactory
    {
        /// <summary>按点取原点与旋转角生成整组实体；失败时抛出带构件名称的中文异常。</summary>
        internal static Element Build(EngineeringPlan plan, DPoint3d origin)
        {
            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            if (!Finite(origin.X) || !Finite(origin.Y) || !Finite(origin.Z))
            {
                throw new InvalidOperationException("放置点无效。");
            }

            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
            {
                throw new InvalidOperationException("三维建模需要三维活动模型。");
            }

            var modelRef = Session.Instance.GetActiveDgnModelRef();
            double scale = model.GetModelInfo().UorPerMeter / 1000.0;
            if (!Finite(scale) || scale <= 0)
            {
                throw new InvalidOperationException("模型长度单位无效。");
            }

            var children = new List<Element>();
            foreach (EngineeringBody body in plan.Bodies)
            {
                try
                {
                    children.Add(BuildBody(body, modelRef, model, scale));
                }
                catch (Exception error)
                {
                    throw new InvalidOperationException("“" + body.Name + "”生成失败：" + error.Message, error);
                }
            }

            if (children.Count == 0)
            {
                throw new InvalidOperationException("没有生成任何三维实体。");
            }

            var cell = new CellHeaderElement(model, plan.CellName, DPoint3d.Zero, DMatrix3d.Identity, children);
            var heading = DTransform3d.Rotation(2, Angle.FromRadians(plan.HeadingDegrees * Math.PI / 180.0));
            var tilt = DTransform3d.Rotation(0, Angle.FromRadians(plan.RotateXDegrees * Math.PI / 180.0));
            var placement = DTransform3d.Multiply(DTransform3d.FromTranslation(origin), DTransform3d.Multiply(heading, tilt));
            cell.ApplyTransform(new TransformInfo(placement));
            return cell;
        }

        private static Element BuildBody(EngineeringBody body, DgnModelRef modelRef, DgnModel model, double scale)
        {
            SolidKernelEntity target;
            if (body.Add.Count == 0)
            {
                throw new InvalidOperationException("没有基体形状。");
            }

            target = Shape(body.Add[0], modelRef, scale);
            if (body.UnionAdd && body.Add.Count > 1)
            {
                var tools = new SolidKernelEntity[body.Add.Count - 1];
                for (int index = 1; index < body.Add.Count; index++)
                {
                    tools[index - 1] = Shape(body.Add[index], modelRef, scale);
                }

                var status = Modify.BooleanUnion(ref target, ref tools, tools.Length);
                if (status != BentleyStatus.Success)
                {
                    throw new InvalidOperationException("相并失败：" + status);
                }
            }

            foreach (EngineeringShape cutter in body.Cut)
            {
                var tools = new[] { Shape(cutter, modelRef, scale) };
                var status = Modify.BooleanSubtract(ref target, ref tools, 1);
                if (status != BentleyStatus.Success)
                {
                    if (body.BestEffortCut)
                    {
                        continue;
                    }

                    throw new InvalidOperationException("差集失败：" + status);
                }
            }

            Element element;
            var convert = Convert1.BodyToElement(out element, target, null, modelRef);
            if (convert != BentleyStatus.Success || element == null)
            {
                throw new InvalidOperationException("实体转 DGN 元素失败：" + convert);
            }

            var setter = new ElementPropertiesSetter();
            setter.SetColor(DgnColorMap.CreateElementColor(
                new RgbColorDef((byte)body.Red, (byte)body.Green, (byte)body.Blue), null, null,
                Session.Instance.GetActiveDgnFile()));
            if (!setter.Apply(element))
            {
                throw new InvalidOperationException("实体颜色设置失败。");
            }

            return element;
        }

        private static SolidKernelEntity Shape(EngineeringShape shape, DgnModelRef modelRef, double scale)
        {
            SolidPrimitive primitive;
            switch (shape.Kind)
            {
                case EngineeringShapeKind.Cone:
                    primitive = ConePrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.Revolve:
                    primitive = RevolvePrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.Extrude:
                    primitive = ExtrudePrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.HexPrism:
                    primitive = HexPrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.Torus:
                    primitive = TorusPrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.TorusArc:
                    primitive = TorusArcPrimitive(shape, scale);
                    break;
                case EngineeringShapeKind.Sweep:
                    return SweepBody(shape, modelRef, scale);
                default:
                    throw new InvalidOperationException("未知形状类型：" + shape.Kind);
            }

            if (primitive == null)
            {
                throw new InvalidOperationException("实体图元创建失败。");
            }

            SolidKernelEntity body;
            var status = Create.BodyFromSolidPrimitive(out body, primitive, modelRef);
            if (status != BentleyStatus.Success || body == null)
            {
                throw new InvalidOperationException("实体图元转实体失败：" + status);
            }

            return body;
        }

        private static DPoint3d P(EngineeringPoint point, double scale)
        {
            return new DPoint3d(point.X * scale, point.Y * scale, point.Z * scale);
        }

        private static SolidPrimitive ConePrimitive(EngineeringShape shape, double scale)
        {
            if (shape.RadiusStart <= 0 || shape.RadiusEnd <= 0)
            {
                throw new InvalidOperationException("圆台半径必须大于 0。");
            }

            DPoint3d a = P(shape.Start, scale);
            DPoint3d b = P(shape.End, scale);
            DVector3d axis = new DVector3d(b.X - a.X, b.Y - a.Y, b.Z - a.Z);
            double length = axis.Magnitude;
            if (length < 1e-9)
            {
                throw new InvalidOperationException("圆台轴线长度为 0。");
            }

            DVector3d unit = new DVector3d(axis.X / length, axis.Y / length, axis.Z / length);
            DVector3d helper = Math.Abs(unit.Z) > 0.9 ? new DVector3d(1, 0, 0) : new DVector3d(0, 0, 1);
            DVector3d xAxis = Normalize(Cross(helper, unit));
            DVector3d yAxis = Cross(unit, xAxis);
            return SolidPrimitive.CreateDgnCone(new DgnConeDetail(a, b, xAxis, yAxis,
                shape.RadiusStart * scale, shape.RadiusEnd * scale, true));
        }

        private static SolidPrimitive RevolvePrimitive(EngineeringShape shape, double scale)
        {
            if (shape.Points == null || shape.Points.Length < 3)
            {
                throw new InvalidOperationException("回转轮廓点不足。");
            }

            EngineeringPoint[] profilePoints = CounterClockwise(shape.Points);
            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            for (int index = 0; index < profilePoints.Length; index++)
            {
                EngineeringPoint start = profilePoints[index];
                EngineeringPoint end = profilePoints[(index + 1) % profilePoints.Length];
                profile.Add(CurvePrimitive.CreateLine(new DSegment3d(
                    new DPoint3d(start.X * scale, 0, start.Z * scale),
                    new DPoint3d(end.X * scale, 0, end.Z * scale))));
            }

            var axis = new DRay3d(DPoint3d.Zero, new DVector3d(0, 0, 1));
            return SolidPrimitive.CreateDgnRotationalSweep(
                new DgnRotationalSweepDetail(profile, axis, Angle.FromRadians(2 * Math.PI), true));
        }

        private static SolidPrimitive ExtrudePrimitive(EngineeringShape shape, double scale)
        {
            if (shape.Points == null || shape.Points.Length < 3)
            {
                throw new InvalidOperationException("拉伸轮廓点不足。");
            }

            EngineeringPoint[] outline;
            EngineeringPoint?[] middles;
            Orient(shape.Points, shape.Direction, shape.ArcMiddles, out outline, out middles);
            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            for (int index = 0; index < outline.Length; index++)
            {
                AddSegment(profile, outline[index], outline[(index + 1) % outline.Length],
                    middles == null ? null : middles[index], scale);
            }

            var direction = new DVector3d(shape.Direction.X * scale, shape.Direction.Y * scale,
                shape.Direction.Z * scale);
            return SolidPrimitive.CreateDgnExtrusion(new DgnExtrusionDetail(profile, direction, true));
        }

        /// <summary>按拉伸方向统一轮廓朝向，并把配套的圆弧中间点一起反向。</summary>
        private static void Orient(
            EngineeringPoint[] points, EngineeringPoint direction, EngineeringPoint?[] arcMiddles,
            out EngineeringPoint[] outline, out EngineeringPoint?[] middles)
        {
            outline = points;
            middles = arcMiddles;
            double normalX = 0;
            double normalY = 0;
            double normalZ = 0;
            for (int index = 0; index < points.Length; index++)
            {
                EngineeringPoint a = points[index];
                EngineeringPoint b = points[(index + 1) % points.Length];
                normalX += (a.Y - b.Y) * (a.Z + b.Z);
                normalY += (a.Z - b.Z) * (a.X + b.X);
                normalZ += (a.X - b.X) * (a.Y + b.Y);
            }

            bool reverse = normalX * direction.X + normalY * direction.Y + normalZ * direction.Z < 0;
            if (!reverse)
            {
                return;
            }

            var reversed = new EngineeringPoint[points.Length];
            for (int index = 0; index < points.Length; index++)
            {
                reversed[index] = points[points.Length - 1 - index];
            }

            outline = reversed;
            if (arcMiddles == null)
            {
                return;
            }

            middles = new EngineeringPoint?[points.Length];
            for (int index = 0; index < points.Length; index++)
            {
                middles[index] = arcMiddles[(points.Length - 2 - index + points.Length) % points.Length];
            }
        }

        /// <summary>加入一段轮廓：有圆弧中间点时用真圆弧，否则用直线。</summary>
        private static void AddSegment(
            CurveVector curve, EngineeringPoint start, EngineeringPoint end,
            EngineeringPoint? middle, double scale)
        {
            if (middle.HasValue)
            {
                DEllipse3d arc;
                if (!DEllipse3d.TryCircularArcFromStartMiddleEnd(
                    P(start, scale), P(middle.Value, scale), P(end, scale), out arc))
                {
                    throw new InvalidOperationException("无法由三点构造真圆弧。");
                }

                curve.Add(CurvePrimitive.CreateArc(arc));
                return;
            }

            curve.Add(CurvePrimitive.CreateLine(new DSegment3d(P(start, scale), P(end, scale))));
        }

        private static SolidPrimitive HexPrimitive(EngineeringShape shape, double scale)
        {
            DPoint3d a = P(shape.Start, scale);
            DPoint3d b = P(shape.End, scale);
            DVector3d axis = new DVector3d(b.X - a.X, b.Y - a.Y, b.Z - a.Z);
            double length = axis.Magnitude;
            if (length < 1e-9)
            {
                throw new InvalidOperationException("六棱柱轴线长度为 0。");
            }

            DVector3d unit = new DVector3d(axis.X / length, axis.Y / length, axis.Z / length);
            DVector3d helper = Math.Abs(unit.Z) > 0.9 ? new DVector3d(1, 0, 0) : new DVector3d(0, 0, 1);
            DVector3d xAxis = Normalize(Cross(helper, unit));
            DVector3d yAxis = Cross(unit, xAxis);

            double radius = shape.RadiusStart * scale;
            var vertices = new DPoint3d[6];
            for (int index = 0; index < 6; index++)
            {
                double angle = index * Math.PI / 3.0;
                vertices[index] = new DPoint3d(
                    a.X + xAxis.X * radius * Math.Cos(angle) + yAxis.X * radius * Math.Sin(angle),
                    a.Y + xAxis.Y * radius * Math.Cos(angle) + yAxis.Y * radius * Math.Sin(angle),
                    a.Z + xAxis.Z * radius * Math.Cos(angle) + yAxis.Z * radius * Math.Sin(angle));
            }

            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            for (int index = 0; index < 6; index++)
            {
                profile.Add(CurvePrimitive.CreateLine(new DSegment3d(
                    vertices[index], vertices[(index + 1) % 6])));
            }

            var direction = new DVector3d(b.X - a.X, b.Y - a.Y, b.Z - a.Z);
            return SolidPrimitive.CreateDgnExtrusion(new DgnExtrusionDetail(profile, direction, true));
        }

        private static SolidPrimitive TorusPrimitive(EngineeringShape shape, double scale)
        {
            DPoint3d center = P(shape.Start, scale);
            double major = shape.MajorRadius * scale;
            double minor = shape.MinorRadius * scale;
            if (major <= 0 || minor <= 0 || minor >= major)
            {
                throw new InvalidOperationException("圆环半径不匹配。");
            }

            return SolidPrimitive.CreateDgnTorusPipe(new DgnTorusPipeDetail(center,
                new DVector3d(1, 0, 0), new DVector3d(0, 1, 0), major, minor, 2 * Math.PI, true));
        }

        private static SolidPrimitive TorusArcPrimitive(EngineeringShape shape, double scale)
        {
            DPoint3d center = P(shape.Start, scale);
            double major = shape.MajorRadius * scale;
            double minor = shape.MinorRadius * scale;
            double sweep = shape.RadiusStart;
            if (major <= 0 || minor <= 0 || minor >= major)
            {
                throw new InvalidOperationException("圆环半径不匹配。");
            }

            if (sweep <= 0 || sweep > 2 * Math.PI)
            {
                throw new InvalidOperationException("圆环扫掠角无效。");
            }

            DVector3d xAxis = Normalize(new DVector3d(
                shape.AxisX.X * scale, shape.AxisX.Y * scale, shape.AxisX.Z * scale));
            DVector3d yAxis = Normalize(new DVector3d(
                shape.AxisY.X * scale, shape.AxisY.Y * scale, shape.AxisY.Z * scale));
            return SolidPrimitive.CreateDgnTorusPipe(new DgnTorusPipeDetail(
                center, xAxis, yAxis, major, minor, sweep, true));
        }

        private static SolidKernelEntity SweepBody(EngineeringShape shape, DgnModelRef modelRef, double scale)
        {
            if (shape.Points == null || shape.Points.Length < 2)
            {
                throw new InvalidOperationException("扫掠路径点不足。");
            }

            double radius = shape.RadiusStart * scale;
            if (radius <= 0)
            {
                throw new InvalidOperationException("扫掠圆截面半径无效。");
            }

            DPoint3d first = P(shape.Points[0], scale);
            DVector3d tangent;
            if (shape.ArcMiddles != null && shape.ArcMiddles[0].HasValue)
            {
                tangent = ArcStartTangent(
                    first, P(shape.ArcMiddles[0].Value, scale), P(shape.Points[1], scale));
            }
            else
            {
                DPoint3d second = P(shape.Points[1], scale);
                tangent = new DVector3d(second.X - first.X, second.Y - first.Y, second.Z - first.Z);
            }

            var disk = CurveVector.CreateDisk(DEllipse3d.FromCenterRadiusNormal(first, radius, tangent),
                CurveVector.BoundaryType.Outer);

            var path = CurveVector.Create(CurveVector.BoundaryType.Open);
            for (int index = 0; index + 1 < shape.Points.Length; index++)
            {
                EngineeringPoint? middle = shape.ArcMiddles == null ? null : shape.ArcMiddles[index];
                AddSegment(path, shape.Points[index], shape.Points[index + 1], middle, scale);
            }

            SolidKernelEntity body;
            var status = Create.BodyFromSweep(out body, disk, path, modelRef,
                false, true, false, null, null, null, null);
            if (status != BentleyStatus.Success || body == null)
            {
                throw new InvalidOperationException("路径扫掠失败：" + status);
            }

            return body;
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        /// <summary>
        /// 圆弧起点的真实切向：由三点定出圆心，切向垂直于半径并在圆弧平面内，
        /// 方向取指向圆弧中间点的一侧。扫掠截面必须按此切向放置，不能用弦方向。
        /// </summary>
        private static DVector3d ArcStartTangent(DPoint3d start, DPoint3d middle, DPoint3d end)
        {
            double ax = middle.X - start.X;
            double ay = middle.Y - start.Y;
            double az = middle.Z - start.Z;
            double bx = end.X - start.X;
            double by = end.Y - start.Y;
            double bz = end.Z - start.Z;

            double nx = ay * bz - az * by;
            double ny = az * bx - ax * bz;
            double nz = ax * by - ay * bx;
            double normalLength = Math.Sqrt(nx * nx + ny * ny + nz * nz);
            if (normalLength < 1e-12)
            {
                throw new InvalidOperationException("圆弧三点共线，无法确定切向。");
            }

            double aa = ax * ax + ay * ay + az * az;
            double bb = bx * bx + by * by + bz * bz;
            double denominator = 2.0 * normalLength * normalLength;

            // center - start = (|a|²·(b×n) + |b|²·(n×a)) / (2|n|²)
            double cbx = by * nz - bz * ny;
            double cby = bz * nx - bx * nz;
            double cbz = bx * ny - by * nx;
            double cax = ny * az - nz * ay;
            double cay = nz * ax - nx * az;
            double caz = nx * ay - ny * ax;

            double rx = (aa * cbx + bb * cax) / denominator;
            double ry = (aa * cby + bb * cay) / denominator;
            double rz = (aa * cbz + bb * caz) / denominator;

            // tangent = n × r
            double tx = ny * rz - nz * ry;
            double ty = nz * rx - nx * rz;
            double tz = nx * ry - ny * rx;
            double length = Math.Sqrt(tx * tx + ty * ty + tz * tz);
            if (length < 1e-12)
            {
                throw new InvalidOperationException("圆弧切向退化。");
            }

            if (tx * ax + ty * ay + tz * az < 0)
            {
                tx = -tx;
                ty = -ty;
                tz = -tz;
            }

            return new DVector3d(tx / length, ty / length, tz / length);
        }

        private static DVector3d Cross(DVector3d a, DVector3d b)
        {
            return new DVector3d(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);
        }

        private static DVector3d Normalize(DVector3d vector)
        {
            double length = vector.Magnitude;
            if (length < 1e-12)
            {
                throw new InvalidOperationException("无法构造正交方向。");
            }

            return new DVector3d(vector.X / length, vector.Y / length, vector.Z / length);
        }

        /// <summary>回转轮廓在 (半径, 高度) 平面内统一为逆时针，避免回转方向相反。</summary>
        private static EngineeringPoint[] CounterClockwise(EngineeringPoint[] profile)
        {
            double area = 0;
            for (int index = 0; index < profile.Length; index++)
            {
                EngineeringPoint a = profile[index];
                EngineeringPoint b = profile[(index + 1) % profile.Length];
                area += a.X * b.Z - b.X * a.Z;
            }

            if (area >= 0)
            {
                return profile;
            }

            var reversed = new EngineeringPoint[profile.Length];
            for (int index = 0; index < profile.Length; index++)
            {
                reversed[index] = profile[profile.Length - 1 - index];
            }

            return reversed;
        }
    }
}
