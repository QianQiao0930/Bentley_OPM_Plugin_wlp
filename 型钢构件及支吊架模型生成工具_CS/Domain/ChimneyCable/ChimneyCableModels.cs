using System;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱（排气筒）拉索三维建模参数：迁移自 AutoCAD 版 <c>HzlsOptions</c> 的建模部分。
    /// 高度按米输入，直径与全部建模尺寸按 mm；局部原点取筒身底部圆心，Z 向上。
    /// 只做三维建模，不生成俯视图（Plan）与正视图（Front）二维图形。
    /// </summary>
    internal sealed class ChimneyCableParameters
    {
        /// <summary>排气筒高度 H（m）。</summary>
        internal double HeightMeters = ChimneyCableConstants.DefaultHeightMeters;

        /// <summary>筒身外直径 D（mm）。</summary>
        internal double DiameterMm = ChimneyCableConstants.DefaultDiameterMm;

        /// <summary>拉索与竖直方向的夹角（°），决定拉索外圆半径。</summary>
        internal double CableAngleDegrees = ChimneyCableConstants.DefaultCableAngleDegrees;

        /// <summary>放置后绕竖轴（Z）的旋转角（°）。</summary>
        internal double HeadingDegrees;

        /// <summary>排气筒高度（mm）。</summary>
        internal double HeightMm
        {
            get { return HeightMeters * 1000.0; }
        }

        /// <summary>筒身半径 R（mm）。</summary>
        internal double RadiusMm
        {
            get { return DiameterMm / 2.0; }
        }
    }

    /// <summary>
    /// 烟囱拉索的输入范围与默认值，逐项对齐 AutoCAD 版 <c>HzlsOptions</c>
    /// （高度 1～300 m、直径 10～20000 mm、拉索角度 1～89°）。纯常量，不依赖 Bentley。
    /// </summary>
    internal static class ChimneyCableConstants
    {
        /// <summary>排气筒高度下限（m）。</summary>
        internal const double MinHeightMeters = 1.0;

        /// <summary>排气筒高度上限（m）。</summary>
        internal const double MaxHeightMeters = 300.0;

        /// <summary>筒身直径下限（mm）。</summary>
        internal const double MinDiameterMm = 10.0;

        /// <summary>筒身直径上限（mm）。</summary>
        internal const double MaxDiameterMm = 20000.0;

        /// <summary>拉索角度下限（°）。</summary>
        internal const double MinAngleDegrees = 1.0;

        /// <summary>拉索角度上限（°）。</summary>
        internal const double MaxAngleDegrees = 89.0;

        /// <summary>排气筒高度默认值（m）。</summary>
        internal const double DefaultHeightMeters = 30.0;

        /// <summary>筒身直径默认值（mm）。</summary>
        internal const double DefaultDiameterMm = 1000.0;

        /// <summary>拉索角度默认值（°）。</summary>
        internal const double DefaultCableAngleDegrees = 30.0;
    }

    /// <summary>
    /// 由 <see cref="ChimneyCableParameters"/> 解出的几何量（mm），
    /// 供计算器、页面只读摘要与中文摘要共用；全部为派生值，不参与输入。
    /// </summary>
    internal sealed class ChimneyCableSpec
    {
        /// <summary>排气筒高度（mm）。</summary>
        internal double HeightMm;

        /// <summary>筒身外直径（mm）。</summary>
        internal double DiameterMm;

        /// <summary>筒身半径 R（mm）。</summary>
        internal double RadiusMm;

        /// <summary>拉索与竖直方向的夹角（°）。</summary>
        internal double CableAngleDegrees;

        /// <summary>拉索外圆半径 = R + (2H/3)·tanθ（mm）。</summary>
        internal double OuterRadiusMm;

        /// <summary>筒身壁厚 = min(max(5, R×0.04), R×0.5)（mm）。</summary>
        internal double WallThicknessMm;

        /// <summary>H/(2R)，即正视图补画中间层拉索的判据比值。</summary>
        internal double ExtraCableRatio;

        /// <summary>是否需要 H/3 高度的中间层拉索。</summary>
        internal bool NeedsExtraCable;

        /// <summary>拉索根数：3 根，或需要中间层时 6 根。</summary>
        internal int CableCount;

        /// <summary>
        /// 地面锚墩个数：每个固定点一个。单层时三向各一个（3），两层时上下层各一个（6）。
        /// </summary>
        internal int AnchorCount;
    }
}
