namespace SteelSectionProbe
{
    internal static class MagneticGaugeCatalog
    {
        internal const double MinSpacingMm=350,MaxSpacingMm=6000,DefaultSpacingMm=1400;
        internal const double BodyRadiusMm=30,FlipReferencePitchMm=24,FlipGapMm=.8,TickSpacingMm=10;
        internal const string CellPrefix="MAGNETIC_LEVEL_GAUGE_L1_";
        internal static int[] Rgb(MagneticGaugeColor color)
        {
            switch(color)
            {
                case MagneticGaugeColor.Dark:return new[]{48,57,65};
                case MagneticGaugeColor.Red:return new[]{215,38,40};
                case MagneticGaugeColor.White:return new[]{245,245,239};
                default:return new[]{174,185,194};
            }
        }
    }
}
