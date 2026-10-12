namespace SteelSectionProbe
{
    internal sealed class Q2SupportPlan
    {
        internal int Type,BigDn,SmallDn;
        internal bool Mirrored,Guide,BigVertical;
        internal string Subitem,ProfileName,Section,Number,Specification,PipeNumber;
        internal double LMm,LoadKn,SizeMm,ThicknessMm,StartMm,LengthMm,CornerYmm,TopZmm;
        internal double SmallYmm,SmallZmm,AngleDeg;
        internal A1ClampPlan BigClamp,SmallClamp;
        internal double[] SmallStationsMm,SmallBlockMm;
        internal double SmallBlockHeightMm {get{return SmallBlockMm==null?0:SmallBlockMm[0];}}
        internal double SmallBlockProjectionMm {get{return SmallBlockMm==null?0:SmallBlockMm[1];}}
    }
}
