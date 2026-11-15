using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱拉索的规则表与输入校核：迁移自 AutoCAD 版
    /// <c>CableStayedChimneyGeometry</c>（拉索外圆半径、中间层判据、三根拉索方位角）
    /// 与 <c>RopeEyeAssemblySolidService</c> 的 φ16 绳眼装配常量。
    /// 纯计算，不依赖 Bentley；角度单位为度，长度单位为 mm。
    /// 绳眼装配常量直接写成最终数值，并用常量表达式保留 CAD 的推导链，避免重复推导产生偏差。
    /// </summary>
    internal static class ChimneyCableCatalog
    {
        /// <summary>H/(2R) 超过该值时在 H/3 高度补挂中间层拉索（与 LISP 阈值 35 一致）。</summary>
        internal const double ExtraCableRatioThreshold = 35.0;

        /// <summary>
        /// 三根拉索的方位角（°）：与 LISP 俯视图 / CAD 三维插值一致，
        /// 依次为 30°、270°、150°（CAD 中为 π/6、3π/2、5π/6）。
        /// </summary>
        internal static readonly double[] CableAzimuthDegrees = { 30.0, 270.0, 150.0 };

        // ---------------------------------------------------------------
        // 筒身
        // ---------------------------------------------------------------

        /// <summary>筒身最小壁厚（mm）：壁厚 = min(max(5, R×0.04), R×0.5)。</summary>
        internal const double MinWallThicknessMm = 5.0;

        /// <summary>筒身壁厚相对筒身半径的比例系数：R×0.04。</summary>
        internal const double WallThicknessRatio = 0.04;

        // ---------------------------------------------------------------
        // φ16 钢丝绳与绳眼装配轴向长度
        // ---------------------------------------------------------------

        /// <summary>钢丝绳公称直径（mm）。</summary>
        internal const double RopeDiameterMm = 16.0;

        /// <summary>钢丝绳半径（mm）。</summary>
        internal const double RopeRadiusMm = 8.0;

        /// <summary>
        /// 绳眼顶（鸡心环冠部绳中心线）相对装配原点的轴向偏移（mm），负值表示在绳眼口之前。
        /// CAD：−(L − C + RopeEyeOffset) = −(89 − 4.7 + 9.516) = −93.816。
        /// </summary>
        internal const double ApexOffsetMm = -93.816;

        /// <summary>
        /// 工作段自由端（拉索主体接入端）相对绳眼口的轴向偏移（mm）。
        /// CAD：首夹 72 + 2×104（夹距 6.5φ）+ 9φ（工作段延伸）= 424。
        /// </summary>
        internal const double JunctionOffsetMm = 424.0;

        /// <summary>
        /// 绳眼装配沿绳轴的总长（mm）：自绳眼顶到工作段自由端，CAD 记 ≈330.2。
        /// = JunctionOffset + ApexOffset = 424 − 93.816 = 330.184。
        /// </summary>
        internal const double TerminalSpanMm = JunctionOffsetMm + ApexOffsetMm;

        /// <summary>
        /// 尾段（死头）自由端相对绳眼口的轴向偏移（mm）：
        /// CAD：首夹 72 + 2×104 + 3φ（尾段延伸）= 328。
        /// </summary>
        internal const double TailEndOffsetMm = 328.0;

        /// <summary>
        /// 拉索过短判据（mm）：长度 ≤ 2×TerminalSpan + 200 时退化为整根普通圆柱，
        /// 不放绳眼装配（与 CAD CreateStrand 的退化分支一致）。
        /// </summary>
        internal const double ShortCableThresholdMm = 2.0 * TerminalSpanMm + 200.0;

        // ---------------------------------------------------------------
        // 鸡心环（16 规格表：B = 17、C = 4.7、D = 38、H = 61、L = 89，端口间隙 0.23φ）
        // ---------------------------------------------------------------

        /// <summary>鸡心环带宽（mm，沿绳眼平面法向）。</summary>
        internal const double ThimbleWidthMm = 17.0;

        /// <summary>鸡心环冠部径向总深度 C（mm）。</summary>
        internal const double ThimbleDepthMm = 4.7;

        /// <summary>鸡心环内径 D（mm）。</summary>
        internal const double ThimbleInnerDiameterMm = 38.0;

        /// <summary>鸡心环喉部收口起点高度 H（mm）。</summary>
        internal const double ThimbleHingeLengthMm = 61.0;

        /// <summary>鸡心环总长 L（mm）。</summary>
        internal const double ThimbleLengthMm = 89.0;

        /// <summary>鸡心环端口间隙（mm）：0.23φ = 3.68。</summary>
        internal const double ThimbleGapMm = 3.68;

        /// <summary>
        /// 鸡心环壁厚（mm）：min(C×0.28, B×0.15) = min(1.316, 2.55) = 1.316，取较小者。
        /// </summary>
        internal const double ThimbleWallMm = ThimbleDepthMm * 0.28;

        /// <summary>绳外缘与鸡心环槽底的名义间隙（mm），与 CAD 的 RopeEyeClearance 一致。</summary>
        internal const double RopeEyeClearanceMm = 0.2;

        /// <summary>
        /// 绳中心线相对鸡心环内背面的外偏（mm）：壁厚 + 绳半径 + 间隙 = 9.516。
        /// </summary>
        internal const double RopeEyeOffsetMm = ThimbleWallMm + RopeRadiusMm + RopeEyeClearanceMm;

        // ---------------------------------------------------------------
        // 绳夹（GB/T 5976—2006 16 规格：A = 31、B = 32、C = 63、R = 8.5、H = 77，
        // U 形螺栓 M14，螺母对边 21、高 11）
        // ---------------------------------------------------------------

        /// <summary>绳夹两螺杆中心距 A（mm）。</summary>
        internal const double ClipAcrossMm = 31.0;

        /// <summary>绳夹夹座沿绳轴宽度 B（mm）。</summary>
        internal const double ClipSeatLengthMm = 32.0;

        /// <summary>绳夹夹座横向总宽 C（mm，沿绳眼平面法向）。</summary>
        internal const double ClipSeatWidthMm = 63.0;

        /// <summary>夹座简化方块高度（mm）：保留约 20 的承压块厚度，不还原肩部贝塞尔轮廓。</summary>
        internal const double ClipSeatThicknessMm = 20.0;

        /// <summary>夹座绳槽半径 R（mm）。</summary>
        internal const double ClipGrooveRadiusMm = 8.5;

        /// <summary>绳夹总高 H（mm），仅登记表值，本模块简化模型不按此高度建模。</summary>
        internal const double ClipHeightMm = 77.0;

        /// <summary>U 形螺栓公称直径 M14（mm）。</summary>
        internal const double BoltDiameterMm = 14.0;

        /// <summary>夹座螺栓孔单边间隙（mm）：0.05d = 0.7。</summary>
        internal const double BoltHoleClearanceMm = 0.7;

        /// <summary>六角螺母对边尺寸（mm）。</summary>
        internal const double NutAcrossFlatsMm = 21.0;

        /// <summary>六角螺母厚度（mm）。</summary>
        internal const double NutHeightMm = 11.0;

        /// <summary>绳夹只数：φ16 按表 A.1 最少 3 只。</summary>
        internal const int ClipCount = 3;

        /// <summary>相邻绳夹中心距（mm）：6.5φ = 104。</summary>
        internal const double ClipSpacingMm = 6.5 * RopeDiameterMm;

        /// <summary>
        /// 第一只绳夹中心距绳眼口的距离（mm）：过渡段 2.5φ + 让位 1φ + 夹座半宽 B/2
        /// = 40 + 16 + 16 = 72。
        /// </summary>
        internal const double FirstClipOffsetMm =
            2.5 * RopeDiameterMm + 1.0 * RopeDiameterMm + ClipSeatLengthMm / 2.0;

        // ---------------------------------------------------------------
        // 上端与筒身的连接环板 + U 形吊筋（2026-11-15 用户要求新增）
        // 环板比筒身半径宽 150，板上开 φ40 孔，孔心距环板外缘 50；
        // 吊筋穿两孔、弯钩挂在环板下方，鸡心环挂在弯钩最低点上。
        // ---------------------------------------------------------------

        /// <summary>环板外半径比筒身半径大出的宽度（mm），用户指定 150。</summary>
        internal const double CollarWidthMm = 150.0;

        /// <summary>环板厚度（mm）。</summary>
        internal const double CollarThicknessMm = 20.0;

        /// <summary>环板内缘嵌入筒壁的深度（mm）：避免与筒身外圆柱面同面导致闪现/布尔异常。</summary>
        internal const double CollarEmbedMm = 3.0;

        /// <summary>环板穿孔直径（mm）：用户指定 φ40，用来穿吊筋。</summary>
        internal const double CollarHoleDiameterMm = 40.0;

        /// <summary>孔中心距环板外边缘的距离（mm）：用户指定 50。</summary>
        internal const double CollarHoleEdgeOffsetMm = 50.0;

        /// <summary>
        /// 同一根拉索两个孔的中心距（mm）：两孔对称于拉索竖直面，同时等于 U 形吊筋的弯曲直径，
        /// 使吊筋弯钩正好落在两孔之间的板下。φ40 孔在 ±50 处互不相交（孔边距 20）。
        /// </summary>
        internal const double CollarHoleSpacingMm = 100.0;

        /// <summary>吊筋直径（mm）：φ20 穿 φ40 孔，两侧各留 10 mm 焊接间隙。</summary>
        internal const double RebarDiameterMm = 20.0;

        /// <summary>吊筋高出环板上表面的长度（mm），用于与环板焊接。</summary>
        internal const double RebarAboveCollarMm = 30.0;

        /// <summary>
        /// 吊筋两腿下端（弯钩肩部）相对环板上表面的下移（mm）：仍在孔内（板厚 20）。
        /// 与弯钩半径 50 一起决定弯钩最低点；取 10 使绳眼最高点距板底约 10 mm。
        /// </summary>
        internal const double RebarShoulderBelowTopMm = 10.0;

        /// <summary>孔中心半径（mm）= 筒身半径 + 150 − 50 = R + 100。</summary>
        internal static double CollarHoleRadiusMm(double chimneyRadiusMm)
        {
            return chimneyRadiusMm + CollarWidthMm - CollarHoleEdgeOffsetMm;
        }

        /// <summary>
        /// 同一拉索两个孔相对拉索竖直面的角偏移（rad）。两个孔心都落在半径 R+100 的圆上，
        /// 由弦长 = 孔距 100 反解，因此每个孔心到环板外缘的距离都正好 50。
        /// </summary>
        internal static double CollarHoleAngleOffset(double chimneyRadiusMm)
        {
            double radius = CollarHoleRadiusMm(chimneyRadiusMm);
            double ratio = CollarHoleSpacingMm / 2.0 / radius;
            if (ratio >= 1.0)
            {
                throw new InvalidOperationException("筒身直径过小，环板孔距超过孔心圆周，无法布孔。");
            }

            return Math.Asin(ratio);
        }

        /// <summary>
        /// 吊筋弯钩最低点相对环板上表面的下移（mm）= 肩部 10 + 弯曲半径（孔距/2）= 60。
        /// 由此绳眼顶落在板下约 46，绳眼最高点距板底仍有约 10 mm 净距。
        /// </summary>
        internal const double RebarBendDepthMm = RebarShoulderBelowTopMm + CollarHoleSpacingMm / 2.0;

        /// <summary>
        /// 绳眼挂点（局部原点）到吊筋弯钩最低点中心的斜距（mm）
        /// = 鸡心环内顶点 9.516 + 吊筋半径 10 = 19.516；方向沿拉索向上游。
        /// </summary>
        internal static double RebarToEyeOffsetMm
        {
            get { return RopeEyeOffsetMm + RebarDiameterMm / 2.0; }
        }

        // ---------------------------------------------------------------
        // 地面锚墩与颜色无关的固定尺寸
        // ---------------------------------------------------------------

        /// <summary>地面锚墩半径（mm）：3×绳半径 = 24。</summary>
        internal const double AnchorRadiusMm = 3.0 * RopeRadiusMm;

        /// <summary>地面锚墩高度（mm）：2×绳半径 = 16。</summary>
        internal const double AnchorHeightMm = 2.0 * RopeRadiusMm;

        /// <summary>地面锚墩埋入地面深度（mm）：1/4 高度 = 4，故锚墩 z 范围为 −4～12。</summary>
        internal const double AnchorBuriedDepthMm = AnchorHeightMm / 4.0;

        /// <summary>拉索与竖直方向夹角的正切值。</summary>
        internal static double TangentDegrees(double angleDegrees)
        {
            return Math.Tan(angleDegrees * Math.PI / 180.0);
        }

        /// <summary>
        /// 拉索外圆半径（mm）：Router = R + (2H/3)·tanθ，H 与 R 均为 mm。
        /// </summary>
        internal static double OuterRadius(double heightMm, double radiusMm, double angleDegrees)
        {
            return radiusMm + (2.0 * heightMm / 3.0) * TangentDegrees(angleDegrees);
        }

        /// <summary>正视图/三维是否需要补挂 H/3 高度的中间层拉索。</summary>
        internal static bool NeedsExtraCable(double heightMm, double radiusMm)
        {
            if (radiusMm <= 0.0)
            {
                return false;
            }

            return heightMm / (2.0 * radiusMm) > ExtraCableRatioThreshold;
        }

        /// <summary>
        /// 筒身壁厚（mm）：壁厚 = min(max(5, R×0.04), R×0.5)，
        /// 保证小筒径也能抽出内孔，同时不越过筒身半径。
        /// </summary>
        internal static double WallThickness(double radiusMm)
        {
            return Math.Min(Math.Max(MinWallThicknessMm, radiusMm * WallThicknessRatio), radiusMm * 0.5);
        }

        /// <summary>解析派生几何量；尺寸关系见 <see cref="OuterRadius"/> 与 <see cref="NeedsExtraCable"/>。</summary>
        internal static ChimneyCableSpec Resolve(ChimneyCableParameters parameters)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            double height = parameters.HeightMm;
            double radius = parameters.RadiusMm;
            var spec = new ChimneyCableSpec
            {
                HeightMm = height,
                DiameterMm = parameters.DiameterMm,
                RadiusMm = radius,
                CableAngleDegrees = parameters.CableAngleDegrees,
                OuterRadiusMm = OuterRadius(height, radius, parameters.CableAngleDegrees),
                WallThicknessMm = WallThickness(radius),
                NeedsExtraCable = NeedsExtraCable(height, radius),
                AnchorCount = CableAzimuthDegrees.Length
            };

            spec.ExtraCableRatio = radius > 0.0 ? height / (2.0 * radius) : 0.0;
            spec.CableCount = CableAzimuthDegrees.Length * (spec.NeedsExtraCable ? 2 : 1);
            return spec;
        }

        /// <summary>输入校核，返回中文原因；通过时 error 为空。</summary>
        internal static bool Validate(ChimneyCableParameters parameters, out string error)
        {
            error = null;
            if (parameters == null)
            {
                error = "参数为空。";
                return false;
            }

            if (!Finite(parameters.HeightMeters) ||
                parameters.HeightMeters < ChimneyCableConstants.MinHeightMeters ||
                parameters.HeightMeters > ChimneyCableConstants.MaxHeightMeters)
            {
                error = "排气筒高度 H 需在 " + ChimneyCableConstants.MinHeightMeters + "～" +
                    ChimneyCableConstants.MaxHeightMeters + " m 之间。";
                return false;
            }

            if (!Finite(parameters.DiameterMm) ||
                parameters.DiameterMm < ChimneyCableConstants.MinDiameterMm ||
                parameters.DiameterMm > ChimneyCableConstants.MaxDiameterMm)
            {
                error = "排气筒直径 D 需在 " + ChimneyCableConstants.MinDiameterMm + "～" +
                    ChimneyCableConstants.MaxDiameterMm + " mm 之间。";
                return false;
            }

            if (!Finite(parameters.CableAngleDegrees) ||
                parameters.CableAngleDegrees < ChimneyCableConstants.MinAngleDegrees ||
                parameters.CableAngleDegrees > ChimneyCableConstants.MaxAngleDegrees)
            {
                error = "拉索角度需在 " + ChimneyCableConstants.MinAngleDegrees + "～" +
                    ChimneyCableConstants.MaxAngleDegrees + "° 之间。";
                return false;
            }

            if (!Finite(parameters.HeadingDegrees))
            {
                error = "绕竖轴旋转角必须是有效数字。";
                return false;
            }

            double radius = parameters.RadiusMm;
            double innerRadius = radius - WallThickness(radius);
            if (innerRadius <= 0.0)
            {
                error = "筒身直径过小：壁厚 " + Format(WallThickness(radius)) + " mm 后内腔不足。";
                return false;
            }

            double outerRadius = OuterRadius(parameters.HeightMm, radius, parameters.CableAngleDegrees);
            if (!Finite(outerRadius) || outerRadius <= radius)
            {
                error = "拉索外圆半径需大于筒身半径，请检查高度、直径与拉索角度。";
                return false;
            }

            return true;
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
