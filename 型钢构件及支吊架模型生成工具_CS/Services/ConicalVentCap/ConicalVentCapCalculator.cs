using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 锥形风帽三维计划（14K117-3 第 3 页构造图、第 5 页尺寸表），
    /// 由 AutoCAD 版 ConicalVentCapSolidService 按 IGES 尺寸 1:1 迁移为纯毫米几何。
    ///
    /// 坐标：局部原点在底部接口平面中心，+Z 向上，全部 mm；D 为连接短管外径，
    /// 板厚向内生成（内径 = D − 2t）。零件编号与参考模型一致：
    /// - 05 连接短管、02 外下锥、01 外上锥、03 内上锥（雨帽，尖朝上）、
    ///   04 内下锥（雨水锥，尖朝下）、03a 内檐环形搭接座、06 假定 L50×50×5 法兰；
    /// - 07 外焊折弯筋（153.4°、厚 6、贴短管外壁与外下锥外侧）；
    /// - 08 内外锥之间两端折弯支架（宽 30、厚 5、两端腿 80、外侧腿 2×φ9）。
    /// 本类只产出 <see cref="EngineeringPlan"/>，不引用任何 Bentley 或 AutoCAD 类型。
    /// </summary>
    internal static class ConicalVentCapCalculator
    {
        /// <summary>壳体与接口件颜色（浅灰）红分量。</summary>
        internal const int ShellRed = 235;

        /// <summary>壳体与接口件颜色（浅灰）绿分量。</summary>
        internal const int ShellGreen = 235;

        /// <summary>壳体与接口件颜色（浅灰）蓝分量。</summary>
        internal const int ShellBlue = 235;

        /// <summary>支撑件颜色（深灰）红分量。</summary>
        internal const int SupportRed = 128;

        /// <summary>支撑件颜色（深灰）绿分量。</summary>
        internal const int SupportGreen = 128;

        /// <summary>支撑件颜色（深灰）蓝分量。</summary>
        internal const int SupportBlue = 128;

        /// <summary>件⑦与外下锥面的焊接贴合间隙（径向，mm）。</summary>
        internal const double Support07WeldingGapMm = 0.01;

        /// <summary>件⑦折弯筋厚度（mm）。</summary>
        internal const double Support07ThicknessMm = 6.0;

        /// <summary>件⑦折弯角：图示 153.4°，建模取 180° − 153.4°。</summary>
        internal const double Support07BendDegrees = 153.4;

        /// <summary>件⑧与内、外锥面的安装间隙（法向，mm）。</summary>
        internal const double Support08ClearanceMm = 0.15;

        /// <summary>件⑧板厚（mm）。</summary>
        internal const double Support08ThicknessMm = 5.0;

        /// <summary>件⑧带宽（mm）。</summary>
        internal const double Support08WidthMm = 30.0;

        /// <summary>件⑧单端腿长（mm）。</summary>
        internal const double Support08LegMm = 80.0;

        /// <summary>件⑧外侧腿 φ9 通孔半径（mm）。</summary>
        internal const double Support08HoleRadiusMm = 4.5;

        /// <summary>
        /// 按参数生成整组实体计划；任何尺寸非法都抛出中文
        /// <see cref="InvalidOperationException"/>，不静默取默认值。
        /// </summary>
        internal static EngineeringPlan Calculate(ConicalVentCapParameters parameters)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            string error;
            if (!ConicalVentCapCatalog.Validate(parameters, out error))
            {
                throw new InvalidOperationException(error);
            }

            ConicalVentCapDimensions dimensions = ConicalVentCapCatalog.Dimensions(parameters.DiameterMm);
            double diameter = parameters.DiameterMm;
            double thickness = parameters.WallThicknessMm;
            int supportCount = parameters.SupportCount;
            double radius3 = dimensions.D3 / 2.0;
            double equator = dimensions.Eq;

            var plan = new EngineeringPlan
            {
                CellName = "CONICAL_VENT_CAP_D" +
                    Math.Round(diameter).ToString("0", CultureInfo.InvariantCulture),
                HeadingDegrees = parameters.HeadingDegrees,
                RotateXDegrees = 0.0
            };

            // 05 连接短管：D 为外径，板厚向内。
            AddShell(plan, "05 连接短管",
                Tube(diameter / 2.0 - thickness, diameter / 2.0, 0.0, dimensions.H5));

            // 02 外下锥、01 外上锥：板厚沿锥面法向偏移。
            AddShell(plan, "02 外下锥",
                FrustumShell(dimensions.D1 / 2.0, dimensions.D2 / 2.0,
                    dimensions.H, equator, thickness));
            AddShell(plan, "01 外上锥",
                FrustumShell(dimensions.D2 / 2.0, dimensions.D1 / 2.0,
                    equator, dimensions.Top, thickness));

            // 03 内上锥（雨帽，尖朝上）、04 内下锥（雨水锥，尖朝下）。
            AddShell(plan, "03 内上锥（雨帽）",
                PointedSheet(radius3, equator, equator + dimensions.H3, thickness));
            AddShell(plan, "04 内下锥（雨水锥）",
                PointedSheet(radius3 - 10.0, equator, equator - dimensions.H4, thickness));

            // 03a 内檐环形搭接座：保留图集 10 mm 挑檐。
            AddShell(plan, "03a 内檐环形搭接座",
                Seat(radius3 - 12.0, radius3, equator - thickness, thickness));

            // 06 假定 L50×50×5 法兰：横板 + 竖肢，再按件⑦直段在每组支撑处让位。
            AddFlange(plan, diameter, dimensions, supportCount);

            // 07 外焊折弯筋、08 内外锥之间折弯支架，均布。
            for (int index = 0; index < supportCount; index++)
            {
                double rotation = 360.0 * index / supportCount;

                var lower = plan.Add("07 外焊折弯筋");
                lower.Color(SupportRed, SupportGreen, SupportBlue);
                lower.Add.Add(Support07Shape(diameter, dimensions, rotation));

                AddSupport08(plan, dimensions, thickness, rotation);
            }

            return plan;
        }

        /// <summary>中文摘要：D、尺寸依据、D2/D3、总高、板厚、支撑组数与实体数。</summary>
        internal static string Describe(
            EngineeringPlan plan, ConicalVentCapDimensions dimensions, ConicalVentCapParameters parameters)
        {
            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            if (dimensions == null)
            {
                throw new ArgumentNullException("dimensions");
            }

            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            return string.Format(CultureInfo.CurrentCulture,
                "D{0:0.###}：{1}，D2={2:0.##}、D3={3:0.##}、总高 {4:0.##}、板厚 {5:0.###}、支撑 {6} 组、{7} 个实体。",
                dimensions.Diameter,
                ConicalVentCapCatalog.BasisText(dimensions.Diameter),
                dimensions.D2,
                dimensions.D3,
                dimensions.Top,
                parameters.WallThicknessMm,
                parameters.SupportCount,
                plan.PartCount);
        }

        private static void AddShell(EngineeringPlan plan, string name, EngineeringShape shape)
        {
            var body = plan.Add(name);
            body.Color(ShellRed, ShellGreen, ShellBlue);
            body.Add.Add(shape);
        }

        private static void AddFlange(
            EngineeringPlan plan, double diameter, ConicalVentCapDimensions dimensions, int supportCount)
        {
            double inner = diameter / 2.0;
            if (inner <= 0.0)
            {
                throw new InvalidOperationException("法兰内半径必须大于 0。");
            }

            var flange = plan.Add("06 法兰");
            flange.Color(ShellRed, ShellGreen, ShellBlue);

            // L 形截面：横板 50×5 + 竖肢 5×50（= CAD 的圆板与竖环相并）。
            flange.Add.Add(EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(inner, 0, 0),
                new EngineeringPoint(inner + 50.0, 0, 0),
                new EngineeringPoint(inner + 50.0, 0, 5.0),
                new EngineeringPoint(inner + 5.0, 0, 5.0),
                new EngineeringPoint(inner + 5.0, 0, 50.0),
                new EngineeringPoint(inner, 0, 50.0)
            }));

            for (int index = 0; index < supportCount; index++)
            {
                double rotation = 360.0 * index / supportCount;
                flange.Cut.Add(Support07Shape(diameter, dimensions, rotation));
            }
        }

        /// <summary>
        /// 件⑦外焊折弯筋：直段贴连接短管外壁（切于 D/2），斜段内表面落在外下锥外表面上，
        /// 折弯高度按锥面切线求解并保留 0.01 mm 焊接贴合间隙。
        /// 大规格（D≥900）宽 36/直段 80/斜段 102；小规格宽 30/直段 60/斜段 82。
        /// </summary>
        private static EngineeringShape Support07Shape(
            double diameter, ConicalVentCapDimensions dimensions, double rotationDegrees)
        {
            bool large = diameter >= 900.0;
            double width = large ? 36.0 : 30.0;
            double lowerLeg = large ? 80.0 : 60.0;
            double upperLeg = large ? 102.0 : 82.0;
            double angle = (180.0 - Support07BendDegrees) * Math.PI / 180.0;
            double halfThickness = Support07ThicknessMm / 2.0;
            double radius = diameter / 2.0 + halfThickness;

            double tangent = Math.Tan(angle);
            if (Math.Abs(tangent) < 1e-9)
            {
                throw new InvalidOperationException("件⑦折弯角无效，无法求解折弯高度。");
            }

            double bendZ = dimensions.H +
                (radius - halfThickness / Math.Cos(angle) - dimensions.D1 / 2.0 - Support07WeldingGapMm) / tangent;

            var path = new List<PlanePoint>
            {
                new PlanePoint(radius, bendZ - lowerLeg),
                new PlanePoint(radius, bendZ),
                new PlanePoint(radius + upperLeg * Math.Sin(angle), bendZ + upperLeg * Math.Cos(angle))
            };

            return BentStrap(path, width, Support07ThicknessMm, rotationDegrees);
        }

        /// <summary>
        /// 件⑧内外锥之间两端折弯支架：span=A、内外腿夹角 φ（内侧腿相对中间跨的倾角 δ = φ−90°）、
        /// 中间跨 + 两端腿 80、宽 30、厚 5；先在 F 站位试放，按整块折弯件轮廓与内、外锥面的
        /// 偏差联立求解滑移量，再迭代 5 次把法向间隙收敛到 0.15 mm。
        /// </summary>
        private static void AddSupport08(
            EngineeringPlan plan, ConicalVentCapDimensions dimensions, double wall, double rotationDegrees)
        {
            double span = dimensions.SupportA;
            double phi = dimensions.SupportPhi;
            double delta = (phi - 90.0) * Math.PI / 180.0;

            var path = new List<PlanePoint>
            {
                new PlanePoint(-Support08LegMm * Math.Sin(delta), -Support08LegMm * Math.Cos(delta)),
                new PlanePoint(0.0, 0.0),
                new PlanePoint(span, 0.0),
                new PlanePoint(span, -Support08LegMm)
            };

            List<PlanePoint> outline = BuildOffsetOutline(path, Support08ThicknessMm);

            double radius1 = dimensions.D1 / 2.0;
            double radius2 = dimensions.D2 / 2.0;
            double radius3 = dimensions.D3 / 2.0 - 10.0;
            double equator = dimensions.Eq;

            // 外下锥母线方向（局部径向 u、轴向 v）与外法向。
            double theta = Math.Atan2(radius2 - radius1, dimensions.H2);
            double ux = Math.Cos(theta);
            double uz = -Math.Sin(theta);
            double vx = Math.Sin(theta);
            double vz = Math.Cos(theta);

            // 外侧腿板面贴在外锥内表面（按 F 站位），再解出内侧腿同时贴内锥的滑移量。
            double outerStation = dimensions.SupportF;
            double anchorX = radius2 - outerStation * vx - wall * ux;
            double anchorZ = equator - outerStation * vz - wall * uz;
            double halfThickness = Support08ThicknessMm / 2.0;

            double originX = anchorX - (span + halfThickness) * ux;
            double originZ = anchorZ - (span + halfThickness) * uz;

            double localX = -40.0 * Math.Sin(delta);
            double localZ = -40.0 * Math.Cos(delta);
            double normalX = Math.Cos(delta) * ux - Math.Sin(delta) * vx;
            double normalZ = Math.Cos(delta) * uz - Math.Sin(delta) * vz;

            double probeX = originX + localX * ux + localZ * vx - halfThickness * normalX;
            double probeZ = originZ + localX * uz + localZ * vz - halfThickness * normalZ;

            double innerSlope = radius3 / dimensions.H4;
            double outerSlope = (radius2 - radius1) / dimensions.H2;
            if (Math.Abs(innerSlope - outerSlope) < 1e-9)
            {
                throw new InvalidOperationException("件⑧就位求解失败：内、外锥斜率相同。");
            }

            double residual = probeX - (radius3 + innerSlope * (probeZ - equator));
            double slideDenominator = -vx + innerSlope * vz;
            if (Math.Abs(slideDenominator) < 1e-9)
            {
                throw new InvalidOperationException("件⑧就位求解失败：内侧腿滑移方向退化。");
            }

            double slide = -residual / slideDenominator;
            originX -= slide * vx;
            originZ -= slide * vz;

            // 整块折弯件的包络在两面之间就位：只按中点相切会在端部和切向侧边超差。
            for (int iteration = 0; iteration < 5; iteration++)
            {
                double outerExcess = double.MinValue;
                double innerExcess = double.MaxValue;

                foreach (PlanePoint local in outline)
                {
                    foreach (double side in new[] { -1.0, 1.0 })
                    {
                        EngineeringPoint world = StrapPoint(
                            local, side * Support08WidthMm / 2.0, theta, originX, originZ);

                        outerExcess = Math.Max(outerExcess,
                            Math.Sqrt(world.X * world.X + world.Y * world.Y) -
                            OuterInnerRadius(world.Z, dimensions, wall));

                        // 内锥是凸面，最近点在支架的切向中面，而不是侧边顶点，故只用 X。
                        innerExcess = Math.Min(innerExcess,
                            world.X - LowerInnerOuterRadius(world.Z, dimensions));
                    }
                }

                double targetOuter = -Support08ClearanceMm * Math.Sqrt(1.0 + outerSlope * outerSlope);
                double targetInner = Support08ClearanceMm * Math.Sqrt(1.0 + innerSlope * innerSlope);
                double outerDelta = targetOuter - outerExcess;
                double innerDelta = targetInner - innerExcess;
                double dz = (outerDelta - innerDelta) / (innerSlope - outerSlope);
                double dr = outerDelta + outerSlope * dz;

                originX += dr;
                originZ += dz;
            }

            var body = plan.Add("08 内外锥折弯支架");
            body.Color(SupportRed, SupportGreen, SupportBlue);

            var points = new EngineeringPoint[outline.Count];
            for (int index = 0; index < outline.Count; index++)
            {
                points[index] = StrapPoint(
                    outline[index], -Support08WidthMm / 2.0, theta, originX, originZ)
                    .RotateZ(rotationDegrees);
            }

            // 带宽沿切向（Y）拉伸并关于装配面对称，等价于 CAD 的拉伸后绕 X 转 90° 再平移半宽。
            EngineeringPoint direction = new EngineeringPoint(0, Support08WidthMm, 0).RotateZ(rotationDegrees);
            body.Add.Add(EngineeringShape.Extrude(points, direction));

            // 外侧腿 2×φ9 通孔：孔轴沿 X 穿过 5 mm 板厚，距端部 20 / 60。
            foreach (double station in new[] { -20.0, -60.0 })
            {
                EngineeringPoint holeStart = StrapPoint(
                    new PlanePoint(span - 10.0, station), 0.0, theta, originX, originZ).RotateZ(rotationDegrees);
                EngineeringPoint holeEnd = StrapPoint(
                    new PlanePoint(span + 10.0, station), 0.0, theta, originX, originZ).RotateZ(rotationDegrees);
                body.Cut.Add(EngineeringShape.Cylinder(holeStart, holeEnd, Support08HoleRadiusMm));
            }
        }

        /// <summary>外锥内表面半径（板厚沿法向内偏后的锥面）。</summary>
        private static double OuterInnerRadius(double z, ConicalVentCapDimensions dimensions, double wall)
        {
            double slope = (dimensions.D2 - dimensions.D1) / (2.0 * dimensions.H2);
            return dimensions.D2 / 2.0 + slope * (z - dimensions.Eq) -
                wall * Math.Sqrt(1.0 + slope * slope);
        }

        /// <summary>内下锥外表面半径（内锥上端直径按 10 mm 挑檐内收）。</summary>
        private static double LowerInnerOuterRadius(double z, ConicalVentCapDimensions dimensions)
        {
            return (dimensions.D3 / 2.0 - 10.0) * (1.0 + (z - dimensions.Eq) / dimensions.H4);
        }

        /// <summary>
        /// 折弯件上的点在装配坐标下的位置：局部 (x=径向、y=轴向) 绕 Y 轴转 theta 后平移到 origin，
        /// 再用 lateral 给带宽（Y 向）。X=径向、Y=横向、Z=轴向。
        /// </summary>
        private static EngineeringPoint StrapPoint(
            PlanePoint local, double lateral, double theta, double originX, double originZ)
        {
            double cosine = Math.Cos(theta);
            double sine = Math.Sin(theta);
            return new EngineeringPoint(
                local.X * cosine + local.Y * sine + originX,
                lateral,
                -local.X * sine + local.Y * cosine + originZ);
        }

        // ============================================================
        // 折弯扁钢
        // ============================================================

        /// <summary>
        /// 等厚折弯扁钢的闭合截面轮廓（尖角斜接，原图未给折弯半径）：
        /// 沿路径分别向两侧偏移半个板厚，再把两侧轮廓首尾相接。
        /// 路径与轮廓均在“x=径向、y=轴向”的平面内。
        /// </summary>
        private static List<PlanePoint> BuildOffsetOutline(IList<PlanePoint> path, double thickness)
        {
            if (path == null || path.Count < 2)
            {
                throw new InvalidOperationException("折弯路径至少需要 2 个点。");
            }

            if (thickness <= 0.0)
            {
                throw new InvalidOperationException("折弯扁钢厚度必须大于 0。");
            }

            List<PlanePoint> forward = OffsetPathSide(path, thickness, 1.0);
            List<PlanePoint> backward = OffsetPathSide(path, thickness, -1.0);
            backward.Reverse();

            var outline = new List<PlanePoint>(forward.Count + backward.Count);
            outline.AddRange(forward);
            outline.AddRange(backward);
            return outline;
        }

        /// <summary>沿路径一侧偏移半个板厚，相邻偏移线求交得到斜接点。</summary>
        private static List<PlanePoint> OffsetPathSide(IList<PlanePoint> path, double thickness, double sign)
        {
            var starts = new List<PlanePoint>(path.Count - 1);
            var directions = new List<PlanePoint>(path.Count - 1);

            for (int index = 0; index + 1 < path.Count; index++)
            {
                PlanePoint a = path[index];
                PlanePoint b = path[index + 1];
                double dx = b.X - a.X;
                double dz = b.Y - a.Y;
                double length = Math.Sqrt(dx * dx + dz * dz);
                if (length <= 1e-9)
                {
                    throw new InvalidOperationException("折弯路径存在重合点。");
                }

                double nx = -dz / length * thickness / 2.0 * sign;
                double nz = dx / length * thickness / 2.0 * sign;
                starts.Add(new PlanePoint(a.X + nx, a.Y + nz));
                directions.Add(new PlanePoint(dx, dz));
            }

            var points = new List<PlanePoint> { starts[0] };

            for (int index = 0; index + 1 < starts.Count; index++)
            {
                PlanePoint a = starts[index];
                PlanePoint u = directions[index];
                PlanePoint b = starts[index + 1];
                PlanePoint v = directions[index + 1];

                double cross = u.X * v.Y - u.Y * v.X;
                if (Math.Abs(cross) <= 1e-9)
                {
                    throw new InvalidOperationException("折弯路径存在 180° 反折，无法斜接。");
                }

                double k = ((b.X - a.X) * v.Y - (b.Y - a.Y) * v.X) / cross;
                points.Add(new PlanePoint(a.X + k * u.X, a.Y + k * u.Y));
            }

            PlanePoint last = starts[starts.Count - 1];
            PlanePoint lastDirection = directions[directions.Count - 1];
            points.Add(new PlanePoint(last.X + lastDirection.X, last.Y + lastDirection.Y));
            return points;
        }

        /// <summary>
        /// 把折弯轮廓（x=径向、y=轴向）拉伸成带宽为 width 的扁钢：
        /// 轮廓先落到 Y=−width/2，再沿旋转后的 Y 向拉伸 width，使带宽关于装配面对称。
        /// </summary>
        private static EngineeringShape BentStrap(
            IList<PlanePoint> path, double width, double thickness, double rotationDegrees)
        {
            if (width <= 0.0)
            {
                throw new InvalidOperationException("扁钢宽度必须大于 0。");
            }

            List<PlanePoint> outline = BuildOffsetOutline(path, thickness);
            var points = new EngineeringPoint[outline.Count];
            for (int index = 0; index < outline.Count; index++)
            {
                points[index] = new EngineeringPoint(
                    outline[index].X, -width / 2.0, outline[index].Y).RotateZ(rotationDegrees);
            }

            EngineeringPoint direction = new EngineeringPoint(0, width, 0).RotateZ(rotationDegrees);
            return EngineeringShape.Extrude(points, direction);
        }

        // ============================================================
        // 壳体与接口件
        // ============================================================

        /// <summary>圆管薄壁：内外半径、从 zBottom 起高 height，绕 Z 轴回转。</summary>
        private static EngineeringShape Tube(
            double innerRadius, double outerRadius, double zBottom, double height)
        {
            if (height <= 0.0)
            {
                throw new InvalidOperationException("圆管高度必须大于 0。");
            }

            if (innerRadius <= 0.0 || outerRadius <= innerRadius)
            {
                throw new InvalidOperationException("圆管内外半径不匹配。");
            }

            return EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(innerRadius, 0, zBottom),
                new EngineeringPoint(outerRadius, 0, zBottom),
                new EngineeringPoint(outerRadius, 0, zBottom + height),
                new EngineeringPoint(innerRadius, 0, zBottom + height)
            });
        }

        /// <summary>
        /// 正圆台薄板：板厚沿锥面法向（径向偏移 = t·√(1+slope²)），与 CAD 的
        /// CreateFrustumShell 同一算法。
        /// </summary>
        private static EngineeringShape FrustumShell(
            double bottomRadius, double topRadius, double zBottom, double zTop, double thickness)
        {
            double rise = zTop - zBottom;
            if (rise <= 0.0)
            {
                throw new InvalidOperationException("圆台高度必须大于 0。");
            }

            double slope = (topRadius - bottomRadius) / rise;
            double radial = thickness * Math.Sqrt(1.0 + slope * slope);
            if (bottomRadius - radial <= 0.0 || topRadius - radial <= 0.0)
            {
                throw new InvalidOperationException("板厚过大，圆台内表面半径非正。");
            }

            return EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(bottomRadius, 0, zBottom),
                new EngineeringPoint(topRadius, 0, zTop),
                new EngineeringPoint(topRadius - radial, 0, zTop),
                new EngineeringPoint(bottomRadius - radial, 0, zBottom)
            });
        }

        /// <summary>
        /// 顶点薄板（雨帽/雨水锥）：外表面为过顶点的锥面，板厚按竖直方向偏移，
        /// vertical = t·√(1+((zTip−zEq)/radius)²)，与 CAD 的 CreatePointedSheet 同一算法。
        /// </summary>
        private static EngineeringShape PointedSheet(
            double radius, double zEquator, double zTip, double thickness)
        {
            if (radius <= 0.0)
            {
                throw new InvalidOperationException("顶点薄板半径必须大于 0。");
            }

            if (Math.Abs(zTip - zEquator) <= 1e-9)
            {
                throw new InvalidOperationException("顶点薄板的顶点高度不能等于母线高度。");
            }

            double sign = zTip > zEquator ? 1.0 : -1.0;
            double vertical = thickness *
                Math.Sqrt(1.0 + Math.Pow((zTip - zEquator) / radius, 2.0));

            return EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(0.0, 0, zTip),
                new EngineeringPoint(radius, 0, zEquator),
                new EngineeringPoint(radius, 0, zEquator - sign * vertical),
                new EngineeringPoint(0.0, 0, zTip - sign * vertical)
            });
        }

        /// <summary>内檐环形搭接座：矩形截面 (inner, zBottom)-(outer, zBottom)-(outer, zBottom+t)-(inner, zBottom+t)。</summary>
        private static EngineeringShape Seat(
            double innerRadius, double outerRadius, double zBottom, double height)
        {
            if (innerRadius <= 0.0 || outerRadius <= innerRadius || height <= 0.0)
            {
                throw new InvalidOperationException("内檐环形搭接座的截面尺寸不匹配。");
            }

            return EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(innerRadius, 0, zBottom),
                new EngineeringPoint(outerRadius, 0, zBottom),
                new EngineeringPoint(outerRadius, 0, zBottom + height),
                new EngineeringPoint(innerRadius, 0, zBottom + height)
            });
        }

        /// <summary>“径向-轴向”平面内的二维点（mm）：X 为半径方向、Y 为轴向，对应 CAD 的 Point2d。</summary>
        private struct PlanePoint
        {
            internal readonly double X;

            internal readonly double Y;

            internal PlanePoint(double x, double y)
            {
                X = x;
                Y = y;
            }
        }
    }
}
