namespace SteelSectionProbe
{
    internal sealed class MagneticGaugeParameters
    {
        internal double ConnectionSpacingMm=1400, HeadingDegrees;
    }
    /// <summary>毫米局部坐标，Z向上，接管-X，显示面-Y；原点为下接口标高的筒体轴心。</summary>
    internal struct MagneticGaugePoint
    {
        internal readonly double X,Y,Z;
        internal MagneticGaugePoint(double x,double y,double z){X=x;Y=y;Z=z;}
    }
    internal enum MagneticGaugeKind { Cylinder, Box, Torus }
    internal enum MagneticGaugeColor { Steel, Dark, Red, White }
    internal sealed class MagneticGaugePart
    {
        internal MagneticGaugeKind Kind;
        internal MagneticGaugePoint Start, End, Size;
        internal double RadiusMm, TubeRadiusMm;
        internal MagneticGaugeColor Color;
    }
    internal sealed class MagneticGaugePlan
    {
        internal MagneticGaugeParameters Parameters;
        internal MagneticGaugePart[] Parts;
        internal int FlipCount, TickCount;
        internal double FlipPitchMm;
        internal string CellName;
    }
}
