using System;

namespace PipeAlign
{
    /// <summary>
    /// 标高计算（开发指南 §9、§16）。
    /// <para>
    /// 这是**唯一**的标高算法入口：业务层不得在别处再写一份"中心线 ± 外径/2"。
    /// 纯计算，不引用任何 Bentley 类型。
    /// </para>
    /// </summary>
    internal static class ElevationCalculator
    {
        /// <summary>
        /// 取一根管道在指定模式下的对齐标高（mm）。开发指南 §16 的
        /// <c>GetAlignmentElevation</c>。
        /// <para>
        /// Zc 取中心线标高；Deff 为有效外径（裸管 Do / 保温外表面 Do + 2×Tins）。
        /// </para>
        /// </summary>
        /// <exception cref="ArgumentNullException">管道或中心线为空。</exception>
        internal static double GetAlignmentElevation(PipeInfo pipe, AlignmentMode mode,
            SurfaceMode surfaceMode)
        {
            if (pipe == null) throw new ArgumentNullException("pipe");
            if (pipe.Axis == null)
                throw new InvalidOperationException("该管道没有可用的中心线，无法计算标高。");

            double zc = pipe.Axis.CenterElevationMm;
            double diameter = pipe.EffectiveDiameterMm(surfaceMode);

            switch (mode)
            {
                case AlignmentMode.Bottom:
                    return zc - diameter / 2.0;
                case AlignmentMode.Top:
                    return zc + diameter / 2.0;
                default:
                    return zc;
            }
        }

        /// <summary>
        /// 计算位移 ΔZ = 基准标高 − 目标标高（开发指南 §9）。
        /// <para>只改 Z，不改 X / Y。</para>
        /// </summary>
        internal static double ComputeDeltaZ(double referenceElevationMm, double targetElevationMm)
        {
            return referenceElevationMm - targetElevationMm;
        }

        /// <summary>
        /// 由中心线标高与有效外径反算管底标高（指南 §34 的示例计算，报表与预览用）。
        /// </summary>
        internal static double BottomElevation(double centerElevationMm, double effectiveDiameterMm)
        {
            return centerElevationMm - effectiveDiameterMm / 2.0;
        }

        /// <summary>由中心线标高与有效外径反算管顶标高。</summary>
        internal static double TopElevation(double centerElevationMm, double effectiveDiameterMm)
        {
            return centerElevationMm + effectiveDiameterMm / 2.0;
        }
    }
}
