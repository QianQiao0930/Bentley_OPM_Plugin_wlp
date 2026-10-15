using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class A1NativeTrialCalculator
    {
        internal static A1NativeTrialPosition Calculate(double[] start, double[] end, double? station, double angle)
        {
            if (start == null || end == null || start.Length != 3 || end.Length != 3)
                throw new InvalidOperationException("管轴端点不完整。");
            foreach (double value in start) RequireFinite(value);
            foreach (double value in end) RequireFinite(value);
            RequireFinite(angle);
            double dx = end[0] - start[0], dy = end[1] - start[1], dz = end[2] - start[2];
            double length = Math.Sqrt(dx * dx + dy * dy);
            RequireFinite(length);
            if (length < 1 || Math.Abs(dz) > .01)
                throw new InvalidOperationException("本次试验仅支持水平直管（两端高差不超过0.01 mm）。");
            double offset = station ?? length / 2;
            RequireFinite(offset);
            if (offset < 0 || offset > length)
                throw new InvalidOperationException("距起点距离须在0～管长之间，单位mm。");
            return new A1NativeTrialPosition { X = start[0] + dx / length * offset,
                Y = start[1] + dy / length * offset, Z = start[2], Ux = dx / length, Uy = dy / length,
                StationMm = offset, LengthMm = length, AngleDeg = ((angle % 360) + 360) % 360 };
        }

        internal static double Parse(string text)
        {
            double value;
            if (!double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
                throw new InvalidOperationException("参数须为数字，距离用mm、角度用度，小数点用英文句点。");
            RequireFinite(value); return value;
        }

        internal static void RequireFinite(double value)
        { if (double.IsNaN(value) || double.IsInfinity(value)) throw new InvalidOperationException("参数或坐标不是有限数值。"); }
    }
}
