namespace SteelSectionProbe
{
    internal sealed class SquareManholeParameters
    {
        internal double BarrelWidthMm=600,BarrelDepthMm=600,BarrelHeightMm=100;
        internal double CoverWidthMm=620,CoverDepthMm=620,CoverHeightMm=40,WallMm=4;
        internal double RotationDegrees;
    }
    internal sealed class SquareManholePlan
    {
        internal SquareManholeParameters Parameters;
        internal double BarrelOutsideWidthMm,BarrelOutsideDepthMm,CoverBottomMm;
        internal double TotalHeightMm,ClearanceXmm,ClearanceYmm;
    }
}
