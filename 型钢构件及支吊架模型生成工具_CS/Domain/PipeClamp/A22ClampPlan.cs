namespace SteelSectionProbe
{
    internal sealed class A22ClampParameters
    {
        internal int FallbackDn=A22ClampCatalog.DefaultDn;
        internal double FallbackColdThicknessMm=A22ClampCatalog.DefaultColdThicknessMm;
        internal string Name="A22";
    }

    internal sealed class A22ClampPlan
    {
        internal int Dn;
        internal double PipeOutsideMm,ColdThicknessMm,BearingPlateThicknessMm;
        internal double A,B,C,E,F,T,W,G,OuterRadiusMm,FlangeEndMm,FlangeRootMm;
        internal double RMinMm,TransitionEndYmm,TransitionTangentYmm,TransitionTangentZmm;
        internal int BoltDiameterMm;
        internal double AllowableLoadKn;
        internal string Code;
        internal string Number,Specification;
        internal double[] BoltCentersYmm
        { get { return F>0?new[]{-B-F,-B,B,B+F}:new[]{-B,B}; } }
    }
}
