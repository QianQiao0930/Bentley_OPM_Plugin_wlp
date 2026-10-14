namespace SteelSectionProbe
{
    internal static class WallLadderCatalog
    {
        internal const double RungDiameterMm=24, RungProtrusionMm=10, MinRungSpacingMm=250, MaxRungSpacingMm=300;
        internal const double TopRungClearanceMm=50, TopExtensionMm=1200, MaxHeightMm=6000;
        internal const double AngleLegMm=75, AngleThicknessMm=10, PlateWidthMm=100, PlateHeightMm=100, PlateThicknessMm=10;
        internal const string AngleProfile="L75x75x10", LadderCell="WALL_LADDER", CageCell="WALL_LADDER_CAGE";
        internal const double CageRadiusMm=355, TabInwardMm=60, HookInwardMm=105, StraightOffsetMm=410;
        internal const double CageFirstHeightMm=2000, CageMaxSpacingMm=1500, HoopWidthMm=50, HoopThicknessMm=5;
        internal const int CageBarCount=11, MaxParts=500;
        internal const double BarWidthMm=30, BarThicknessMm=5, TopHookNMm=-700, VerticalToleranceMm=5;
    }
}
