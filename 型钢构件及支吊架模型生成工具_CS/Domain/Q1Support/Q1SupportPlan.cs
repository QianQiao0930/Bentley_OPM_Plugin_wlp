namespace SteelSectionProbe
{
    /// <summary>Q1 毫米局部布局：X 大管轴，Y 径向高度，Z 大管卡开口。H 为图示中心标高差。</summary>
    internal sealed class Q1SupportPlan
    {
        internal int Type,SmallDn,BigDn;
        internal double HeightMm,LowMm,LengthMm,SizeMm,ThicknessMm,LoadKn;
        internal double SmallXmm,SmallYmm,SmallZmm,CornerXmm,CornerZmm,PadThicknessMm,PadSizeMm;
        internal bool Parallel,Mirrored;
        internal string Subitem,ProfileName,Section,Number,Specification,PipeNumber;
        internal A1ClampPlan BigClamp,SmallClamp;
    }
}
