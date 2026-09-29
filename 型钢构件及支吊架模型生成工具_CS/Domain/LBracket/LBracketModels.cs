namespace SteelSectionProbe
{
    internal struct LBracketPoint
    {
        internal double X,Y,Z;
        internal LBracketPoint(double x,double y,double z){X=x;Y=y;Z=z;}
    }
    internal sealed class LBracketSelection
    {
        internal ulong ElementId;
        internal bool IsFromReference;
        internal LBracketPoint Corner,PostEnd,ArmEnd;
        internal double HeightMm,LengthMm,RunX,RunY;
    }
    internal sealed class LBracketParameters
    {
        internal char Variant='A';
        internal int Type=1;
        internal double WidthMm=250;
        internal string Name="D7";
        internal bool KeepAuxiliaryLine=true;
    }
    internal sealed class LBracketVariant
    {
        internal char Key;
        internal string Family,Profile,Specification;
        internal double HeightMm,ThicknessMm,CentroidMm;
        internal double MaxHeightMm,MaxWidthMm;
        internal double[] HeightColumns,WidthColumns;
        internal double?[][] Loads;
    }
    internal sealed class LBracketPlan
    {
        internal LBracketParameters Parameters;
        internal LBracketSelection Selection;
        internal LBracketVariant Variant;
        internal string Number,Specification;
        internal double PostCutLengthMm,ArmCutLengthMm;
        internal double? AllowableLoadKn,UsedHeightMm,UsedWidthMm;
    }
}
