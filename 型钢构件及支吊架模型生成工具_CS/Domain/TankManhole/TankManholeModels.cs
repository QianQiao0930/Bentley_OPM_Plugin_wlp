namespace SteelSectionProbe
{
    internal enum TankCoverMode { Davit, Hinge }
    internal sealed class TankManholeParameters
    {
        internal int NominalDn=600;
        internal int PressureLbs=150;
        internal TankCoverMode CoverMode=TankCoverMode.Davit;
        internal double HeadingDegrees;
        internal double NeckLengthMm=150;
        internal bool Mirrored;
        internal bool IncludeBolts=true;
        internal bool IncludeLifting=true;
    }
    internal sealed class TankManholeSize
    {
        internal int NominalDn,NominalInches,BoltCount;
        internal double BoreMm,NeckOutsideMm,FlangeOutsideMm,FlangeThicknessMm;
        internal double BoltCircleMm,BoltDiameterMm,CoverThicknessMm,DavitDiameterMm;
    }
    internal sealed class TankManholePlan
    {
        internal TankManholeParameters Parameters;
        internal TankManholeSize Size;
        internal double HeadingRadians;
        internal double FlangeBackMm,FlangeFrontMm,CoverBackMm,CoverFrontMm;
        internal double FlangeRadiusMm,BoltCircleRadiusMm,BoltHoleRadiusMm;
        internal double DavitPivotXmm,DavitXmm,PostYmm,ArmZmm,PostTopZmm,StudZmm;
        internal double FlatThicknessMm,LoftLengthMm;
    }
}
