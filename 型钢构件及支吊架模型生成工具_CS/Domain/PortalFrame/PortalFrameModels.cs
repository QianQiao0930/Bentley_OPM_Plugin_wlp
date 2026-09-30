namespace SteelSectionProbe
{
    internal sealed class PortalFrameParameters
    {
        internal string Kind="D8";
        internal char Variant='A';
        internal int Type=1;
        internal double SpanMm=500;
        internal double L3Mm=200,L4Mm=200;
        internal bool AddPlate;
        internal string PlateSubtype="A";
        internal double PlateOffsetMm;
        internal char Weld='A';
        internal string Name="D8";
        internal double HeadingDegrees;
        internal bool KeepAuxiliaryLine=true;
    }
    internal sealed class PortalFrameVariant
    {
        internal string PostFamily,PostProfile,ArmFamily,ArmProfile;
        internal string PostSpecification,ArmSpecification;
        internal double PostWidth,ArmDepth,ArmFlange,ArmWidth,PostWeb,ChannelGap;
        internal PortalGroundSpec Ground;
    }
    internal sealed class PortalGroundSpec
    {
        internal double PlateSide,HoleSpacing,HoleDiameter,PlateThickness;
        internal double BoltDiameter,BoltLength,Embedment,MinPavement;
    }
    internal sealed class PortalFramePlan
    {
        internal PortalFrameParameters Parameters;
        internal PortalFrameVariant Variant;
        internal string SupportType,SupportCode,Number,CellName,AssemblySpecification;
        internal double HeightMm,FrameHeightMm,SpanMm,ArmLengthMm,PostLengthMm;
        internal double PostPitchMm,PostVOffsetMm,GroundLiftMm;
        internal double? AllowableLoadKn;
        internal int ArmQuantity;
        internal double L1Mm,L3Mm,L4Mm;
        internal double[] MemberBStationsMm;
        internal G2AnchorPlan Plate;
        internal double MemberAStartMm;
    }
}
