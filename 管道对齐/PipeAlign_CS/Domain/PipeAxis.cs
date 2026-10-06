using System;

namespace PipeAlign
{
    /// <summary>
    /// 管道中心线（业务单位：毫米）。
    /// <para>
    /// 这是开发指南 §9 要求的**主数据源**：程序先取中心线，再由中心线标高与外径
    /// 推算管底 / 管顶。程序**不得**用 <c>Element.GetRange()</c> 的包围盒当作工程标高
    /// （指南 §8.1、§36）—— 包围盒只允许用于 Debug、预览与几何合理性检查。
    /// </para>
    /// <para>本类型是纯数据，不引用任何 Bentley 类型，可在离线自检工程里构造与断言。</para>
    /// </summary>
    internal sealed class PipeAxis
    {
        internal PipeAxis(double startXmm, double startYmm, double startZmm,
            double endXmm, double endYmm, double endZmm)
        {
            StartXmm = startXmm;
            StartYmm = startYmm;
            StartZmm = startZmm;
            EndXmm = endXmm;
            EndYmm = endYmm;
            EndZmm = endZmm;
        }

        internal double StartXmm { get; private set; }
        internal double StartYmm { get; private set; }
        internal double StartZmm { get; private set; }
        internal double EndXmm { get; private set; }
        internal double EndYmm { get; private set; }
        internal double EndZmm { get; private set; }

        /// <summary>两端高差（mm）。水平管的判据就是它的绝对值。</summary>
        internal double DeltaZmm { get { return EndZmm - StartZmm; } }

        /// <summary>中心线标高 Zc（mm）。水平管的两个端点等高，这里取中点更稳健。</summary>
        internal double CenterElevationMm { get { return (StartZmm + EndZmm) / 2.0; } }

        /// <summary>水平投影长度（mm）。</summary>
        internal double HorizontalRunMm
        {
            get
            {
                double dx = EndXmm - StartXmm;
                double dy = EndYmm - StartYmm;
                return Math.Sqrt(dx * dx + dy * dy);
            }
        }

        /// <summary>三维长度（mm）。</summary>
        internal double LengthMm
        {
            get
            {
                double dx = EndXmm - StartXmm;
                double dy = EndYmm - StartYmm;
                return Math.Sqrt(dx * dx + dy * dy + DeltaZmm * DeltaZmm);
            }
        }

        /// <summary>坡度（%）；水平投影为 0（竖直管）时返回 <c>null</c>。</summary>
        internal double? SlopePercent
        {
            get
            {
                double run = HorizontalRunMm;
                if (run <= 0.0) return null;
                return DeltaZmm / run * 100.0;
            }
        }

        /// <summary>零长度管：没有可用的中心线方向，必须拒绝。</summary>
        internal bool IsDegenerate { get { return LengthMm <= ZeroLengthToleranceMm; } }

        /// <summary>
        /// 是否按水平管处理（开发指南 §11）：<c>abs(ΔZ) &lt;= HorizontalTolerance</c>。
        /// 容差由调用方从配置传入，**不在业务代码里写死**。
        /// </summary>
        internal bool IsHorizontal(double toleranceMm)
        {
            if (toleranceMm < 0.0) toleranceMm = 0.0;
            return Math.Abs(DeltaZmm) <= toleranceMm;
        }

        /// <summary>
        /// 整体沿 Z 平移 <paramref name="deltaZmm"/>。
        /// <para>指南 §9：程序**只修改 Z 坐标**，不得修改 X 和 Y。</para>
        /// </summary>
        internal PipeAxis ShiftedByZ(double deltaZmm)
        {
            return new PipeAxis(StartXmm, StartYmm, StartZmm + deltaZmm,
                EndXmm, EndYmm, EndZmm + deltaZmm);
        }

        /// <summary>零长度判据（mm）。管道不可能短于 0.001 mm，超过即为退化几何。</summary>
        internal const double ZeroLengthToleranceMm = 1.0e-3;

        public override string ToString()
        {
            return string.Format(System.Globalization.CultureInfo.InvariantCulture,
                "({0:F3},{1:F3},{2:F3})→({3:F3},{4:F3},{5:F3}) Zc={6:F3}",
                StartXmm, StartYmm, StartZmm, EndXmm, EndYmm, EndZmm, CenterElevationMm);
        }
    }
}
