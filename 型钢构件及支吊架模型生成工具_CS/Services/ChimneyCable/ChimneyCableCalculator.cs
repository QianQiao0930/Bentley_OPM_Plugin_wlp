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
            for (int index = 0; index < azimuths.Length; index++)
            {
                double angle = Radians(azimuths[index]);
                double cosine = Math.Cos(angle);
                double sine = Math.Sin(angle);
                string label = "拉索 " + (index + 1).ToString(CultureInfo.InvariantCulture);

                var top = new EngineeringPoint(
                    spec.RadiusMm * cosine, spec.RadiusMm * sine, 2.0 * spec.HeightMm / 3.0);
                var ground = new EngineeringPoint(
                    spec.OuterRadiusMm * cosine, spec.OuterRadiusMm * sine, 0.0);

                AddStrand(plan, top, ground, label + "（上层）");
                if (spec.NeedsExtraCable)
                {
                    var middleTop = new EngineeringPoint(
                        spec.RadiusMm * cosine, spec.RadiusMm * sine, spec.HeightMm / 3.0);
                    AddStrand(plan, middleTop, ground, label + "（中间层）");
                }

                AddAnchor(plan, ground, "地面锚墩 " + (index + 1).ToString(CultureInfo.InvariantCulture));
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
                "拉索 {5} 根（{6}）、地面锚墩 {7} 个；共 {8} 个实体；绳眼为光滑样条示意、绳夹跨两段绳。",
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
        /// 单根拉索：拉索过短（长度 ≤ 2×TerminalSpan+200）时退化为整根普通圆柱（CAD 行为），
        /// 否则主体自上端 top+unit·span 到下端 ground−unit·span，两端各加一套绳眼装配。
        /// </summary>
        private static void AddStrand(
            EngineeringPlan plan, EngineeringPoint top, EngineeringPoint ground, string name)
        {
            EngineeringPoint axis = Subtract(ground, top);
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
                Offset(ground, unit, -span),
                ropeRadius));

            AddRopeEye(body, plan, top, unit, true, name + " 上端绳眼");
            AddRopeEye(body, plan, ground, unit, false, name + " 下端绳眼");
        }

        /// <summary>
        /// 在挂点处放一套绳眼装配，轴向沿拉索、上端向下、下端向上。
        ///
        /// 与 CAD <c>RopeEyeAssemblySolidService</c> 的差异（均为简化，但曲线本身是光滑的）：
        /// 1) 鸡心环为内径 φ38、带宽 17、壁厚 1.316 的**光滑环带**，沿泪滴路径以 B 样条
        ///    扫掠矩形截面；不还原槽形截面、唇壁抛物线槽底与端口倒角；
        /// 2) 绳圈为**真圆弧链**（每两采样点一段真圆弧，共线处退化为直线）扫掠 φ16 圆截面，
        ///    覆盖“工作段 → 过渡 → 绕鸡心环泪滴 → 过渡 → 尾段”，不再用折线采样；
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

            // 绳圈用真圆弧链扫掠（相邻圆弧切向连续），不采样成折线。
            rope.Add.Add(EngineeringShape.Sweep(
                world, ChimneyCableCatalog.RopeRadiusMm, worldMids));

            // ---- 鸡心环：内径 φ38、带宽 17、壁厚 1.316 的环带；
            //      内外边界均为真圆弧链，沿带宽方向拉伸。
            var innerKnots = new List<int>();
            var innerMidIndices = new List<int>();
            ArcChain(inner, innerKnots, innerMidIndices);
            var bandPoints = new EngineeringPoint[2 * innerKnots.Count];
            var bandMids = new EngineeringPoint?[bandPoints.Length];
            int knotCount = innerKnots.Count - 1;
            for (int index = 0; index < innerKnots.Count; index++)
            {
                int knot = innerKnots[index];
                bandPoints[index] = frame.Map(
                    inner[knot].X + normals[knot].X * ChimneyCableCatalog.ThimbleWallMm,
                    0.0,
                    inner[knot].Z + normals[knot].Z * ChimneyCableCatalog.ThimbleWallMm);
            }

            for (int index = 0; index < innerKnots.Count; index++)
            {
                int knot = innerKnots[innerKnots.Count - 1 - index];
                bandPoints[innerKnots.Count + index] = frame.Map(
                    inner[knot].X, 0.0, inner[knot].Z);
            }

            for (int index = 0; index < knotCount; index++)
            {
                int mid = innerMidIndices[index];
                bandMids[index] = frame.Map(
                    inner[mid].X + normals[mid].X * ChimneyCableCatalog.ThimbleWallMm,
                    0.0,
                    inner[mid].Z + normals[mid].Z * ChimneyCableCatalog.ThimbleWallMm);
                int reversed = innerMidIndices[knotCount - 1 - index];
                bandMids[innerKnots.Count + index] = frame.Map(
                    inner[reversed].X, 0.0, inner[reversed].Z);
            }

            var thimble = plan.Add(name + " 鸡心环");
            thimble.Color(FittingRed, FittingGreen, FittingBlue);
            thimble.Add.Add(EngineeringShape.Extrude(
                bandPoints,
                frame.Direction(0.0, ChimneyCableCatalog.ThimbleWidthMm, 0.0),
                bandMids));

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
            double bodyX = mouthX + ChimneyCableCatalog.JunctionOffsetMm + BodyPenetrationMm;
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
