namespace SteelSectionProbe
{
    internal static class HandrailCatalog
    {
        internal const string PageId="steel-handrail",CellName="STEEL_HANDRAIL",SupportType="普通钢结构围栏";
        internal const double TopZ=1017,KneeZ=560,TopOd=42.4,KneeOd=33.7,PostOd=48.3,Wall=3.2,BallDiameter=76;
        internal const double Radius=140,MaxSpacing=2000,Module=50,CornerPost=300,Tolerance=0.01;
        internal const double PathOffset=-34.2,KickOffset=37.15,KickHeight=130,KickThickness=6,KickBottom=10;
        internal const double PlateLength=146,PlateWidth=75,PlateThickness=10,BendRadius=76;
        internal const double FlatMajor=70,FlatMinor=16.1,Transition=38.5,ClosureReach=300;
        internal static readonly string[] ConnectionLabels={"类型 1 · 直柱压扁端侧装","类型 2 · 下弯侧装","类型 3 · 水平底板顶装","类型 4 · 预留（无底部节点）"};
        internal static readonly string[] ClosureLabels={"不闭合","仅始端","仅末端","两端闭合"};
    }
}
