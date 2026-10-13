namespace SteelSectionProbe
{
    internal sealed class TankLadderParameters
    {
        internal double TankHeightMm = 2000;
        internal double WidthMm = 420;
        internal double ReinforcementSpacingMm = 900;
        internal double HeadingDegrees;
        internal bool MergeComponents = true;
    }

    internal sealed class TankLadderPoint
    {
        internal readonly double X, Y, Z;
        internal TankLadderPoint(double x, double y, double z) { X = x; Y = y; Z = z; }
    }

    internal sealed class TankLadderLeg
    {
        internal TankLadderPoint Start, ShortEnd, ArcMiddle, VerticalStart, Bottom;
    }

    internal sealed class TankLadderPlan
    {
        internal TankLadderParameters Parameters;
        internal TankLadderPoint BottomAngleOrigin;
        internal TankLadderPoint[] PostOrigins, ReinforcementOrigins, RungCenters;
        internal TankLadderLeg[] Legs;
        internal double BottomAngleLengthMm, LegVerticalHeightMm, RungLengthMm, LegClearWidthMm;
        internal int ComponentCount;
    }
}
