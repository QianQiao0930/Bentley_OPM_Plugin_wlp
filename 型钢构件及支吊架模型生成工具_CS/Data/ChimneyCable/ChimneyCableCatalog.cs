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

        // 壁厚自 2026-11-17 起由用户直接输入（默认 10 mm），
        // 不再按 min(max(5, R×0.04), R×0.5) 自动推算；仅保留“必须小于筒身半径”的硬约束。

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
        /// 鸡心环环带两端向绳眼口内缩的长度（mm）：环带端面缩进绳圈转折点以内，
        /// 否则 1.316 厚的薄带端面会从两股绳之间穿出来（用户反馈“鸡心环露片”）。
        /// </summary>
        internal const double ThimbleEndTrimMm = 8.0;

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
        // 上端与筒身的连接环板 + U 形吊筋（2026-11-15 用户要求新增，同日二次调整）
        // 环板比筒身半径宽 100，板上开 φ24 孔，孔心距环板外缘 50；
        // U 形吊筋穿两孔，板下弯钩吊住鸡心环，板面用两个 M20 螺母压紧。
        // ---------------------------------------------------------------

        /// <summary>环板外半径比筒身半径大出的宽度（mm），用户第二次改为 100。</summary>
        internal const double CollarWidthMm = 100.0;

        /// <summary>环板厚度（mm）。</summary>
        internal const double CollarThicknessMm = 20.0;

        /// <summary>环板内缘嵌入筒壁的深度（mm）：避免与筒身外圆柱面同面导致闪现/布尔异常。</summary>
        internal const double CollarEmbedMm = 3.0;

        /// <summary>
        /// 环板穿孔直径（mm）：用户第二次要求“不用那么大的洞”，按 M20 吊筋取 φ24
        /// （单边间隙 2 mm，足够穿装；也小于 M20 螺母对边 30，螺母才能压住孔口）。
        /// </summary>
        internal const double CollarHoleDiameterMm = 24.0;

        /// <summary>孔中心距环板外边缘的距离（mm）：用户指定 50。</summary>
        internal const double CollarHoleEdgeOffsetMm = 50.0;

        /// <summary>
        /// 同一根拉索两个孔的中心距（mm）：两孔对称于拉索竖直面，同时等于 U 形吊筋的弯曲直径，
        /// 使吊筋弯钩正好落在两孔之间的板下。φ24 孔在 ±50 处不相交（孔边距 76）。
        /// </summary>
        internal const double CollarHoleSpacingMm = 100.0;

        /// <summary>吊筋（U 形螺栓）直径（mm）：M20，穿 φ24 孔两侧各留 2 mm 间隙。</summary>
        internal const double RebarDiameterMm = 20.0;

        /// <summary>吊筋两腿高出环板上表面的长度（mm）：螺母 16 + 外露螺纹 14。</summary>
        internal const double RebarAboveCollarMm = 30.0;

        /// <summary>U 形吊筋螺母对边尺寸（mm）：M20 六角螺母 GB/T 41，s = 30。</summary>
        internal const double CollarNutAcrossFlatsMm = 30.0;

        /// <summary>U 形吊筋螺母厚度（mm）：M20 螺母 m = 16。</summary>
        internal const double CollarNutHeightMm = 16.0;

        /// <summary>
        /// 吊筋两腿下端（弯钩肩部）相对环板上表面的下移（mm）：仍在孔内（板厚 20）。
        /// 与弯钩半径 50 一起决定弯钩最低点；取 10 使绳眼最高点距板底约 11 mm。
        /// </summary>
        internal const double RebarShoulderBelowTopMm = 10.0;

        /// <summary>孔中心半径（mm）= 筒身半径 + 100 − 50 = R + 50。</summary>
        internal static double CollarHoleRadiusMm(double chimneyRadiusMm)
        {
            return chimneyRadiusMm + CollarWidthMm - CollarHoleEdgeOffsetMm;
        }

        /// <summary>
        /// 同一拉索两个孔相对拉索竖直面的角偏移（rad）。两个孔心都落在半径 R+50 的圆上，
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
        /// 由此绳眼顶落在板下约 46，绳眼最高点距板底仍有约 11 mm 净距。
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

        /// <summary>
        /// 绳眼弯段工作段伸入绳轴的长度（mm）：绳眼从挂点起画到这一处，与主体圆柱同轴重叠，
        /// 由布尔并集合成一根绳。**不要缩短**：试过改成 150（与主体只搭 12），绳眼路径首段
        /// 由 392 变 20，放样按 24 段采样后相邻截面只差 0.8 mm，放样体退化，
        /// 宿主在“拉索 1（上层）”报 `相并失败：Error`；525 是宿主已验证可用的长度。
        /// </summary>
        internal const double RopeEyeStubMm = 525.0;

        /// <summary>主体圆柱端头距绳眼挂点的距离（mm）：留出与绳眼搭接的长度。</summary>
        internal const double RopeEyeJointMm = RopeEyeStubMm - 195.0;

        // ---------------------------------------------------------------
        // 地面端 φ30 吊环（2026-11-17 用户按“φ30 吊环大样图”要求重做）
        // 一根 φ30 圆钢弯成细长 U 形：环宽 100、露出混凝土面 100、埋深 900，
        // 两条腿底端各弯一个 180° 回钩（中心线半径 37.5、两肢中心距 75、上翘 90）；
        // 绳眼挂在环顶。两层拉索时每个方位两个吊环，沿拉索方向相距 300（四腿平行、互不干涉）。
        // ---------------------------------------------------------------

        /// <summary>
        /// 两层吊索时两个吊环沿拉索方向（径向）的中心距（mm）。
        /// 用户 2026-11-17 明确：大样图 100 宽不变，300 是两个吊环之间的距离。
        /// </summary>
        internal const double GroundRingSpacingMm = 300.0;

        /// <summary>吊环圆钢直径（mm）：大样图 φ30（HPB300 或 Q235B，禁止冷加工、须热弯）。</summary>
        internal const double GroundRingBarMm = 30.0;

        /// <summary>
        /// 吊环两条腿之间的**净距**（mm）：大样图 100（按像素比例核对：净距 100、
        /// 中心距 130、环外宽 160）。因此两腿中心距 = 100 + 30 = 130。
        /// </summary>
        internal const double GroundRingClearMm = 100.0;

        /// <summary>
        /// 吊环露出混凝土面的高度（mm）：大样图 100，量到环顶外缘。
        /// 环顶中心线标高 = 100 − 15 = 85。
        /// </summary>
        internal const double GroundRingExposedMm = 100.0;

        /// <summary>
        /// 吊环埋入混凝土的深度（mm）：大样图 900，量到回钩最低点外缘（即最低点 z = −900）。
        /// </summary>
        internal const double GroundRingEmbeddedMm = 900.0;

        /// <summary>底部回钩的**内**半径（mm）：大样图 37.5；回钩净宽即 2×37.5 = 75。</summary>
        internal const double GroundRingHookInnerRadiusMm = 37.5;

        /// <summary>底部回钩的净宽（mm）：大样图 75，等于 2×内半径。</summary>
        internal const double GroundRingHookClearMm = 2.0 * GroundRingHookInnerRadiusMm;

        /// <summary>底部回钩中心线弯曲半径（mm）：内半径 + 半个钢筋直径 = 37.5 + 15 = 52.5。</summary>
        internal static double GroundRingHookRadiusMm
        {
            get { return GroundRingHookInnerRadiusMm + GroundRingBarMm / 2.0; }
        }

        /// <summary>底部回钩自最低点向上到端头的高度（mm）：大样图 90。</summary>
        internal const double GroundRingHookRiseMm = 90.0;

        /// <summary>吊环两腿中心距的一半（mm）：(100 + 30)/2 = 65。</summary>
        internal static double GroundRingHalfMm
        {
            get { return (GroundRingClearMm + GroundRingBarMm) / 2.0; }
        }

        /// <summary>吊环环顶中心线标高（mm）：100 − 15 = 85，绳眼就挂在这里。</summary>
        internal static double GroundRingCrownMm
        {
            get { return GroundRingExposedMm - GroundRingBarMm / 2.0; }
        }

        /// <summary>
        /// 吊环两条腿直段的下端标高（mm）：最低点 −900 再往上让出回钩中心线半径与半个钢筋直径，
        /// 即 −900 + 52.5 + 15 = −832.5，回钩的最低外缘正好落在 −900。
        /// </summary>
        internal static double GroundRingLegBottomMm
        {
            get
            {
                return -(GroundRingEmbeddedMm - GroundRingHookRadiusMm - GroundRingBarMm / 2.0);
            }
        }

        /// <summary>回钩回程肢的中心线横向位置（mm）：65 + 2×52.5 = 170。</summary>
        internal static double GroundRingHookReturnMm
        {
            get { return GroundRingHalfMm + 2.0 * GroundRingHookRadiusMm; }
        }

        /// <summary>回钩端头标高（mm）：最低点 −900 上翘 90 = −810。</summary>
        internal static double GroundRingHookTipMm
        {
            get { return -GroundRingEmbeddedMm + GroundRingHookRiseMm; }
        }

        /// <summary>
        /// 地面绳眼吊点：绳眼局部原点（环顶中心线上方）沿拉索向上游
        /// 鸡心环内顶点 9.516 + φ30 吊环半径 15 = 24.516 mm、沿绳眼平面内法向偏出 8 mm
        /// （与上端同一个推导，只是下端绳眼朝上、吊环直径由 φ20 改 φ30 后多让 5 mm）。
        /// </summary>
        internal static double GroundEyeOffsetMm
        {
            get { return RopeEyeOffsetMm + GroundRingBarMm / 2.0; }
        }

        // ---------------------------------------------------------------
        // 地面锚墩与颜色无关的固定尺寸
        // ---------------------------------------------------------------

        /// <summary>
        /// 地面锚墩半径（mm）：取 90 覆盖 φ30 吊环的环体（净距 100、外侧到 ±80），
        /// 两层吊索时两块 φ180 锚墩相距 300 也不会相碰（净距 120）。
        /// </summary>
        internal const double AnchorRadiusMm = 90.0;

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
                WallThicknessMm = parameters.WallThicknessMm,
                NeedsExtraCable = NeedsExtraCable(height, radius),
                GenerateCables = parameters.GenerateCables,
                GenerateBase = parameters.GenerateBase,
                ShellBottomMm = parameters.GenerateBase ? ChimneyBaseConstants.BasePlateThickness : 0.0
            };

            spec.ExtraCableRatio = radius > 0.0 ? height / (2.0 * radius) : 0.0;

            // 拉索与地面吊环：关掉时整组不生成（排气筒自立）。
            int layers = spec.NeedsExtraCable ? 2 : 1;
            spec.CableCount = parameters.GenerateCables ? CableAzimuthDegrees.Length * layers : 0;
            spec.AnchorCount = spec.CableCount;

            // 基础：只有生成时才带出地脚螺栓与基础尺寸，供摘要与材料用量使用。
            if (parameters.GenerateBase)
            {
                ChimneyBaseParameters baseParameters = ToBaseParameters(parameters);
                double d1, d2, d3;
                ChimneyBaseCatalog.ResolveDiameters(baseParameters, out d1, out d2, out d3);
                spec.BoltCount = parameters.BoltCount;
                spec.FoundationThicknessMm = parameters.FoundationThicknessMm;
                spec.FoundationSideMm = ChimneyBaseCatalog.FoundationSide(baseParameters, d3);
                spec.EmbeddedPlateDiameterMm = d3;
                spec.BoltCircleDiameterMm = d2;
            }

            return spec;
        }

        /// <summary>
        /// 把烟囱拉索参数映射成底座参数（复用底座模块的业务逻辑）：
        /// 风管直径取筒身直径，D2/D3 与基础尺寸原样透传（0 仍表示自动）。
        /// </summary>
        internal static ChimneyBaseParameters ToBaseParameters(ChimneyCableParameters parameters)
        {
            return new ChimneyBaseParameters
            {
                ExhaustDiameterMm = parameters.DiameterMm,
                BoltCircleDiameterMm = parameters.BoltCircleDiameterMm,
                EmbeddedPlateDiameterMm = parameters.EmbeddedPlateDiameterMm,
                BoltCount = parameters.BoltCount,
                AbovePlateMm = parameters.AbovePlateMm,
                FoundationThicknessMm = parameters.FoundationThicknessMm,
                FoundationWidthMm = 0.0,
                HeadingDegrees = 0.0
            };
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

            if (!Finite(parameters.WallThicknessMm) ||
                parameters.WallThicknessMm < ChimneyCableConstants.MinWallThicknessMm ||
                parameters.WallThicknessMm > ChimneyCableConstants.MaxWallThicknessMm)
            {
                error = "筒身壁厚 t 需在 " + ChimneyCableConstants.MinWallThicknessMm + "～" +
                    ChimneyCableConstants.MaxWallThicknessMm + " mm 之间。";
                return false;
            }

            // 拉索角度只在不自立（生成拉索）时才参与建模与校核。
            if (parameters.GenerateCables &&
                (!Finite(parameters.CableAngleDegrees) ||
                 parameters.CableAngleDegrees < ChimneyCableConstants.MinAngleDegrees ||
                 parameters.CableAngleDegrees > ChimneyCableConstants.MaxAngleDegrees))
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
            double innerRadius = radius - parameters.WallThicknessMm;
            if (innerRadius <= 0.0)
            {
                error = "筒身直径过小：壁厚 " + Format(parameters.WallThicknessMm) + " mm 后内腔不足，壁厚须小于筒身半径 " +
                    Format(radius) + " mm。";
                return false;
            }

            // 生成基础时，底盘（预埋板/加劲肋/地脚螺栓/检修门）直接复用底座模块的校核：
            // 直径下限 100、螺栓个数、露出长度、基础厚度等都由它负责。
            if (parameters.GenerateBase)
            {
                string baseError;
                if (!ChimneyBaseCatalog.Validate(ToBaseParameters(parameters), out baseError))
                {
                    error = "底座：" + baseError;
                    return false;
                }
            }

            if (!parameters.GenerateCables)
            {
                return true;
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
