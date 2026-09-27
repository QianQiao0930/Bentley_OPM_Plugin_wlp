namespace SteelSectionProbe
{
    internal sealed class E1GuideItem
    {
        internal string Key, FamilyId, ProfileName, ModeId, Specification;
        internal int MinDn, MaxDn;
        internal double FaceWidthMm, DepthMm, LinerWidthMm, LinerHeightMm, LinerThicknessMm, LoadKn;
    }
    internal sealed class E1GuidePlan
    {
        internal E1GuideItem Item;
        internal int Dn;
        internal double OutsideMm, HeightMm, FaceMm, CenterXmm, CenterYmm, CenterZmm;
        internal double PipeX, PipeY, AwayX, AwayY;
        internal bool Stainless;
        internal string Material, Number, PipeNumber;
        internal ulong SourceId;
        internal bool IsAuxiliaryLine;
    }
}
