namespace SteelSectionProbe
{
    internal sealed class N1CantileverParameters
    {
        internal int Type=1;
        internal char Subtype='A';
        internal double EquipmentOdMm=2000,PreweldMm=200,L2Mm=300;
        internal bool Reverse=false,ShowPreweld=false;
    }
    internal sealed class N1CantileverVariant
    {
        internal char Key;
        internal int PlateType;
        internal string Family,ProfileA,ProfileB,SectionA,SectionB;
        internal double[] LoadsKn;
    }
    internal sealed class N1CantileverPlan
    {
        internal N1CantileverParameters Parameters;
        internal N1CantileverVariant Variant;
        internal string Number,Specification;
        internal bool HasLoad;
        internal double LMm,LoadArmMm,RootMm,L1Mm,L2Mm,ACutMm,VerticalLoadKn,BTopOffsetMm;
    }
    // Auxiliary line in active-model millimetres. X points from equipment to pipe,
    // Y is the transverse horizontal axis, Z is world up. Origin is equipment centre.
    internal sealed class N1CantileverFrame
    {
        internal double X,Y,Z,RunX,RunY,LengthMm;
        internal double[] Point(double x,double y,double z)
        {return new[]{X+x*RunX-y*RunY,Y+x*RunY+y*RunX,Z+z};}
    }
}
