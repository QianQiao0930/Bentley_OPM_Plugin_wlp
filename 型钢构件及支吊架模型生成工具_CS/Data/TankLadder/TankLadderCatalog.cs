namespace SteelSectionProbe
{
    /// <summary>原水箱爬梯的构件尺寸；数量上限为建模保护，不作为设计标准。</summary>
    internal static class TankLadderCatalog
    {
        internal const string CellName = "TANK_LADDER";
        internal const string AngleProfile = "L50x50x5";
        internal const double FrameWidthMm = 50, FrameHeightMm = 600;
        internal const double LegWidthMm = 60, LegThicknessMm = 10, TopLengthMm = 340;
        internal const double BendRadiusMm = 150, LegDropMm = 50, LegExtraHeightMm = 480;
        internal const double ReinforcementWidthMm = 60, ReinforcementThicknessMm = 10;
        internal const double ReinforcementLengthMm = 250, ReinforcementOffsetMm = 10;
        internal const double ReinforcementBottomMm = 100;
        internal const double RungDiameterMm = 18, RungBottomMm = 300, RungSpacingMm = 300;
        internal const int MaxComponents = 500;
    }
}
