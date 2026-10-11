using System;
namespace SteelSectionProbe
{
    internal static class N2CantileverCatalog
    {
        internal const string SupportType="N2-[设备上生根的双悬臂架]";
        internal const string CellName="N2_DOUBLE_CANTILEVER";
        internal const string AssemblyItemName="PipeSupportAssembly_N2_DOUBLE_CANTILEVER";
        internal static string ComponentItemName(string role){return "PipeSupportComponent_N2_DOUBLE_CANTILEVER_"+role;}
        private static readonly N2CantileverVariant[] Items={
            V('A',"equal_angle","L75x75x7","∠75×7",1,310,new[]{7.2,3.6,1.8}),
            V('B',"equal_angle","L100x100x10","∠100×10",1,310,new[]{10.0,4.8,2}),
            V('C',"parallel_channel","12.6","[12.6",1,310,new[]{24.0,12,4.8}),
            V('D',"parallel_channel","16a","[16a",2,390,new[]{40.0,20,10})};
        private static N2CantileverVariant V(char key,string family,string profile,string section,int plate,double min,double[] loads)
        {return new N2CantileverVariant{Key=key,Family=family,ProfileA=profile,ProfileB=profile,
            SectionA=section,SectionB=section,PlateType=plate,MinimumL2Mm=min,LoadsKn=loads};}
        internal static N2CantileverVariant Require(char key)
        {foreach(var v in Items)if(v.Key==key)return v;throw new InvalidOperationException("N2 子项应为 A～D。");}
        internal static double AllowableLoad(N2CantileverVariant v,double arm)
        {
            if(double.IsNaN(arm)||double.IsInfinity(arm)||arm<=0||arm>750)
                throw new InvalidOperationException("设备外壁至载荷位置 a 必须大于 0 且不超过 750 mm；图纸空白范围不外推。");
            return v.LoadsKn[arm<=250?0:arm<=500?1:2];
        }
        internal static ModeData Mode(N2CantileverVariant v,bool memberB)
        {return ProfileLookup.Mode(RuntimeData.Families,v.Family,memberB?v.ProfileB:v.ProfileA,
            v.Family=="equal_angle"?"outer_corner":"lower_left");}
    }
}
