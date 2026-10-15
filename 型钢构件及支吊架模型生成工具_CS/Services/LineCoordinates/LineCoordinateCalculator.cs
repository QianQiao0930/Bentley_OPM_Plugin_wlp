using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class LineCoordinateCalculator
    {
        internal static double Parse(string text, string label)
        {
            double value;
            if (!double.TryParse(text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
                throw new InvalidOperationException(label + "请输入有效数字。");
            if (!Finite(value)) throw new InvalidOperationException(label + "必须是有限数值。");
            return value;
        }

        internal static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }

        internal static double Length(LineCoordinates coordinates)
        {
            if (coordinates == null) throw new ArgumentNullException("coordinates");
            ValidatePoint(coordinates.Start); ValidatePoint(coordinates.End);
            double x = coordinates.End.X - coordinates.Start.X;
            double y = coordinates.End.Y - coordinates.Start.Y;
            double z = coordinates.End.Z - coordinates.Start.Z;
            double maximum = Math.Max(Math.Abs(x), Math.Max(Math.Abs(y), Math.Abs(z)));
            if (!Finite(maximum)) throw new InvalidOperationException("坐标超出可计算范围。");
            if (maximum == 0) return 0;
            double length = maximum * Math.Sqrt((x / maximum) * (x / maximum) +
                (y / maximum) * (y / maximum) + (z / maximum) * (z / maximum));
            if (!Finite(length)) throw new InvalidOperationException("线段长度超出可计算范围。");
            return length;
        }

        internal static void Validate(LineCoordinates coordinates, bool is3d, double minimumLengthMm)
        {
            if (!Finite(minimumLengthMm) || minimumLengthMm < 0) throw new ArgumentOutOfRangeException("minimumLengthMm");
            double length = Length(coordinates);
            if (length == 0 || length < minimumLengthMm)
                throw new InvalidOperationException("起点和终点不能重合，线段长度不能小于模型分辨率。");
            if (!is3d && (coordinates.Start.Z != 0 || coordinates.End.Z != 0))
                throw new InvalidOperationException("二维模型的 Z 坐标只能为 0。");
        }

        internal static bool Same(LineCoordinates a, LineCoordinates b, double toleranceMm)
        {
            return a != null && b != null && SamePoint(a.Start, b.Start, toleranceMm) && SamePoint(a.End, b.End, toleranceMm);
        }

        private static bool SamePoint(LineCoordinatePoint a, LineCoordinatePoint b, double tolerance)
        {
            return Math.Abs(a.X - b.X) <= tolerance && Math.Abs(a.Y - b.Y) <= tolerance && Math.Abs(a.Z - b.Z) <= tolerance;
        }

        private static void ValidatePoint(LineCoordinatePoint point)
        {
            if (!Finite(point.X) || !Finite(point.Y) || !Finite(point.Z))
                throw new InvalidOperationException("端点坐标必须是有限数值。");
        }

        // 保留往返精度，避免只修改一个字段时舍入其余五个坐标（往返/测试用）。
        internal static string Format(double value) { return value.ToString("G17", CultureInfo.CurrentCulture); }

        // 界面显示：毫米坐标只显示 2 位小数；未编辑字段在应用时仍沿用精确值（见页面）。
        internal static string Display(double value) { return value.ToString("0.##", CultureInfo.CurrentCulture); }
    }
}
