using System;

namespace SteelSectionProbe
{
    /// <summary>轴向定位的纯计算，所有坐标与偏移使用相同单位。</summary>
    internal static class AxisPlacementCalculator
    {
        internal static double[] Unit(double[] start, double[] end)
        {
            Validate(start);
            Validate(end);
            double dx = end[0] - start[0], dy = end[1] - start[1], dz = end[2] - start[2];
            double length = Math.Sqrt(dx * dx + dy * dy + dz * dz);
            if (length <= 1e-9 || !Finite(length))
            {
                throw new InvalidOperationException("定位轴线长度无效。");
            }
            double sign = dz < 0 ? -1 : 1;
            return new[] { sign * dx / length, sign * dy / length, sign * dz / length };
        }

        internal static double Offset(double[] origin, double[] point, double[] start, double[] end)
        {
            Validate(origin);
            Validate(point);
            var u = Unit(start, end);
            return (point[0] - origin[0]) * u[0] + (point[1] - origin[1]) * u[1] + (point[2] - origin[2]) * u[2];
        }

        /// <summary>正值朝上；水平轴正值沿辅助线起点至终点。保留原定位点的横向偏差。</summary>
        internal static double[] Shift(double[] origin, double[] start, double[] end, double offset, bool rejectOutside)
        {
            Validate(origin);
            if (!Finite(offset))
                throw new InvalidOperationException("沿轴偏移必须为有限数字。");
            var u = Unit(start, end);
            double a = Offset(origin, start, start, end), b = Offset(origin, end, start, end);
            double min = Math.Min(a, b), max = Math.Max(a, b);
            if (rejectOutside && (offset < min - 1e-6 || offset > max + 1e-6))
            {
                throw new InvalidOperationException("沿轴偏移超出所选线段范围：" + min.ToString("0.###") + "～" + max.ToString("0.###") + " mm。");
            }
            offset = Math.Max(min, Math.Min(max, offset));
            return new[] { origin[0] + offset * u[0], origin[1] + offset * u[1], origin[2] + offset * u[2] };
        }

        private static bool Finite(double v)
        {
            return !double.IsNaN(v) && !double.IsInfinity(v);
        }
        private static void Validate(double[] p)
        {
            if (p == null || p.Length != 3 || !Finite(p[0]) || !Finite(p[1]) || !Finite(p[2]))
                throw new InvalidOperationException("定位坐标无效。");
        }
    }
}
