using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 花篮螺栓总成三维计划：迁移自 AutoCAD 版 TurnbuckleSolidService。
    /// 局部坐标 Y 为拉杆轴、X 为销轴、Z 为厚度，原点在花篮体中心；
    /// 生成后统一绕 X 轴转 90°，使拉杆轴竖直（世界 +Z），再按点取基点平移。
    /// </summary>
    internal static class TurnbuckleCalculator
    {
        internal const int SteelRed = 174;
        internal const int SteelGreen = 185;
        internal const int SteelBlue = 194;
        internal const int MetalRed = 120;
        internal const int MetalGreen = 130;
        internal const int MetalBlue = 140;

        internal static EngineeringPlan Calculate(TurnbuckleParameters parameters)
        {
            string error;
            if (!TurnbuckleCatalog.Validate(parameters, out error))
            {
                throw new InvalidOperationException(error);
            }

            TurnbuckleSpec spec = TurnbuckleCatalog.Resolve(parameters);
            var plan = new EngineeringPlan
            {
                CellName = "TURNBUCKLE_M" + spec.Size,
                HeadingDegrees = parameters.HeadingDegrees,
                RotateXDegrees = 90.0
            };

            BuildNutFrame(plan, spec);
            BuildBosses(plan, spec);

            foreach (int sign in new[] { -1, 1 })
            {
                AddRod(plan, spec, sign);
                AddClevis(plan, spec, sign);
            }

            return plan;
        }

        internal static string Describe(EngineeringPlan plan, TurnbuckleSpec spec)
        {
            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            return string.Format(CultureInfo.CurrentCulture,
                "M{0}：花篮螺母总长 {1:0.#}、宽 {2:0.#}、厚 {3:0.#}；卸扣销轴 φ{4:0.#}；共 {5} 个实体。",
                spec.Size, spec.L, spec.B, spec.Thickness, spec.PinDiameter, plan.PartCount);
        }

        private static void BuildNutFrame(EngineeringPlan plan, TurnbuckleSpec spec)
        {
            double halfThickness = spec.Thickness / 2.0;
            List<EngineeringPoint> outline = spec.RoundedStyle
                ? RoundedRectangle(spec.B, spec.BodyLength, spec.Corner, 0.0, 0.0, 8)
                : ShoulderedOutline(spec);
            var body = plan.Add("花篮螺母框体");
            body.Color(SteelRed, SteelGreen, SteelBlue);
            body.Add.Add(EngineeringShape.Extrude(
                AtZ(outline, -halfThickness), new EngineeringPoint(0, 0, spec.Thickness)));

            List<EngineeringPoint> opening = RoundedRectangle(
                spec.B - 2.0 * spec.Rail, spec.H, spec.OpeningRadius, 0.0, 0.0, 8);
            body.Cut.Add(EngineeringShape.Extrude(
                AtZ(opening, -halfThickness - 1.0), new EngineeringPoint(0, 0, spec.Thickness + 2.0)));

            double boreEnd = spec.L / 2.0 + 1.0;
            body.Cut.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0, -boreEnd, 0), new EngineeringPoint(0, boreEnd, 0), spec.D / 2.0));
        }

        private static void BuildBosses(EngineeringPlan plan, TurnbuckleSpec spec)
        {
            double boreEnd = spec.L / 2.0 + 1.0;
            foreach (int sign in new[] { -1, 1 })
            {
                double centerY = sign * (spec.H / 2.0 + spec.BossLength / 2.0);
                var boss = plan.Add("端部六角凸台");
                boss.Color(SteelRed, SteelGreen, SteelBlue);
                boss.Add.Add(EngineeringShape.HexPrism(
                    new EngineeringPoint(0, centerY - spec.BossLength / 2.0, 0),
                    new EngineeringPoint(0, centerY + spec.BossLength / 2.0, 0),
                    spec.HexAcrossFlats));
                boss.Cut.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(0, -boreEnd, 0), new EngineeringPoint(0, boreEnd, 0), spec.D / 2.0));
            }
        }

        private static void AddRod(EngineeringPlan plan, TurnbuckleSpec spec, int sign)
        {
            double centerY = sign * (spec.h / 2.0 + spec.StudLength / 2.0);
            var rod = plan.Add("拉杆");
            rod.Color(SteelRed, SteelGreen, SteelBlue);
            rod.Add.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0, centerY - spec.StudLength / 2.0, 0),
                new EngineeringPoint(0, centerY + spec.StudLength / 2.0, 0),
                spec.D / 2.0));
        }

        /// <summary>
        /// 单侧 U 形卸扣：本体 + 销轴 + 两个垫圈 + 两个开口销，
        /// 按 sign 先绕 Z 轴翻转（正侧）再沿 Y 平移到装配位置。
        /// </summary>
        private static void AddClevis(EngineeringPlan plan, TurnbuckleSpec spec, int sign)
        {
            double offset = (spec.L / 2.0 + spec.EndGap) + (spec.ClevisH + spec.HeadHeight);
            double translateY = sign * offset;
            Func<EngineeringPoint, EngineeringPoint> map = point =>
            {
                EngineeringPoint mapped = sign > 0
                    ? new EngineeringPoint(-point.X, -point.Y, point.Z)
                    : point;
                return mapped.Offset(0, translateY, 0);
            };
            Func<EngineeringPoint, EngineeringPoint> vector = point =>
                sign > 0 ? new EngineeringPoint(-point.X, -point.Y, point.Z) : point;

            double halfThickness = spec.ClevisThickness / 2.0;
            double shoulder = spec.ClevisFullShoulder ? spec.HeadHeight : 0.3 * spec.HeadHeight;
            double topY = spec.ClevisH + spec.HeadHeight;

            var profile = new List<EngineeringPoint>
            {
                new EngineeringPoint(-spec.ClevisB / 2.0, -spec.Clevish, 0),
                new EngineeringPoint(spec.ClevisB / 2.0, -spec.Clevish, 0),
                new EngineeringPoint(spec.ClevisB / 2.0, topY - shoulder, 0),
                new EngineeringPoint(spec.TopWidth / 2.0, topY, 0),
                new EngineeringPoint(-spec.TopWidth / 2.0, topY, 0),
                new EngineeringPoint(-spec.ClevisB / 2.0, topY - shoulder, 0)
            };

            var body = plan.Add("U 形卸扣本体");
            body.Color(SteelRed, SteelGreen, SteelBlue);
            body.Add.Add(EngineeringShape.Extrude(
                MapPoints(profile, map, -halfThickness), vector(new EngineeringPoint(0, 0, spec.ClevisThickness))));

            double gap = spec.ClevisB - 2.0 * spec.Leg;
            double slotHeight = spec.ClevisH + spec.Clevish + 10.0;
            List<EngineeringPoint> slot = RoundedRectangle(gap, slotHeight, spec.InsideRadius,
                0.0, spec.ClevisH - slotHeight / 2.0, 8);
            body.Cut.Add(EngineeringShape.Extrude(
                MapPoints(slot, map, -halfThickness - 1.0),
                vector(new EngineeringPoint(0, 0, spec.ClevisThickness + 2.0))));

            double pinHoleRadius = (spec.PinDiameter + spec.PinClearance) / 2.0;
            body.Cut.Add(EngineeringShape.Cylinder(
                map(new EngineeringPoint(-spec.ClevisB / 2.0 - 1.0, 0, 0)),
                map(new EngineeringPoint(spec.ClevisB / 2.0 + 1.0, 0, 0)),
                pinHoleRadius));

            double threadCenter = spec.ClevisH + spec.HeadHeight / 2.0;
            double threadHalf = spec.HeadHeight / 2.0 + 1.0;
            body.Cut.Add(EngineeringShape.Cylinder(
                map(new EngineeringPoint(0, threadCenter - threadHalf, 0)),
                map(new EngineeringPoint(0, threadCenter + threadHalf, 0)),
                spec.D / 2.0));

            double pinLength = spec.ClevisB + 2.0 * spec.PinOverhang;
            var pin = plan.Add("销轴");
            pin.Color(MetalRed, MetalGreen, MetalBlue);
            pin.Add.Add(EngineeringShape.Cylinder(
                map(new EngineeringPoint(-pinLength / 2.0, 0, 0)),
                map(new EngineeringPoint(pinLength / 2.0, 0, 0)),
                spec.PinDiameter / 2.0));

            double wire = 0.035 * spec.PinDiameter;
            foreach (int side in new[] { -1, 1 })
            {
                double x = side * (spec.ClevisB / 2.0 + 0.65 * spec.PinOverhang);
                pin.Cut.Add(EngineeringShape.Cylinder(
                    map(new EngineeringPoint(x, -spec.PinDiameter / 2.0 - 1.0, 0)),
                    map(new EngineeringPoint(x, spec.PinDiameter / 2.0 + 1.0, 0)),
                    2.2 * wire));
            }

            foreach (int side in new[] { -1, 1 })
            {
                double x = side * (spec.ClevisB / 2.0 + spec.WasherThickness / 2.0);
                var washer = plan.Add("垫圈");
                washer.Color(MetalRed, MetalGreen, MetalBlue);
                washer.Add.Add(EngineeringShape.Cylinder(
                    map(new EngineeringPoint(x - spec.WasherThickness / 2.0, 0, 0)),
                    map(new EngineeringPoint(x + spec.WasherThickness / 2.0, 0, 0)),
                    spec.WasherOd / 2.0));
                washer.Cut.Add(EngineeringShape.Cylinder(
                    map(new EngineeringPoint(x - spec.WasherThickness / 2.0 - 1.0, 0, 0)),
                    map(new EngineeringPoint(x + spec.WasherThickness / 2.0 + 1.0, 0, 0)),
                    pinHoleRadius));

                double retainerX = side * (spec.ClevisB / 2.0 + 0.65 * spec.PinOverhang);
                var retainer = plan.Add("开口销");
                retainer.Color(MetalRed, MetalGreen, MetalBlue);
                retainer.Add.Add(EngineeringShape.Cylinder(
                    map(new EngineeringPoint(retainerX, -0.85 * spec.PinDiameter, 0)),
                    map(new EngineeringPoint(retainerX, 0.85 * spec.PinDiameter, 0)),
                    wire));
                retainer.Add.Add(EngineeringShape.Torus(
                    map(new EngineeringPoint(retainerX, 0.85 * spec.PinDiameter, 0)),
                    0.12 * spec.PinDiameter, wire));
            }
        }

        private static List<EngineeringPoint> ShoulderedOutline(TurnbuckleSpec spec)
        {
            double halfLength = spec.BodyLength / 2.0;
            double halfB = spec.B / 2.0;
            double halfHex = spec.HexAcrossFlats / 2.0;
            double shoulder = spec.Rail;
            return new List<EngineeringPoint>
            {
                new EngineeringPoint(-halfHex, -halfLength, 0),
                new EngineeringPoint(halfHex, -halfLength, 0),
                new EngineeringPoint(halfB, -halfLength + shoulder, 0),
                new EngineeringPoint(halfB, halfLength - shoulder, 0),
                new EngineeringPoint(halfHex, halfLength, 0),
                new EngineeringPoint(-halfHex, halfLength, 0),
                new EngineeringPoint(-halfB, halfLength - shoulder, 0),
                new EngineeringPoint(-halfB, -halfLength + shoulder, 0)
            };
        }

        /// <summary>圆角矩形轮廓（XY 平面），圆心可按 centerX/centerY 偏移。</summary>
        private static List<EngineeringPoint> RoundedRectangle(
            double width, double height, double radius,
            double centerX, double centerY, int segments)
        {
            double halfWidth = width / 2.0;
            double halfHeight = height / 2.0;
            radius = Math.Min(radius, Math.Min(halfWidth, halfHeight) - 0.01);
            if (radius <= 0.01)
            {
                return new List<EngineeringPoint>
                {
                    new EngineeringPoint(centerX - halfWidth, centerY - halfHeight, 0),
                    new EngineeringPoint(centerX + halfWidth, centerY - halfHeight, 0),
                    new EngineeringPoint(centerX + halfWidth, centerY + halfHeight, 0),
                    new EngineeringPoint(centerX - halfWidth, centerY + halfHeight, 0)
                };
            }

            var points = new List<EngineeringPoint>();
            AddArc(points, centerX + halfWidth - radius, centerY + halfHeight - radius, radius, 0.0, 90.0, segments);
            AddArc(points, centerX - halfWidth + radius, centerY + halfHeight - radius, radius, 90.0, 180.0, segments);
            AddArc(points, centerX - halfWidth + radius, centerY - halfHeight + radius, radius, 180.0, 270.0, segments);
            AddArc(points, centerX + halfWidth - radius, centerY - halfHeight + radius, radius, 270.0, 360.0, segments);
            return points;
        }

        private static void AddArc(List<EngineeringPoint> points, double centerX, double centerY,
            double radius, double startDegrees, double endDegrees, int segments)
        {
            for (int index = 0; index <= segments; index++)
            {
                double angle = (startDegrees + (endDegrees - startDegrees) * index / segments) * Math.PI / 180.0;
                var point = new EngineeringPoint(
                    centerX + Math.Cos(angle) * radius, centerY + Math.Sin(angle) * radius, 0);
                if (points.Count == 0 || !Same(points[points.Count - 1], point))
                {
                    points.Add(point);
                }
            }
        }

        private static bool Same(EngineeringPoint a, EngineeringPoint b)
        {
            return Math.Abs(a.X - b.X) < 1e-9 && Math.Abs(a.Y - b.Y) < 1e-9;
        }

        private static EngineeringPoint[] AtZ(List<EngineeringPoint> points, double z)
        {
            var result = new List<EngineeringPoint>(points.Count);
            foreach (EngineeringPoint point in points)
            {
                result.Add(new EngineeringPoint(point.X, point.Y, z));
            }

            return result.ToArray();
        }

        private static EngineeringPoint[] MapPoints(
            List<EngineeringPoint> points, Func<EngineeringPoint, EngineeringPoint> map, double z)
        {
            var result = new List<EngineeringPoint>(points.Count);
            foreach (EngineeringPoint point in points)
            {
                result.Add(map(new EngineeringPoint(point.X, point.Y, z)));
            }

            return result.ToArray();
        }
    }
}
