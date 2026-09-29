namespace SteelSectionProbe
{
    internal sealed class TFrameParameters
    {
        internal string Kind="D12";
        internal char Variant='A';
        internal int Type=1;
        internal double SpanMm=250;
        internal double HeadingDegrees;
        internal char WeldJoint='A';
        internal string Stiffener="";
        internal bool KeepAuxiliaryLine=true;
    }
    internal sealed class TFrameVariant
    {
        internal string FamilyA,ProfileA,FamilyB,ProfileB,SpecA,SpecB;
        internal double WidthA,DepthA,FlangeA,WidthB,WebB,FitU,FitW;
        internal PortalGroundSpec Ground;
    }
    internal sealed class TFramePlan
    {
        internal TFrameParameters Parameters;
        internal TFrameVariant Variant;
        internal string Number,SupportType,SupportCode,CellName,AssemblySpecification;
        internal double HeightMm,L1Mm,L2Mm,PostLengthMm,GroundLiftMm,PostVOffsetMm;
        internal double ArmStartVMm,ArmStartWMm;
        internal double? AllowableLoadKn;
    }
    internal sealed class TFrameLimits
    {
        internal bool Horizontal;
        internal double MaxHeightMm,MaxSpanMm,WebThicknessMm;
        internal double MaxLineMm { get { return Horizontal?MaxHeightMm+WebThicknessMm:MaxHeightMm; } }
    }
}
