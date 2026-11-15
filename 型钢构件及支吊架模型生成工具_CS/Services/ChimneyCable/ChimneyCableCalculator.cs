using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱拉索三维计划：迁移自 AutoCAD 版 <c>CableStayedChimneySolidService</c> 与
    /// <c>RopeEyeAssemblySolidService</c>，只保留三维建模（不含俯视图/正视图二维绘制）。
    ///
    /// 坐标：局部原点 = 筒身底部圆心，Z 向上，全部尺寸为 mm。
    /// 筒身 = 径向矩形回转成的空心筒壁（上下环形端面保留）；
    /// 拉索 = φ16 钢丝绳，三根方位角 30°/270°/150°，上端系在筒身 2H/3 表面、
    /// 下端落在地面锚墩；H/(2R) &gt; 35 时在 H/3 高度补一组中间层拉索；
    /// 每根拉索两端各一套绳眼装配（鸡心环 + 3 只绳夹），装配轴向沿拉索、上端向下、下端向上。
    ///
    /// 绳眼为“简化但保留主要尺寸”的示意，简化项见 <see cref="AddRopeEye"/> 注释。
    /// </summary>
    internal static class ChimneyCableCalculator
    {
        /// <summary>筒身颜色（钢灰）。</summary>
        internal const int ShellRed = 174;
        internal const int ShellGreen = 185;
        internal const int ShellBlue = 194;

        /// <summary>钢丝绳颜色（橙棕）。</summary>
        internal const int RopeRed = 200;
        internal const int RopeGreen = 120;
        internal const int RopeBlue = 40;

        /// <summary>鸡心环、夹座颜色（深灰）。</summary>
        internal const int FittingRed = 110;
        internal const int FittingGreen = 115;
        internal const int FittingBlue = 120;

        /// <summary>U 形螺栓、六角螺母颜色（浅灰）。</summary>
        internal const int BoltRed = 170;
        internal const int BoltGreen = 175;
        internal const int BoltBlue = 180;

        /// <summary>地面锚墩颜色（混凝土灰）。</summary>
        internal const int AnchorRed = 128;
        internal const int AnchorGreen = 128;
        internal const int AnchorBlue = 128;

        /// <summary>绳圈端点伸入拉索主体（或主体端点）的长度（mm），保证并集有实体搭接。</summary>
        private const double BodyPenetrationMm = 8.0;

        /// <summary>
        /// 尾段绳相对工作段绳的额外侧偏（mm）。名义布置两股绳中心距 = 2R = 16，
        /// 扫掠体会与自身相切；这里留 1 mm 间隙，保证扫掠体是合法流形。
        /// </summary>
        private const double StrandGapMm = 1.0;

        /// <summary>过渡段回弯的轴向长度（mm）：CAD 过渡段 2.5φ = 40，直段伸入 4，故取 36。</summary>
        private const double BlendRunMm = 36.0;

        /// <summary>过渡段三次贝塞尔采样段数。</summary>
        private const int BlendSamples = 10;

        /// <summary>鸡心环左/右腿贝塞尔采样段数。</summary>
        private const int ThimbleLegSamples = 20;

        /// <summary>鸡心环冠部半圆采样段数。</summary>
        private const int ThimbleArcSamples = 16;

        /// <summary>U 形螺栓弧顶采样段数。</summary>
        private const int BoltArcSamples = 12;

        /// <summary>按参数生成完整三维计划；参数不合法时抛出带中文原因的计划异常。</summary>
        internal static EngineeringPlan Calculate(ChimneyCableParameters parameters)
        {
            string error;
            if (!ChimneyCableCatalog.Validate(parameters, out error))
            {
                throw new InvalidOperationException(error);
            }

            ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
            var plan = new EngineeringPlan
            {
                CellName = "CHIMNEY_CABLE_H" + Math.Round(
                    parameters.HeightMeters, MidpointRounding.AwayFromZero)
                    .ToString("0", CultureInfo.InvariantCulture),
                HeadingDegrees = parameters.HeadingDegrees,
                RotateXDegrees = 0.0
            };

            AddShell(plan, spec);

            double[] azimuths = ChimneyCableCatalog.CableAzimuthDegrees;
            double upperHeight = 2.0 * spec.HeightMm / 3.0;
            AddCollar(plan, spec, azimuths, upperHeight, "上端连接环板");
            if (spec.NeedsExtraCable)
            {
                AddCollar(plan, spec, azimuths, spec.HeightMm / 3.0, "中间层连接环板");
            }

            for (int index = 0; index < azimuths.Length; index++)
            {
                double angle = Radians(azimuths[index]);
                double cosine = Math.Cos(angle);
                double sine = Math.Sin(angle);
                string label = "拉索 " + (index + 1).ToString(CultureInfo.InvariantCulture);
                string anchorLabel = "地面锚墩 " + (index + 1).ToString(CultureInfo.InvariantCulture);

                // 单层：地面固定点就在拉索外圆上；两层：上层比下层外扩 150（两个 U 形钢筋间隔 150）。
                double upperGroundRadius = spec.OuterRadiusMm +
                    (spec.NeedsExtraCable ? ChimneyCableCatalog.GroundLayerOffsetMm : 0.0);
                var upperGround = new EngineeringPoint(
                    upperGroundRadius * cosine, upperGroundRadius * sine, 0.0);

                AddRebar(plan, spec, angle, upperHeight, label + " 上端吊筋");
                AddStrand(plan, EyeHardPoint(spec, angle, upperHeight, upperGround), upperGround,
                    label + "（上层）");
                if (spec.NeedsExtraCable)
                {
                    var middleGround = new EngineeringPoint(
                        spec.OuterRadiusMm * cosine, spec.OuterRadiusMm * sine, 0.0);
                    AddGroundRebar(plan, angle, upperGroundRadius, label + " 下端吊筋（上层）");
                    AddAnchor(plan, upperGround, anchorLabel + "（上层）");

                    double middleHeight = spec.HeightMm / 3.0;
                    AddRebar(plan, spec, angle, middleHeight, label + " 中间层吊筋");
                    AddStrand(plan, EyeHardPoint(spec, angle, middleHeight, middleGround), middleGround,
                        label + "（中间层）");
                    AddGroundRebar(plan, angle, spec.OuterRadiusMm, label + " 下端吊筋（中间层）");
                    AddAnchor(plan, middleGround, anchorLabel + "（中间层）");
                }
                else
                {
                    AddGroundRebar(plan, angle, upperGroundRadius, label + " 下端吊筋");
                    AddAnchor(plan, upperGround, anchorLabel);
                }
            }

            return plan;
        }

        /// <summary>
        /// 中文摘要：H、D、R、拉索外圆半径、拉索根数、是否中间层与实体数；
        /// 同时点明绳眼为简化示意。
        /// </summary>
        internal static string Describe(EngineeringPlan plan, ChimneyCableParameters parameters)
        {
            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
            return string.Format(CultureInfo.CurrentCulture,
                "H {0:0.###} m、D {1:0.###} mm（R {2:0.###}、壁厚 {3:0.###}）；拉索外圆半径 {4:0.###} mm；" +
                "拉索 {5} 根（{6}）、地面锚墩 {7} 个；共 {8} 个实体；上端经连接环板（比筒身半径宽 100、板上 φ24 孔）与 M20 U 形螺栓（两腿各一个螺母）挂接，下端经埋入锚墩的 ∩ 形 φ20 钢筋固定（两层时上层固定点比下层外扩 150），绳眼为真圆弧链放样示意、绳夹跨两段绳。",
                spec.HeightMm / 1000.0,
                spec.DiameterMm,
                spec.RadiusMm,
                spec.WallThicknessMm,
                spec.OuterRadiusMm,
                spec.CableCount,
                spec.NeedsExtraCable
                    ? "H/(2R) = " + Format(spec.ExtraCableRatio) + " > 35，含 H/3 中间层"
                    : "H/(2R) = " + Format(spec.ExtraCableRatio) + " ≤ 35，无中间层",
                spec.AnchorCount,
                plan.PartCount);
        }

        /// <summary>
        /// 筒身：Revolve 矩形 (R−壁厚,0)-(R,0)-(R,H)-(R−壁厚,H)，
        /// 得到上下环形端面保留的空心筒壁；壁厚 = min(max(5, R×0.04), R×0.5)。
        /// </summary>
        private static void AddShell(EngineeringPlan plan, ChimneyCableSpec spec)
        {
            double radius = spec.RadiusMm;
            double inner = radius - spec.WallThicknessMm;
            if (inner <= 0.0)
            {
                throw new InvalidOperationException("筒身壁厚不小于筒身半径，无法生成空心筒壁。");
            }

            var profile = new[]
            {
                new EngineeringPoint(inner, 0.0, 0.0),
                new EngineeringPoint(radius, 0.0, 0.0),
                new EngineeringPoint(radius, 0.0, spec.HeightMm),
                new EngineeringPoint(inner, 0.0, spec.HeightMm)
            };

            var body = plan.Add("筒身");
            body.Color(ShellRed, ShellGreen, ShellBlue);
            body.Add.Add(EngineeringShape.Revolve(profile));
        }

        /// <summary>
        /// 拉索与筒身的连接环板：内缘嵌入筒壁 3 mm、外缘比筒身半径宽 100 的环形板（厚 20），
        /// 上表面与拉索原始切点同高；每个拉索方向开两个 φ24 竖直孔，
        /// 孔心半径 = R + 50（距外缘 50），两孔对称于拉索竖直面、中心距 100，用来穿 U 形螺栓。
        /// </summary>
        private static void AddCollar(
            EngineeringPlan plan, ChimneyCableSpec spec, double[] azimuths,
            double heightMm, string name)
        {
            double inner = spec.RadiusMm - ChimneyCableCatalog.CollarEmbedMm;
            double outer = spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm;
            double bottom = heightMm - ChimneyCableCatalog.CollarThicknessMm;
            if (inner <= 0.0 || outer <= inner)
            {
                throw new InvalidOperationException(name + "尺寸无效，请检查筒身直径。");
            }

            var body = plan.Add(name);
            body.Color(FittingRed, FittingGreen, FittingBlue);

            // 径向矩形绕 Z 轴回转 360°，得到上下端面都保留的环形板。
            body.Add.Add(EngineeringShape.Revolve(new[]
            {
                new EngineeringPoint(inner, 0.0, bottom),
                new EngineeringPoint(outer, 0.0, bottom),
                new EngineeringPoint(outer, 0.0, heightMm),
                new EngineeringPoint(inner, 0.0, heightMm)
            }));

            double holeRadius = ChimneyCableCatalog.CollarHoleRadiusMm(spec.RadiusMm);
            double hole = ChimneyCableCatalog.CollarHoleDiameterMm / 2.0;
            double step = ChimneyCableCatalog.CollarHoleAngleOffset(spec.RadiusMm);
            foreach (double azimuth in azimuths)
            {
                double angle = Radians(azimuth);
                foreach (double side in new[] { -1.0, 1.0 })
                {
                    body.Cut.Add(EngineeringShape.Cylinder(
                        CollarPoint(angle + side * step, holeRadius, bottom - 1.0),
                        CollarPoint(angle + side * step, holeRadius, heightMm + 1.0),
                        hole));
                }
            }
        }

        /// <summary>
        /// U 形吊筋（M20 U 形螺栓）：两腿垂直穿过环板的两个 φ24 孔，板下用半径 = 孔距/2 的
        /// 半圆弯钩相连（肩部仍在孔内），弯钩最低点吊住鸡心环；两腿在板面以上各用一个
        /// M20 六角螺母（对边 30、厚 16）压紧，螺母上方露出约 14 mm 螺纹。
        /// 绳眼整体位于环板下方，与板底留有约 11 mm 净距，不会与板相交。
        /// </summary>
        private static void AddRebar(
            EngineeringPlan plan, ChimneyCableSpec spec, double radians, double heightMm, string name)
        {
            double holeRadius = ChimneyCableCatalog.CollarHoleRadiusMm(spec.RadiusMm);
            double step = ChimneyCableCatalog.CollarHoleAngleOffset(spec.RadiusMm);
            double top = heightMm + ChimneyCableCatalog.RebarAboveCollarMm;
            double shoulder = heightMm - ChimneyCableCatalog.RebarShoulderBelowTopMm;
            double bend = heightMm - ChimneyCableCatalog.RebarBendDepthMm;

            var path = new[]
            {
                CollarPoint(radians + step, holeRadius, top),
                CollarPoint(radians + step, holeRadius, shoulder),
                CollarPoint(radians - step, holeRadius, shoulder),
                CollarPoint(radians - step, holeRadius, top)
            };
            var middles = new EngineeringPoint?[4];
            middles[1] = CollarPoint(radians, holeRadius * Math.Cos(step), bend);

            var body = plan.Add(name);
            body.Color(BoltRed, BoltGreen, BoltBlue);
            body.Add.Add(EngineeringShape.Sweep(
                path, ChimneyCableCatalog.RebarDiameterMm / 2.0, middles));

            // 两个螺母压在环板上表面，把 U 形螺栓固定在板上。
            double nutTop = heightMm + ChimneyCableCatalog.CollarNutHeightMm;
            foreach (double side in new[] { -1.0, 1.0 })
            {
                body.Add.Add(EngineeringShape.HexPrism(
                    CollarPoint(radians + side * step, holeRadius, heightMm),
                    CollarPoint(radians + side * step, holeRadius, nutTop),
                    ChimneyCableCatalog.CollarNutAcrossFlatsMm));
            }
        }

        /// <summary>
        /// 绳眼挂点：鸡心环挂在吊筋弯钩最低点上，绳眼局部原点（绳眼顶）在弯钩中心
        /// 沿拉索向上游 19.516 mm、并沿绳眼平面内法向偏出 8 mm——因为绳眼坐标架把
        /// 工作段绳放在局部 z = −R 上（即拉索轴线本身），绳眼开孔中心在局部 z = 0。
        /// 挂点与拉索方向互相依赖，迭代 4 次即可收敛（角度变化 &lt; 0.3°）。
        /// </summary>
        private static EngineeringPoint EyeHardPoint(
            ChimneyCableSpec spec, double radians, double heightMm, EngineeringPoint ground)
        {
            double holeRadius = ChimneyCableCatalog.CollarHoleRadiusMm(spec.RadiusMm);
            double step = ChimneyCableCatalog.CollarHoleAngleOffset(spec.RadiusMm);
            EngineeringPoint bend = CollarPoint(
                radians, holeRadius * Math.Cos(step),
                heightMm - ChimneyCableCatalog.RebarBendDepthMm);
            double along = ChimneyCableCatalog.RebarToEyeOffsetMm;
            var top = new EngineeringPoint(
                spec.RadiusMm * Math.Cos(radians), spec.RadiusMm * Math.Sin(radians), heightMm);
            for (int iteration = 0; iteration < 4; iteration++)
            {
                EngineeringPoint unit = Normalize(Subtract(ground, top));
                EngineeringPoint side = Normalize(Cross(new EngineeringPoint(0.0, 0.0, 1.0), unit));
                EngineeringPoint inPlane = Normalize(Cross(unit, side));
                top = Subtract(bend, Sum(
                    Scale(unit, along),
                    Scale(inPlane, ChimneyCableCatalog.RopeRadiusMm)));
            }

            return top;
        }

        /// <summary>环板/吊筋上的一点（世界坐标）：方位角 <paramref name="radians"/>、半径、高度。</summary>
        private static EngineeringPoint CollarPoint(double radians, double radius, double z)
        {
            return new EngineeringPoint(radius * Math.Cos(radians), radius * Math.Sin(radians), z);
        }

        /// <summary>
        /// 单根拉索：拉索过短（长度 ≤ 2×TerminalSpan+200）时退化为整根普通圆柱（CAD 行为），
        /// 否则主体自上端 top+unit·span 到下端 bottom−unit·span，两端各加一套绳眼装配；
        /// 下端绳眼挂在锚墩上 U 形钢筋的弯拱顶点上，因此绳轴取“上端挂点 → 下端挂点”，
        /// 不能再用地面锚点，否则下端绳眼会与主绳错开一个横向距离。
        /// </summary>
        private static void AddStrand(
            EngineeringPlan plan, EngineeringPoint top, EngineeringPoint ground, string name)
        {
            // 下端挂点与绳方向互相依赖（挂点偏移量沿绳方向），迭代 4 次收敛。
            EngineeringPoint bottom = ground;
            for (int iteration = 0; iteration < 4; iteration++)
            {
                EngineeringPoint direction = Normalize(Subtract(bottom, top));
                bottom = GroundEyeHardPoint(ground, direction);
            }

            EngineeringPoint axis = Subtract(bottom, top);
            double length = Length(axis);
            if (length <= 1e-6 || double.IsNaN(length) || double.IsInfinity(length))
            {
                throw new InvalidOperationException(name + "的长度无效，请检查参数。");
            }

            EngineeringPoint unit = Scale(axis, 1.0 / length);
            double ropeRadius = ChimneyCableCatalog.RopeRadiusMm;

            var body = plan.Add(name);
            body.Color(RopeRed, RopeGreen, RopeBlue);

            if (length <= ChimneyCableCatalog.ShortCableThresholdMm)
            {
                body.Add.Add(EngineeringShape.Cylinder(top, ground, ropeRadius));
                return;
            }

            double span = ChimneyCableCatalog.TerminalSpanMm;
            body.Add.Add(EngineeringShape.Cylinder(
                Offset(top, unit, span),
                Offset(bottom, unit, -span),
                ropeRadius));

            AddRopeEye(body, plan, top, unit, true, name + " 上端绳眼");
            AddRopeEye(body, plan, bottom, unit, false, name + " 下端绳眼");
        }

        /// <summary>
        /// 地面绳眼挂点：绳眼挂在 U 形钢筋弯拱顶点上，局部原点（绳眼顶）在弯拱顶点
        /// 沿拉索向上游 19.516 mm、沿绳眼平面内法向偏出 8 mm；下端绳眼朝上，
        /// 因此方向与上端相反，直接加在弯拱顶点上。
        /// </summary>
        private static EngineeringPoint GroundEyeHardPoint(EngineeringPoint ground, EngineeringPoint unit)
        {
            var crown = new EngineeringPoint(
                ground.X, ground.Y, ChimneyCableCatalog.GroundRebarCrownMm);
            EngineeringPoint side = Normalize(Cross(new EngineeringPoint(0.0, 0.0, 1.0), unit));
            EngineeringPoint inPlane = Normalize(Cross(unit, side));
            return Sum(crown, Sum(
                Scale(unit, ChimneyCableCatalog.GroundEyeOffsetMm),
                Scale(inPlane, ChimneyCableCatalog.RopeRadiusMm)));
        }

        /// <summary>
        /// 鸡心环的备用几何：旧做法——内外边界都是真圆弧链的环带拉伸（1.316×17 平板）。
        /// 平板在绳圈里会挡住绳子（用户误认为断绳），只在槽形截面扫掠被内核拒绝时使用。
        /// </summary>
        private static EngineeringShape ThimbleBandFallback(
            EyeFrame frame, List<EngineeringPoint> path, List<EngineeringPoint> normals,
            List<int> knots, List<int> mids)
        {
            int count = knots.Count;
            int segments = count - 1;
            var points = new EngineeringPoint[2 * count];
            var arcMids = new EngineeringPoint?[points.Length];
            for (int index = 0; index < count; index++)
            {
                int knot = knots[index];
                points[index] = frame.Map(
                    path[knot].X + normals[knot].X * ChimneyCableCatalog.ThimbleWallMm,
                    0.0,
                    path[knot].Z + normals[knot].Z * ChimneyCableCatalog.ThimbleWallMm);
            }

            for (int index = 0; index < count; index++)
            {
                int knot = knots[count - 1 - index];
                points[count + index] = frame.Map(path[knot].X, 0.0, path[knot].Z);
            }

            for (int index = 0; index < segments; index++)
            {
                int mid = mids[index];
                arcMids[index] = frame.Map(
                    path[mid].X + normals[mid].X * ChimneyCableCatalog.ThimbleWallMm,
                    0.0,
                    path[mid].Z + normals[mid].Z * ChimneyCableCatalog.ThimbleWallMm);
                int reversed = mids[segments - 1 - index];
                arcMids[count + index] = frame.Map(path[reversed].X, 0.0, path[reversed].Z);
            }

            return EngineeringShape.Extrude(
                points,
                frame.Direction(0.0, ChimneyCableCatalog.ThimbleWidthMm, 0.0),
                arcMids);
        }

        /// <summary>
        /// 鸡心环槽形截面（对应 CAD <c>BuildThimble</c> 的 profile）：
        /// 第一坐标 = 相对内背面路径的外偏（mm），第三坐标 = 带宽方向（mm）。
        /// 槽底为抛物线托住钢丝绳内缘、两侧为唇壁，材料全部在路径外侧（朝绳一侧）。
        /// </summary>
        private static EngineeringPoint[] ThimbleChannelProfile()
        {
            double halfWidth = ChimneyCableCatalog.ThimbleWidthMm / 2.0;
            double halfChannel = (ChimneyCableCatalog.ThimbleWidthMm -
                2.0 * ChimneyCableCatalog.ThimbleWallMm) / 2.0;
            double lip = ChimneyCableCatalog.ThimbleDepthMm;
            double floor = ChimneyCableCatalog.ThimbleWallMm;
            const double offset = 0.1;

            var points = new List<EngineeringPoint>
            {
                new EngineeringPoint(offset, 0.0, -halfWidth),
                new EngineeringPoint(offset + lip, 0.0, -halfWidth),
                new EngineeringPoint(offset + lip, 0.0, -halfChannel)
            };

            for (int index = 0; index <= 24; index++)
            {
                double width = -halfChannel + 2.0 * halfChannel * index / 24.0;
                double depth = offset + floor +
                    (lip - floor) * (width / halfChannel) * (width / halfChannel);
                points.Add(new EngineeringPoint(depth, 0.0, width));
            }

            points.Add(new EngineeringPoint(offset + lip, 0.0, halfWidth));
            points.Add(new EngineeringPoint(offset, 0.0, halfWidth));
            return points.ToArray();
        }

        /// <summary>
        /// 地面端 U 形钢筋：∩ 形 φ20，腿距 100、弯拱顶点在地面上 50，两腿直段下到地面以下 200，
        /// 底端向两侧外撇 90°、再上翘一个小钩，便于预埋/浇筑到混凝土里；
        /// 绳眼挂在弯拱顶点上。两腿在拉索竖直面两侧对称，整根钢筋为平面形状。
        /// </summary>
        private static void AddGroundRebar(
            EngineeringPlan plan, double radians, double radiusMm, string name)
        {
            double half = ChimneyCableCatalog.GroundRebarLegSpacingMm / 2.0;
            double crown = ChimneyCableCatalog.GroundRebarCrownMm;
            double shoulder = crown - half;
            double legBottom = ChimneyCableCatalog.GroundRebarLegBottomMm;
            double bend = ChimneyCableCatalog.GroundRebarHookRadiusMm;
            double run = ChimneyCableCatalog.GroundRebarHookRunMm;
            double curl = ChimneyCableCatalog.GroundRebarHookCurlRadiusMm;
            double up = ChimneyCableCatalog.GroundRebarHookCurlUpMm;

            double hookZ = legBottom - bend;              // 水平段高度
            double hookEnd = half + bend + run;           // 水平段外端
            double tipY = hookEnd + curl;                 // 端头上翘处的切向位置
            double tipZ = hookZ + curl;                   // 端头上翘起点

            var plane = new List<EngineeringPoint>
            {
                new EngineeringPoint(tipY, 0.0, tipZ + up),
                new EngineeringPoint(tipY, 0.0, tipZ),
                new EngineeringPoint(hookEnd, 0.0, hookZ),
                new EngineeringPoint(half + bend, 0.0, hookZ),
                new EngineeringPoint(half, 0.0, legBottom),
                new EngineeringPoint(half, 0.0, shoulder),
                new EngineeringPoint(-half, 0.0, shoulder),
                new EngineeringPoint(-half, 0.0, legBottom),
                new EngineeringPoint(-(half + bend), 0.0, hookZ),
                new EngineeringPoint(-hookEnd, 0.0, hookZ),
                new EngineeringPoint(-tipY, 0.0, tipZ),
                new EngineeringPoint(-tipY, 0.0, tipZ + up)
            };

            var path = new EngineeringPoint[plane.Count];
            for (int index = 0; index < plane.Count; index++)
            {
                path[index] = GroundPoint(radians, radiusMm, plane[index].X, plane[index].Z);
            }

            double diagonal = Math.Sqrt(0.5);
            var middles = new EngineeringPoint?[plane.Count];
            middles[1] = GroundPoint(radians, radiusMm, hookEnd + curl * diagonal, hookZ + curl * diagonal);
            middles[3] = GroundPoint(radians, radiusMm, half + bend - bend * diagonal, hookZ + bend * diagonal);
            middles[5] = GroundPoint(radians, radiusMm, 0.0, crown);
            middles[7] = GroundPoint(radians, radiusMm, -(half + bend - bend * diagonal),
                hookZ + bend * diagonal);
            middles[9] = GroundPoint(radians, radiusMm, -(hookEnd + curl * diagonal),
                hookZ + curl * diagonal);

            var body = plan.Add(name);
            body.Color(BoltRed, BoltGreen, BoltBlue);
            body.Add.Add(EngineeringShape.Sweep(
                path, ChimneyCableCatalog.RebarDiameterMm / 2.0, middles));
        }

        /// <summary>
        /// 地面端点上的一点：方位角 <paramref name="radians"/>、半径 <paramref name="radiusMm"/>，
        /// 沿切向偏移 <paramref name="tangential"/>、高度 <paramref name="z"/>。
        /// </summary>
        private static EngineeringPoint GroundPoint(
            double radians, double radiusMm, double tangential, double z)
        {
            double cosine = Math.Cos(radians);
            double sine = Math.Sin(radians);
            return new EngineeringPoint(
                radiusMm * cosine - tangential * sine,
                radiusMm * sine + tangential * cosine,
                z);
        }

        /// <summary>
        /// 去掉路径两端累计长度不足 <paramref name="trim"/> 的点（至少保留 3 点）。
        /// 用于把鸡心环环带的两端缩进绳圈转折点以内。
        /// </summary>
        private static List<EngineeringPoint> TrimPath(List<EngineeringPoint> path, double trim)
        {
            if (path == null || path.Count < 5 || trim <= 0.0)
            {
                return path == null ? new List<EngineeringPoint>() : new List<EngineeringPoint>(path);
            }

            int start = 0;
            double travelled = 0.0;
            while (start + 3 < path.Count && travelled < trim)
            {
                travelled += Length(Subtract(path[start + 1], path[start]));
                start++;
            }

            int end = path.Count - 1;
            travelled = 0.0;
            while (end - start > 2 && travelled < trim)
            {
                travelled += Length(Subtract(path[end], path[end - 1]));
                end--;
            }

            var result = new List<EngineeringPoint>(end - start + 1);
            for (int index = start; index <= end; index++)
            {
                result.Add(path[index]);
            }

            return result;
        }

        /// <summary>
        /// 在挂点处放一套绳眼装配，轴向沿拉索、上端向下、下端向上。
        ///
        /// 与 CAD <c>RopeEyeAssemblySolidService</c> 的差异（均为简化，但曲线本身是光滑的）：
        /// 1) 鸡心环为内径 φ38、带宽 17、壁厚 1.316 的**光滑环带**，沿泪滴路径以 B 样条
        ///    扫掠矩形截面；不还原槽形截面、唇壁抛物线槽底与端口倒角；
        /// 2) 绳圈为**真圆弧链**（每两采样点一段真圆弧，共线处退化为直线）放样成的单一光滑管面，
        ///    覆盖“工作段 → 过渡 → 绕鸡心环泪滴 → 过渡 → 尾段”，不再用折线采样，
        ///    也不逐段扫掠（逐段扫掠会在每段接缝留下横向棱线）；放样不可用时退回扫掠；
        /// 3) 绳夹为跨两段绳的真实夹持：鞍座压在 z = −R 的工作段外侧（32×63×20，φ17 绳槽），
        ///    U 形螺栓绕过 z = +R+1 的尾段，两腿穿过鞍座后在另一侧用 M14 螺母拧紧；
        ///    不还原肩部贝塞尔轮廓与绳夹总高 77 的鞍形；
        /// 4) U 形螺栓用真半圆弧顶 + 两直腿扫掠，六角螺母对边 21、高 11 用正六棱柱；
        /// 5) 尾段绳比工作段绳多让 1 mm，避免扫掠体自相切。
        /// </summary>
        private static void AddRopeEye(
            EngineeringBody rope, EngineeringPlan plan, EngineeringPoint hardPoint,
            EngineeringPoint axis, bool fromTop, string name)
        {
            EyeFrame frame = EyeFrame.Create(hardPoint, axis, fromTop);

            List<EngineeringPoint> inner = ThimbleInnerPath();
            List<EngineeringPoint> normals = OutwardNormals(inner);
            double mouthX = inner[inner.Count - 1].X;

            // ---- 钢丝绳绳圈：沿鸡心环内侧泪滴路径扫掠 φ16 圆截面，
            //      两直段端点伸入主体 8 mm，与拉索主体同一实体相并（UnionAdd）。
            List<EngineeringPoint> loop = OffsetPath(inner, normals, ChimneyCableCatalog.RopeEyeOffsetMm);
            List<EngineeringPoint> path = RopeEyePath(loop, mouthX);
            var knots = new List<int>();
            var midIndices = new List<int>();
            ArcChain(path, knots, midIndices);

            var world = new EngineeringPoint[knots.Count];
            var worldMids = new EngineeringPoint?[knots.Count];
            for (int index = 0; index < knots.Count; index++)
            {
                world[index] = frame.Map(path[knots[index]].X, 0.0, path[knots[index]].Z);
                worldMids[index] = index < midIndices.Count
                    ? frame.Map(path[midIndices[index]].X, 0.0, path[midIndices[index]].Z)
                    : (EngineeringPoint?)null;
            }

            // 绳圈沿同一圆弧链放样成单一光滑管面：截面全为真圆、坐标架由绳眼平面法向定死，
            // 因而没有逐段扫掠留下的一圈圈横向棱线；内核拒绝放样时自动退回扫掠。
            rope.Add.Add(EngineeringShape.Loft(
                world, ChimneyCableCatalog.RopeRadiusMm, worldMids,
                frame.Direction(0.0, 1.0, 0.0)));

            // ---- 鸡心环：按 CAD 的**开口槽形截面**沿泪滴内背面路径扫掠：
            //      槽底（抛物线）托住钢丝绳内缘、两侧唇壁高 C、带宽 B=17、壁厚 1.316；
            //      截面材料在路径外侧（朝绳子一侧），绳坐在槽里，不会像扁带那样挡住绳子。
            //      两端向绳眼口内缩 ThimbleEndTrimMm，避免端面从两股绳之间穿出。
            List<EngineeringPoint> bandPath = TrimPath(inner, ChimneyCableCatalog.ThimbleEndTrimMm);
            List<EngineeringPoint> bandNormals = OutwardNormals(bandPath);
            var innerKnots = new List<int>();
            var innerMidIndices = new List<int>();
            ArcChain(bandPath, innerKnots, innerMidIndices);

            var bandWorld = new EngineeringPoint[innerKnots.Count];
            var bandMids = new EngineeringPoint?[innerKnots.Count];
            for (int index = 0; index < innerKnots.Count; index++)
            {
                int knot = innerKnots[index];
                bandWorld[index] = frame.Map(bandPath[knot].X, 0.0, bandPath[knot].Z);
                bandMids[index] = index < innerMidIndices.Count
                    ? frame.Map(bandPath[innerMidIndices[index]].X, 0.0, bandPath[innerMidIndices[index]].Z)
                    : (EngineeringPoint?)null;
            }

            var thimble = plan.Add(name + " 鸡心环");
            thimble.Color(FittingRed, FittingGreen, FittingBlue);
            EngineeringShape thimbleShape = EngineeringShape.ProfileSweep(
                bandWorld,
                ThimbleChannelProfile(),
                bandMids,
                frame.Direction(0.0, 1.0, 0.0),
                frame.Direction(bandNormals[innerKnots[0]].X, 0.0, bandNormals[innerKnots[0]].Z));
            thimbleShape.Fallback = ThimbleBandFallback(frame, bandPath, bandNormals, innerKnots, innerMidIndices);
            thimble.Add.Add(thimbleShape);

            // ---- 3 只绳夹：首只中心距绳眼口 72，其后每 104 等距。
            for (int index = 0; index < ChimneyCableCatalog.ClipCount; index++)
            {
                double clipX = mouthX + ChimneyCableCatalog.FirstClipOffsetMm +
                    index * ChimneyCableCatalog.ClipSpacingMm;
                AddClip(plan, frame, clipX, name + " 绳夹 " +
                    (index + 1).ToString(CultureInfo.InvariantCulture));
            }
        }

        /// <summary>
        /// 一只绳夹：鞍座压在**工作段**绳（局部 z = −R）外侧，U 形螺栓绕过**尾段**绳
        /// （z = +R）后两条直腿穿过鞍座，螺母在鞍座外侧拧紧，从而把两段绳扣在一起。
        /// </summary>
        private static void AddClip(EngineeringPlan plan, EyeFrame frame, double clipX, string name)
        {
            double radius = ChimneyCableCatalog.RopeRadiusMm;
            double liveZ = -radius;
            double tailZ = radius + StrandGapMm;
            double length = ChimneyCableCatalog.ClipSeatLengthMm;
            double width = ChimneyCableCatalog.ClipSeatWidthMm;
            double thickness = ChimneyCableCatalog.ClipSeatThicknessMm;
            double seatTop = liveZ;
            double seatBottom = seatTop - thickness;
            double half = ChimneyCableCatalog.ClipAcrossMm / 2.0;

            var seat = plan.Add(name + " 夹座");
            seat.Color(FittingRed, FittingGreen, FittingBlue);
            seat.BestEffortCut = true;
            seat.Add.Add(EngineeringShape.Extrude(
                new[]
                {
                    frame.Map(clipX - length / 2.0, -width / 2.0, seatBottom),
                    frame.Map(clipX + length / 2.0, -width / 2.0, seatBottom),
                    frame.Map(clipX + length / 2.0, width / 2.0, seatBottom),
                    frame.Map(clipX - length / 2.0, width / 2.0, seatBottom)
                },
                frame.Direction(0.0, 0.0, thickness)));

            seat.Cut.Add(EngineeringShape.Cylinder(
                frame.Map(clipX - length, 0.0, liveZ),
                frame.Map(clipX + length, 0.0, liveZ),
                ChimneyCableCatalog.ClipGrooveRadiusMm));

            double holeRadius =
                (ChimneyCableCatalog.BoltDiameterMm + ChimneyCableCatalog.BoltHoleClearanceMm) / 2.0;
            foreach (double side in new[] { -1.0, 1.0 })
            {
                seat.Cut.Add(EngineeringShape.Cylinder(
                    frame.Map(clipX, side * half, seatBottom - 1.0),
                    frame.Map(clipX, side * half, seatTop + 1.0),
                    holeRadius));
            }

            double endZ = seatBottom - ChimneyCableCatalog.NutHeightMm + 1.0;
            var bolt = plan.Add(name + " U 形螺栓与螺母");
            bolt.Color(BoltRed, BoltGreen, BoltBlue);
            EngineeringPoint?[] arcMiddles;
            EngineeringPoint[] path = UBoltPath(frame, clipX, tailZ, half, endZ, out arcMiddles);
            bolt.Add.Add(EngineeringShape.Sweep(
                path, ChimneyCableCatalog.BoltDiameterMm / 2.0, arcMiddles));

            foreach (double side in new[] { -1.0, 1.0 })
            {
                bolt.Add.Add(EngineeringShape.HexPrism(
                    frame.Map(clipX, side * half, endZ - 1.0),
                    frame.Map(clipX, side * half,
                        endZ - 1.0 + ChimneyCableCatalog.NutHeightMm),
                    ChimneyCableCatalog.NutAcrossFlatsMm));
            }
        }

        /// <summary>
        /// U 形螺栓路径（局部坐标）：两条直腿沿 Z 穿过鞍座，顶部为绕尾段绳的 180° 真圆弧
        /// （半径 = 两腿中心距/2），腿端伸入螺母 1 mm 便于并集搭接。
        /// </summary>
        private static EngineeringPoint[] UBoltPath(
            EyeFrame frame, double clipX, double tailZ, double half, double endZ,
            out EngineeringPoint?[] arcMiddles)
        {
            var path = new[]
            {
                frame.Map(clipX, -half, endZ),
                frame.Map(clipX, -half, tailZ),
                frame.Map(clipX, half, tailZ),
                frame.Map(clipX, half, endZ)
            };

            arcMiddles = new EngineeringPoint?[4];
            arcMiddles[1] = frame.Map(clipX, 0.0, tailZ + half);
            return path;
        }

        /// <summary>
        /// 绳眼装配在绳眼平面内的完整绳路径（局部 x = 沿绳轴向内、z = 平面内横向）：
        /// 主体内 8 mm 起 → 工作段 → 过渡贝塞尔 → 绕鸡心环泪滴 → 过渡贝塞尔 → 尾段自由端。
        /// 工作段位于 z = −R（与拉索主体同轴），尾段位于 z = R + 间隙。
        /// </summary>
        private static List<EngineeringPoint> RopeEyePath(List<EngineeringPoint> loop, double mouthX)
        {
            double radius = ChimneyCableCatalog.RopeRadiusMm;
            double blendX = mouthX + BlendRunMm;
            double bodyX = ChimneyCableCatalog.RopeEyeStubMm;
            double tailX = mouthX + ChimneyCableCatalog.TailEndOffsetMm;
            double tailZ = radius + StrandGapMm;

            var path = new List<EngineeringPoint>();
            AddUnique(path, new EngineeringPoint(bodyX, 0.0, -radius));
            AddUnique(path, new EngineeringPoint(blendX, 0.0, -radius));

            EngineeringPoint start = loop[0];
            AddCubic(path,
                blendX, -radius,
                blendX - 14.0, -radius,
                start.X + 14.0, start.Z,
                start.X, start.Z,
                BlendSamples);

            for (int index = 1; index < loop.Count; index++)
            {
                AddUnique(path, loop[index]);
            }

            EngineeringPoint end = loop[loop.Count - 1];
            AddCubic(path,
                end.X, end.Z,
                end.X + 14.0, end.Z,
                blendX - 14.0, tailZ,
                blendX, tailZ,
                BlendSamples);

            AddUnique(path, new EngineeringPoint(tailX, 0.0, tailZ));
            return path;
        }

        /// <summary>
        /// 鸡心环内背面泪滴路径（局部 x = 沿绳轴向内、z = 平面内横向）：
        /// 绳眼口 (±端口间隙/2) → 左腿贝塞尔 → 冠部半圆（半径 = 内径/2）→ 右腿贝塞尔。
        /// 冠部顶点 = 绳眼顶 + 壁厚 + 绳半径 + 间隙（即 RopeEyeOffset），
        /// 最宽处 ±内径/2 = ±19，绳眼口在 x = −ApexOffset = 93.816。
        /// </summary>
        private static List<EngineeringPoint> ThimbleInnerPath()
        {
            double innerRadius = ChimneyCableCatalog.ThimbleInnerDiameterMm / 2.0;
            double crownX = ChimneyCableCatalog.RopeEyeOffsetMm;
            double centerX = crownX + innerRadius;
            double mouthX = crownX +
                (ChimneyCableCatalog.ThimbleLengthMm - ChimneyCableCatalog.ThimbleDepthMm);
            double halfGap = ChimneyCableCatalog.ThimbleGapMm / 2.0;
            double legRun = ChimneyCableCatalog.ThimbleLengthMm -
                ChimneyCableCatalog.ThimbleDepthMm - ChimneyCableCatalog.ThimbleHingeLengthMm;
            double throatRun = ChimneyCableCatalog.ThimbleLengthMm -
                ChimneyCableCatalog.ThimbleDepthMm - innerRadius;

            var path = new List<EngineeringPoint>();

            AddCubic(path,
                mouthX, -halfGap,
                mouthX - legRun * 1.25, -halfGap,
                mouthX - (throatRun + legRun) * 0.52, -innerRadius,
                centerX, -innerRadius,
                ThimbleLegSamples);

            for (int sample = 1; sample <= ThimbleArcSamples; sample++)
            {
                double angle = -Math.PI / 2.0 - Math.PI * sample / ThimbleArcSamples;
                AddUnique(path, new EngineeringPoint(
                    centerX + innerRadius * Math.Cos(angle), 0.0, innerRadius * Math.Sin(angle)));
            }

            AddCubic(path,
                centerX, innerRadius,
                mouthX - (throatRun + legRun) * 0.52, innerRadius,
                mouthX - legRun * 1.25, halfGap,
                mouthX, halfGap,
                ThimbleLegSamples);

            return path;
        }

        /// <summary>
        /// 泪滴路径上每点的外法向（局部 xz 平面）。路径按“绳眼口 → 冠部 → 绳眼口”的
        /// 顺时针方向排列，切向逆时针旋转 90° 即外侧法向：(−tz, tx)。
        /// </summary>
        private static List<EngineeringPoint> OutwardNormals(List<EngineeringPoint> path)
        {
            var normals = new List<EngineeringPoint>(path.Count);
            for (int index = 0; index < path.Count; index++)
            {
                EngineeringPoint previous = path[index == 0 ? 0 : index - 1];
                EngineeringPoint next = path[index == path.Count - 1 ? index : index + 1];
                double tangentX = next.X - previous.X;
                double tangentZ = next.Z - previous.Z;
                double length = Math.Sqrt(tangentX * tangentX + tangentZ * tangentZ);
                if (length < 1e-9)
                {
                    normals.Add(new EngineeringPoint(0.0, 0.0, 0.0));
                    continue;
                }

                normals.Add(new EngineeringPoint(-tangentZ / length, 0.0, tangentX / length));
            }

            return normals;
        }

        /// <summary>沿每点外法向偏移一条局部 xz 折线。</summary>
        private static List<EngineeringPoint> OffsetPath(
            List<EngineeringPoint> path, List<EngineeringPoint> normals, double offset)
        {
            var result = new List<EngineeringPoint>(path.Count);
            for (int index = 0; index < path.Count; index++)
            {
                result.Add(new EngineeringPoint(
                    path[index].X + normals[index].X * offset,
                    0.0,
                    path[index].Z + normals[index].Z * offset));
            }

            return result;
        }

        /// <summary>追加三次贝塞尔采样点（局部 xz 平面，含起点，重复点由 <see cref="AddUnique"/> 合并）。</summary>
        private static void AddCubic(
            List<EngineeringPoint> path,
            double x0, double z0, double x1, double z1,
            double x2, double z2, double x3, double z3, int samples)
        {
            for (int sample = 0; sample <= samples; sample++)
            {
                double t = (double)sample / samples;
                double u = 1.0 - t;
                double x = u * u * u * x0 + 3.0 * u * u * t * x1 + 3.0 * u * t * t * x2 + t * t * t * x3;
                double z = u * u * u * z0 + 3.0 * u * u * t * z1 + 3.0 * u * t * t * z2 + t * t * t * z3;
                AddUnique(path, new EngineeringPoint(x, 0.0, z));
            }
        }

        /// <summary>追加点并跳过与上一点重复（阈值 1e-7）的点，避免扫掠路径出现零长段。</summary>
        private static void AddUnique(List<EngineeringPoint> path, EngineeringPoint point)
        {
            if (path.Count > 0)
            {
                EngineeringPoint last = path[path.Count - 1];
                if (Math.Abs(last.X - point.X) < 1e-7 && Math.Abs(last.Z - point.Z) < 1e-7)
                {
                    return;
                }
            }

            path.Add(point);
        }

        /// <summary>
        /// 把采样折线转成“真圆弧链”：每两个采样点取一个节点，中间采样点作为圆弧中间点。
        /// 相邻圆弧在节点处共用切线方向，所以整体是光滑曲线而不是折线。
        /// </summary>
        private static void ArcChain(
            List<EngineeringPoint> samples, List<int> knots, List<int> midIndices)
        {
            knots.Clear();
            midIndices.Clear();
            for (int index = 0; index + 2 < samples.Count; index += 2)
            {
                knots.Add(index);
                midIndices.Add(index + 1);
            }

            int last = samples.Count - 1;
            if (knots.Count == 0 || knots[knots.Count - 1] != last)
            {
                knots.Add(last);
            }
        }

        /// <summary>按步长抽稀拟合点，避免高密度点让插值样条在急弯处过冲；首尾点始终保留。</summary>
        private static List<EngineeringPoint> Thin(List<EngineeringPoint> points, int step)
        {
            if (points == null || points.Count <= 3 || step < 2)
            {
                return points == null ? new List<EngineeringPoint>() : new List<EngineeringPoint>(points);
            }

            var result = new List<EngineeringPoint>(points.Count / step + 2);
            for (int index = 0; index < points.Count; index++)
            {
                if (index == 0 || index == points.Count - 1 || index % step == 0)
                {
                    result.Add(points[index]);
                }
            }

            return result;
        }

        /// <summary>地面锚墩：半径 24、高 16 的圆柱，圆心 = 地面端，z 范围 −4～12（1/4 埋入地面）。</summary>
        private static void AddAnchor(EngineeringPlan plan, EngineeringPoint ground, string name)
        {
            var body = plan.Add(name);
            body.Color(AnchorRed, AnchorGreen, AnchorBlue);
            body.Add.Add(EngineeringShape.Cylinder(
                ground.Offset(0.0, 0.0, -ChimneyCableCatalog.AnchorBuriedDepthMm),
                ground.Offset(0.0, 0.0,
                    ChimneyCableCatalog.AnchorHeightMm - ChimneyCableCatalog.AnchorBuriedDepthMm),
                ChimneyCableCatalog.AnchorRadiusMm));
        }

        /// <summary>
        /// 绳眼装配的局部坐标架：
        /// X = 沿绳轴向内（自挂点指向跨中），Y = 绳眼平面法向（世界 Z × 绳轴，近竖直退化为 X），
        /// Z = 平面内横向（两股绳的分开方向）；原点沿 Z 偏一个绳半径，
        /// 使局部 z = −R 的工作段绳与拉索主体同轴。
        /// </summary>
        private sealed class EyeFrame
        {
            internal EngineeringPoint Origin;
            internal EngineeringPoint X;
            internal EngineeringPoint Y;
            internal EngineeringPoint Z;

            /// <summary>局部坐标 → 世界坐标。</summary>
            internal EngineeringPoint Map(double x, double y, double z)
            {
                return new EngineeringPoint(
                    Origin.X + X.X * x + Y.X * y + Z.X * z,
                    Origin.Y + X.Y * x + Y.Y * y + Z.Y * z,
                    Origin.Z + X.Z * x + Y.Z * y + Z.Z * z);
            }

            /// <summary>局部方向 → 世界方向（不含平移）。</summary>
            internal EngineeringPoint Direction(double x, double y, double z)
            {
                return new EngineeringPoint(
                    X.X * x + Y.X * y + Z.X * z,
                    X.Y * x + Y.Y * y + Z.Y * z,
                    X.Z * x + Y.Z * y + Z.Z * z);
            }

            /// <summary>
            /// 按挂点与拉索单位轴建立坐标架：上端轴向朝下、下端轴向朝上，
            /// 平面法向两端都取世界 Z × 绳轴（与 CAD AddStrandEye 一致，近竖直退化为 X）；
            /// 因此两端局部 Z（两股绳分开方向）指向相反，绳夹夹座都朝挂点外侧。
            /// </summary>
            internal static EyeFrame Create(EngineeringPoint hardPoint, EngineeringPoint unit, bool fromTop)
            {
                EngineeringPoint eyeX = fromTop ? unit : Scale(unit, -1.0);
                EngineeringPoint cross = Cross(new EngineeringPoint(0.0, 0.0, 1.0), unit);
                EngineeringPoint eyeY = Length(cross) < 1e-6
                    ? new EngineeringPoint(1.0, 0.0, 0.0)
                    : Normalize(cross);
                EngineeringPoint eyeZ = Normalize(Cross(eyeX, eyeY));
                var frame = new EyeFrame { X = eyeX, Y = eyeY, Z = eyeZ };
                frame.Origin = hardPoint.Offset(
                    eyeZ.X * ChimneyCableCatalog.RopeRadiusMm,
                    eyeZ.Y * ChimneyCableCatalog.RopeRadiusMm,
                    eyeZ.Z * ChimneyCableCatalog.RopeRadiusMm);
                return frame;
            }
        }

        private static double Radians(double degrees)
        {
            return degrees * Math.PI / 180.0;
        }

        private static EngineeringPoint Sum(EngineeringPoint a, EngineeringPoint b)
        {
            return new EngineeringPoint(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        }

        private static EngineeringPoint Subtract(EngineeringPoint a, EngineeringPoint b)
        {
            return new EngineeringPoint(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        }

        private static EngineeringPoint Scale(EngineeringPoint value, double factor)
        {
            return new EngineeringPoint(value.X * factor, value.Y * factor, value.Z * factor);
        }

        private static EngineeringPoint Offset(EngineeringPoint origin, EngineeringPoint unit, double distance)
        {
            return Sum(origin, Scale(unit, distance));
        }

        private static double Length(EngineeringPoint value)
        {
            return Math.Sqrt(value.X * value.X + value.Y * value.Y + value.Z * value.Z);
        }

        private static EngineeringPoint Normalize(EngineeringPoint value)
        {
            double length = Length(value);
            if (length < 1e-12)
            {
                throw new InvalidOperationException("拉索方向无法建立绳眼坐标架。");
            }

            return Scale(value, 1.0 / length);
        }

        private static EngineeringPoint Cross(EngineeringPoint a, EngineeringPoint b)
        {
            return new EngineeringPoint(
                a.Y * b.Z - a.Z * b.Y,
                a.Z * b.X - a.X * b.Z,
                a.X * b.Y - a.Y * b.X);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
