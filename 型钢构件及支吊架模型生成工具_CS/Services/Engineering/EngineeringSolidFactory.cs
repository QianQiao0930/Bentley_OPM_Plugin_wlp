using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
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
                case EngineeringShapeKind.Loft:
                    return LoftBody(shape, modelRef, scale);
                case EngineeringShapeKind.SplineSweep:
                    return SplineBody(shape, modelRef, scale, false);
                case EngineeringShapeKind.SplineBand:
                    return SplineBody(shape, modelRef, scale, true);
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

        /// <summary>加入一段轮廓：有圆弧中间点时用真圆弧；三点接近共线（直线段）时退回直线。</summary>
        private static void AddSegment(
            CurveVector curve, EngineeringPoint start, EngineeringPoint end,
            EngineeringPoint? middle, double scale)
        {
            if (middle.HasValue)
            {
                DEllipse3d arc;
                if (DEllipse3d.TryCircularArcFromStartMiddleEnd(
                    P(start, scale), P(middle.Value, scale), P(end, scale), out arc))
                {
                    curve.Add(CurvePrimitive.CreateArc(arc));
                    return;
                }

                // 共线或近共线的三个点构不成圆弧，这一段本来就是直线。
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

        /// <summary>放样的截面目标间距（mm）：越小越贴合路径，放样行数越多。</summary>
        private const double LoftStepMm = 2.5;

        /// <summary>单段路径最多细分出的行数，避免长直线段产生上百行。</summary>
        private const int LoftMaxSubSteps = 24;

        /// <summary>
        /// 圆截面沿路径放样：每个截面都是真圆，坐标架由路径平面法向显式定死，
        /// 得到的是**单一**光滑管面，不会像逐段扫掠那样出现一圈圈横向棱线。
        /// 内核拒绝放样时退回逐段圆弧扫掠（几何相同，只是分段处留下棱线）。
        /// </summary>
        private static SolidKernelEntity LoftBody(
            EngineeringShape shape, DgnModelRef modelRef, double scale)
        {
            string reason;
            try
            {
                SolidKernelEntity body;
                if (TryLoftBody(shape, modelRef, scale, out body, out reason))
                {
                    return body;
                }
            }
            catch (Exception error)
            {
                reason = error.GetType().Name + "：" + error.Message;
            }

            // 放样不可用时退回扫掠；写一行日志，便于宿主判断到底走了哪条路线。
            EngineeringLog.Write("圈体放样未成功，退回逐段扫掠：" + reason);
            return SweepBody(shape, modelRef, scale);
        }

        private static bool TryLoftBody(
            EngineeringShape shape, DgnModelRef modelRef, double scale,
            out SolidKernelEntity body, out string reason)
        {
            body = null;
            if (shape.Points == null || shape.Points.Length < 2)
            {
                reason = "路径点不足";
                return false;
            }

            double radius = shape.RadiusStart * scale;
            if (!(radius > 0) || !Finite(radius))
            {
                reason = "截面半径无效";
                return false;
            }

            var plane = new DVector3d(shape.AxisX.X, shape.AxisX.Y, shape.AxisX.Z);
            if (plane.Magnitude < 1e-9)
            {
                reason = "截面基准方向无效";
                return false;
            }

            DVector3d planeNormal = Normalize(plane);

            var segments = new List<LoftSegment>(shape.Points.Length - 1);
            for (int index = 0; index + 1 < shape.Points.Length; index++)
            {
                EngineeringPoint? middle = shape.ArcMiddles == null ? null : shape.ArcMiddles[index];
                DPoint3d start = P(shape.Points[index], scale);
                DPoint3d end = P(shape.Points[index + 1], scale);
                segments.Add(middle.HasValue
                    ? LoftSegment.Arc(start, P(middle.Value, scale), end)
                    : LoftSegment.Line(start, end));
            }

            var sections = new List<CurveVector>();
            double step = LoftStepMm * scale;
            for (int index = 0; index < segments.Count; index++)
            {
                LoftSegment segment = segments[index];
                int steps = Math.Max(1, (int)Math.Ceiling(segment.Length / step));
                if (steps > LoftMaxSubSteps)
                {
                    steps = LoftMaxSubSteps;
                }

                // 段终点交给下一段（末段终点单独补），避免出现重复截面使放样退化。
                for (int sub = 0; sub < steps; sub++)
                {
                    DPoint3d center;
                    DVector3d tangent;
                    segment.Evaluate((double)sub / steps, out center, out tangent);
                    CurveVector section = SectionCurve(center, tangent, planeNormal, radius);
                    if (section == null)
                    {
                        reason = "第 " + sections.Count + " 个截面构造失败";
                        return false;
                    }

                    sections.Add(section);
                }
            }

            DPoint3d tail;
            DVector3d tailTangent;
            segments[segments.Count - 1].Evaluate(1.0, out tail, out tailTangent);
            CurveVector tailSection = SectionCurve(tail, tailTangent, planeNormal, radius);
            if (tailSection == null)
            {
                reason = "末截面构造失败";
                return false;
            }

            sections.Add(tailSection);

            var status = Create.BodyFromLoft(out body, sections.ToArray(), sections.Count,
                new CurveVector[0], 0, modelRef, false, false);
            if (status != BentleyStatus.Success || body == null)
            {
                reason = "放样返回 " + status + "（共 " + sections.Count + " 个截面）";
                return false;
            }

            reason = null;
            return true;
        }

        /// <summary>
        /// 单个放样截面：圆平面由切向与路径平面法向确定（0° 方向固定，放样不扭转）。
        /// </summary>
        private static CurveVector SectionCurve(
            DPoint3d center, DVector3d tangent, DVector3d planeNormal, double radius)
        {
            DVector3d axis = Normalize(tangent);

            // 平面法向去掉沿切向的分量，作为截面的 0° 方向。
            double along = planeNormal.X * axis.X + planeNormal.Y * axis.Y + planeNormal.Z * axis.Z;
            var u = new DVector3d(
                planeNormal.X - axis.X * along,
                planeNormal.Y - axis.Y * along,
                planeNormal.Z - axis.Z * along);
            if (u.Magnitude < 1e-6)
            {
                return null;
            }

            u = Normalize(u);
            DVector3d v = Cross(axis, u);
            var ellipse = new DEllipse3d(center,
                new DVector3d(u.X * radius, u.Y * radius, u.Z * radius),
                new DVector3d(v.X * radius, v.Y * radius, v.Z * radius));
            ellipse.SweepAngle = Angle.FromRadians(2.0 * Math.PI);
            return CurveVector.CreateDisk(ellipse, CurveVector.BoundaryType.Outer);
        }

        /// <summary>放样用的一段路径：真圆弧（三点定圆）或直线，可按参数取点与切向。</summary>
        private struct LoftSegment
        {
            private bool isLine;
            private DPoint3d start;
            private DPoint3d end;
            private DPoint3d center;
            private DVector3d radiusAxis;
            private DVector3d tangentAxis;
            private double radius;
            private double sweep;

            internal double Length;

            internal static LoftSegment Line(DPoint3d from, DPoint3d to)
            {
                return new LoftSegment
                {
                    isLine = true,
                    start = from,
                    end = to,
                    Length = Distance(from, to)
                };
            }

            internal static LoftSegment Arc(DPoint3d from, DPoint3d through, DPoint3d to)
            {
                var first = new DVector3d(through.X - from.X, through.Y - from.Y, through.Z - from.Z);
                var second = new DVector3d(to.X - from.X, to.Y - from.Y, to.Z - from.Z);
                DVector3d normal = Cross(first, second);
                double normalLength = normal.Magnitude;
                double firstLength = first.Magnitude;
                double secondLength = second.Magnitude;

                // 三点共线（或近共线）时本来就该是直线。
                if (normalLength < 1e-9 || firstLength < 1e-9 || secondLength < 1e-9 ||
                    normalLength < 1e-6 * firstLength * secondLength)
                {
                    return Line(from, to);
                }

                double aa = firstLength * firstLength;
                double bb = secondLength * secondLength;
                double denominator = 2.0 * normalLength * normalLength;

                // center - from = (|first|²·(second×n) + |second|²·(n×first)) / (2|n|²)
                var secondCrossNormal = Cross(second, normal);
                var normalCrossFirst = Cross(normal, first);
                var center = new DPoint3d(
                    from.X + (aa * secondCrossNormal.X + bb * normalCrossFirst.X) / denominator,
                    from.Y + (aa * secondCrossNormal.Y + bb * normalCrossFirst.Y) / denominator,
                    from.Z + (aa * secondCrossNormal.Z + bb * normalCrossFirst.Z) / denominator);

                var unitNormal = Normalize(normal);
                var radiusAxis = new DVector3d(
                    (from.X - center.X) / Distance(center, from),
                    (from.Y - center.Y) / Distance(center, from),
                    (from.Z - center.Z) / Distance(center, from));
                double radius = Distance(center, from);
                DVector3d tangentAxis = Cross(unitNormal, radiusAxis);

                double throughAngle = AngleOf(through, center, radiusAxis, tangentAxis);
                double endAngle = AngleOf(to, center, radiusAxis, tangentAxis);
                double sweep = endAngle >= throughAngle ? endAngle : endAngle - 2.0 * Math.PI;

                return new LoftSegment
                {
                    isLine = false,
                    start = from,
                    end = to,
                    center = center,
                    radiusAxis = radiusAxis,
                    tangentAxis = tangentAxis,
                    radius = radius,
                    sweep = sweep,
                    Length = Math.Abs(sweep) * radius
                };
            }

            internal void Evaluate(double t, out DPoint3d point, out DVector3d tangent)
            {
                if (isLine)
                {
                    point = new DPoint3d(
                        start.X + (end.X - start.X) * t,
                        start.Y + (end.Y - start.Y) * t,
                        start.Z + (end.Z - start.Z) * t);
                    tangent = Normalize(new DVector3d(
                        end.X - start.X, end.Y - start.Y, end.Z - start.Z));
                    return;
                }

                double angle = sweep * t;
                double cosine = Math.Cos(angle);
                double sine = Math.Sin(angle);
                point = new DPoint3d(
                    center.X + radius * (radiusAxis.X * cosine + tangentAxis.X * sine),
                    center.Y + radius * (radiusAxis.Y * cosine + tangentAxis.Y * sine),
                    center.Z + radius * (radiusAxis.Z * cosine + tangentAxis.Z * sine));

                double direction = sweep >= 0 ? 1.0 : -1.0;
                tangent = Normalize(new DVector3d(
                    direction * (-radiusAxis.X * sine + tangentAxis.X * cosine),
                    direction * (-radiusAxis.Y * sine + tangentAxis.Y * cosine),
                    direction * (-radiusAxis.Z * sine + tangentAxis.Z * cosine)));
            }

            private static double AngleOf(
                DPoint3d point, DPoint3d center, DVector3d radiusAxis, DVector3d tangentAxis)
            {
                double x = point.X - center.X;
                double y = point.Y - center.Y;
                double z = point.Z - center.Z;
                double cosine = x * radiusAxis.X + y * radiusAxis.Y + z * radiusAxis.Z;
                double sine = x * tangentAxis.X + y * tangentAxis.Y + z * tangentAxis.Z;
                double angle = Math.Atan2(sine, cosine);
                return angle < 0 ? angle + 2.0 * Math.PI : angle;
            }
        }

        private static double Distance(DPoint3d a, DPoint3d b)
        {
            double x = a.X - b.X;
            double y = a.Y - b.Y;
            double z = a.Z - b.Z;
            return Math.Sqrt(x * x + y * y + z * z);
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }
        /// <summary>
        /// 沿“拟合点 → 光滑插值样条”生成的路径扫掠：绳圈用圆截面，鸡心环环带用矩形截面。
        /// 样条为真正的 B 样条（MSInterpolationCurve），不会把曲线拆成折线。
        /// </summary>
        private static SolidKernelEntity SplineBody(
            EngineeringShape shape, DgnModelRef modelRef, double scale, bool band)
        {
            if (shape.Points == null || shape.Points.Length < 3)
            {
                throw new InvalidOperationException("光滑路径拟合点不足。");
            }

            var fit = new List<DPoint3d>(shape.Points.Length);
            foreach (EngineeringPoint point in shape.Points)
            {
                fit.Add(P(point, scale));
            }

            DPoint3d start = fit[0];
            DVector3d tangent = StartDirection(fit);
            CurveVector profile;
            DVector3d lockDirection = DVector3d.Zero;
            bool hasLock = false;

            if (band)
            {
                double halfWidth = shape.RadiusStart * scale / 2.0;
                double thickness = shape.RadiusEnd * scale;
                if (halfWidth <= 0 || thickness <= 0)
                {
                    throw new InvalidOperationException("环带宽度或厚度无效。");
                }

                DVector3d outOfPlane = Normalize(new DVector3d(
                    shape.AxisX.X, shape.AxisX.Y, shape.AxisX.Z));
                // 环带贴在路径外侧（厚度沿路径平面外法向指向环外）。
                DVector3d inPlane = Normalize(Cross(tangent, outOfPlane));
                var corners = new[]
                {
                    Combine(start, inPlane, 0.0, outOfPlane, -halfWidth),
                    Combine(start, inPlane, thickness, outOfPlane, -halfWidth),
                    Combine(start, inPlane, thickness, outOfPlane, halfWidth),
                    Combine(start, inPlane, 0.0, outOfPlane, halfWidth)
                };

                profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
                for (int index = 0; index < 4; index++)
                {
                    profile.Add(CurvePrimitive.CreateLine(new DSegment3d(
                        corners[index], corners[(index + 1) % 4])));
                }

                lockDirection = outOfPlane;
                hasLock = true;
            }
            else
            {
                double radius = shape.RadiusStart * scale;
                if (radius <= 0)
                {
                    throw new InvalidOperationException("扫掠圆截面半径无效。");
                }

                profile = CurveVector.CreateDisk(
                    DEllipse3d.FromCenterRadiusNormal(start, radius, tangent), CurveVector.BoundaryType.Outer);
            }

            // 直接用控制点构造 B 样条，避免 ConvertToBspline 在宿主内返回空引用。
            CurvePrimitive spline;
            try
            {
                spline = CreateSplinePath(fit);
            }
            catch (Exception error)
            {
                throw new InvalidOperationException("光滑路径构造失败：" + error.Message, error);
            }

            var path = CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(spline);

            SolidKernelEntity body;
            BentleyStatus status;
            if (hasLock)
            {
                status = Create.BodyFromSweep(out body, profile, path, modelRef,
                    false, true, false, lockDirection, null, null, null);
            }
            else
            {
                status = Create.BodyFromSweep(out body, profile, path, modelRef,
                    false, true, false, null, null, null, null);
            }

            if (status != BentleyStatus.Success || body == null)
            {
                // 内核不接受样条路径扫掠时，用同一组截面放样，表面仍然连续光滑。
                return LoftBody(shape, modelRef, scale, band);
            }

            return body;
        }

        /// <summary>沿拟合点逐点建截面后放样；作为光滑扫掠失败时的后备路径。</summary>
        private static SolidKernelEntity LoftBody(
            EngineeringShape shape, DgnModelRef modelRef, double scale, bool band)
        {
            int count = shape.Points.Length;
            if (count < 2)
            {
                throw new InvalidOperationException("放样截面不足。");
            }

            var sections = new CurveVector[count];
            for (int index = 0; index < count; index++)
            {
                DPoint3d center = P(shape.Points[index], scale);
                int previous = index == 0 ? 0 : index - 1;
                int next = index == count - 1 ? count - 1 : index + 1;
                DPoint3d before = P(shape.Points[previous], scale);
                DPoint3d after = P(shape.Points[next], scale);
                DVector3d tangent = Normalize(new DVector3d(
                    after.X - before.X, after.Y - before.Y, after.Z - before.Z));

                if (!band)
                {
                    double radius = shape.RadiusStart * scale;
                    sections[index] = CurveVector.CreateDisk(
                        DEllipse3d.FromCenterRadiusNormal(center, radius, tangent),
                        CurveVector.BoundaryType.Outer);
                    continue;
                }

                double halfWidth = shape.RadiusStart * scale / 2.0;
                double thickness = shape.RadiusEnd * scale;
                DVector3d outOfPlane = Normalize(new DVector3d(
                    shape.AxisX.X, shape.AxisX.Y, shape.AxisX.Z));
                DVector3d inPlane = Normalize(Cross(tangent, outOfPlane));
                var corners = new[]
                {
                    Combine(center, inPlane, 0.0, outOfPlane, -halfWidth),
                    Combine(center, inPlane, thickness, outOfPlane, -halfWidth),
                    Combine(center, inPlane, thickness, outOfPlane, halfWidth),
                    Combine(center, inPlane, 0.0, outOfPlane, halfWidth)
                };

                var section = CurveVector.Create(CurveVector.BoundaryType.Outer);
                for (int corner = 0; corner < 4; corner++)
                {
                    section.Add(CurvePrimitive.CreateLine(new DSegment3d(
                        corners[corner], corners[(corner + 1) % 4])));
                }

                sections[index] = section;
            }

            SolidKernelEntity body;
            var status = Create.BodyFromLoft(out body, sections, sections.Length,
                new CurveVector[0], 0, modelRef, false, false);
            if (status != BentleyStatus.Success || body == null)
            {
                throw new InvalidOperationException("光滑路径扫掠与放样均失败：" + status);
            }

            return body;
        }

        private static DVector3d StartDirection(IList<DPoint3d> points)
        {
            DPoint3d first = points[0];
            for (int index = 1; index < points.Count; index++)
            {
                DPoint3d next = points[index];
                var direction = new DVector3d(next.X - first.X, next.Y - first.Y, next.Z - first.Z);
                if (direction.Magnitude > 1e-9)
                {
                    return Normalize(direction);
                }
            }

            throw new InvalidOperationException("路径起点切线无效。");
        }

        /// <summary>
        /// 用控制点、单位权重与钳位均匀节点向量直接构造三次 B 样条曲线（clamped，端点过首末控制点）。
        /// 不经过插值曲线转换，避免宿主内 ConvertToBspline 返回空引用。
        /// </summary>
        private static CurvePrimitive CreateSplinePath(IList<DPoint3d> poles)
        {
            int count = poles.Count;
            if (count < 2)
            {
                throw new InvalidOperationException("B 样条控制点不足。");
            }

            int order = Math.Min(4, count);
            var weights = new List<double>(count);
            for (int index = 0; index < count; index++)
            {
                weights.Add(1.0);
            }

            int knotCount = count + order;
            int span = count - order + 1;
            var knots = new List<double>(knotCount);
            for (int index = 0; index < knotCount; index++)
            {
                if (index < order)
                {
                    knots.Add(0.0);
                }
                else if (index >= count)
                {
                    knots.Add(1.0);
                }
                else
                {
                    knots.Add((double)(index - order + 1) / span);
                }
            }

            var curve = CurvePrimitive.CreateBsplineCurve(
                new List<DPoint3d>(poles), weights, knots, order, false, false);
            if (curve == null)
            {
                throw new InvalidOperationException("B 样条曲线构造返回空。");
            }

            return curve;
        }

        private static DPoint3d Combine(
            DPoint3d origin, DVector3d axisA, double scaleA, DVector3d axisB, double scaleB)
        {
            return new DPoint3d(
                origin.X + axisA.X * scaleA + axisB.X * scaleB,
                origin.Y + axisA.Y * scaleA + axisB.Y * scaleB,
                origin.Z + axisA.Z * scaleA + axisB.Z * scaleB);
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

    /// <summary>
    /// 工程三维构造的诊断日志：固定写到
    /// <c>%LOCALAPPDATA%\SteelSectionProbe\logs\Engineering\latest.log</c>，每次进程启动覆盖，
    /// 超过 256 KB 自动截断。任何写入异常都被吞掉，绝不影响建模。
    /// </summary>
    internal static class EngineeringLog
    {
        private static readonly object Gate = new object();
        private static bool started;

        internal static void Write(string message)
        {
            try
            {
                lock (Gate)
                {
                    string directory = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "SteelSectionProbe", "logs", "Engineering");
                    Directory.CreateDirectory(directory);
                    string file = Path.Combine(directory, "latest.log");
                    var info = new FileInfo(file);
                    if (!started || (info.Exists && info.Length > 256 * 1024))
                    {
                        started = true;
                        File.WriteAllText(file, "", new UTF8Encoding(false));
                    }

                    File.AppendAllText(file,
                        DateTime.Now.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture) + "  " + message +
                        Environment.NewLine, new UTF8Encoding(false));
                }
            }
            catch (Exception)
            {
                // 日志失败不影响建模。
            }
        }
    }
}
