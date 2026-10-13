namespace SteelSectionProbe
{
    internal sealed class BracketParameters
    {
        internal bool Double;
        internal char Subtype='A';
        internal int Type=1;
        internal double HeightMm;
        internal bool Reverse;
        internal bool KeepAuxiliaryLine=true;
        internal double L2Mm,L3Mm,L4Mm,EquipmentOdMm,PreweldMm;
        internal bool ShowPreweld;
    }
    internal sealed class BracketPlan
    {
        internal bool Double,Reverse,KeepAuxiliaryLine,ShowPreweld;
        internal char Subtype;
        internal int Type,PlateType;
        internal string SectionA,SectionB,SectionC,Number,Specification;
        internal double L,L1,L2,L3,L4,H,EquipmentOd,Preweld,PlateThickness,
            BeamLength,BraceRun,EndOverhang,SectionAHeight,SectionAWidth,
            SectionAWeb,SectionCWidth,ConnectorSpan,VerticalLoad,HorizontalLoad;
        /// <summary>从定向辅助线起点到支架建模原点的距离，毫米。</summary>
        internal double RootOffsetMm;
        /// <summary>相对横担顶面的横担板中心、斜撑板中心及斜撑接触面标高，毫米。</summary>
        internal double BeamCenterZMm,BracePlateCenterZMm,BraceContactZMm;
    }
}
