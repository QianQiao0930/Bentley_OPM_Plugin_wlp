using System;

namespace SteelSectionProbe
{
    /// <summary>Separates native generic Topwork control points without transforming the CEL body.</summary>
    internal sealed class ActuatorControlLayout
    {
        internal double HeightMm { get; private set; }
        internal double RadiusMm { get; private set; }
        internal double DiameterMm { get { return 2 * RadiusMm; } }

        internal static ActuatorControlLayout FromBounds(double lowX, double lowY, double lowZ,
            double highX, double highY, double highZ, double mmPerUnit)
        {
            foreach (double number in new[] { lowX, lowY, lowZ, highX, highY, highZ, mmPerUnit })
                if (double.IsNaN(number) || double.IsInfinity(number)) throw new InvalidOperationException("CEL 范围或单位换算无效。");
            if (mmPerUnit <= 0 || lowX > highX || lowY > highY || lowZ > highZ)
                throw new InvalidOperationException("CEL 范围或单位换算无效。");
            double radial = Math.Max(Math.Max(Math.Abs(lowX), Math.Abs(highX)), Math.Max(Math.Abs(lowY), Math.Abs(highY))) * mmPerUnit;
            double axial = Math.Max(Math.Abs(lowZ), Math.Abs(highZ)) * mmPerUnit;
            if (Math.Max(radial, axial) < 0.000001) throw new InvalidOperationException("CEL 图形范围为空，无法设置执行机构调节柄。");
            // Long narrow or flat cells also need three distinct control points.
            // Distances position controls only; they are not manufacturer sizing parameters.
            double height = Math.Max(axial, radial * 0.5);
            double radius = Math.Max(radial, height * 0.5);
            if (double.IsInfinity(height) || double.IsInfinity(radius) || double.IsInfinity(radius * 2))
                throw new InvalidOperationException("CEL 图形范围过大。");
            return new ActuatorControlLayout { HeightMm = height, RadiusMm = radius };
        }
    }
}
