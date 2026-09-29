namespace SteelSectionProbe
{
    internal sealed class TriangleBracketParameters
    {
        internal string Kind="D5";
        internal char Variant='A';
        internal int Type=1;
        internal double L1Mm=600;
        internal string Name="D5";
        internal bool Reverse;
        internal bool KeepAuxiliaryLine=true;
        internal bool AddPlate;
        internal string PlateSubtype="A";
        internal double PlateOffsetMm;
    }

    internal sealed class TriangleBracketVariant
    {
        internal string SectionA,SectionB,BoltSubtype;
        internal double HeightA,WidthA,WebA,FlangeA,HeightB,WidthB,WebB,FlangeB;
        internal double BoltSpacing,BoltEdge,WebGap,ConnectorLength,ConnectorHeight,ConnectorThickness;
        internal double?[] Loads;
    }

    internal sealed class TriangleBracketPlan
    {
        internal TriangleBracketParameters Parameters;
        internal TriangleBracketVariant Variant;
        internal G2AnchorPlan Plate;
        internal string Number,SupportType,SupportCode,CellName,AssemblySpecification;
        internal double L1Mm,L2Mm,BeamStartMm,BeamLengthMm,BraceLengthMm,EndOverhangMm;
        internal double P1ZMm,P3ZMm,ToeOffsetMm,MinL1Mm,AllowableVerticalKn,AllowableHorizontalKn;
        internal bool HasLoad;
        internal int QuantityA,QuantityB;
    }
}
