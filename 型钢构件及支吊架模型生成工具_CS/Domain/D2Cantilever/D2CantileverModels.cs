namespace SteelSectionProbe
{
    /// <summary>D2/D3 悬臂参数，尺寸单位为毫米。</summary>
    internal sealed class D2CantileverParameters
    {
        internal string Kind = "D2";
        internal int Type = 1;
        internal char Subtype = 'A';
        internal string Name = "D2";
        internal double LoadDistanceMm = 250;
        internal bool Reverse = false;
        internal bool KeepAuxiliaryLine = true;
        internal bool AddPlate;
        internal string PlateSubtype = "A";
        internal double PlateOffsetMm;
    }

    internal sealed class D2CantileverVariant
    {
        internal char Key;
        internal string Family, ProfilePrefix, Section;
        internal double?[] Loads;
    }

    internal sealed class D2CantileverPlan
    {
        internal D2CantileverParameters Parameters;
        internal D2CantileverVariant Variant;
        internal G2AnchorPlan Plate;
        internal G11CantileverPlan ConcreteAnchor;
        internal string Number, Specification;
        internal double LengthMm, BeamStartMm, BeamLengthMm;
        internal double SectionHeightMm, SectionWidthMm;
        internal double SectionAnchorYmm, SectionAnchorZmm, RootStationMm;
        internal double? VerticalLoadKn, HorizontalLoadKn;
    }
}
