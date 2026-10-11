using System;
namespace SteelSectionProbe
{
    internal static class N1CantileverCatalog
    {
        internal const string SupportType="N1-[设备上生根的单悬臂架]";
        internal const string SupportCode="N1_CANTILEVER";
        internal const string CellName="N1_CANTILEVER";
        internal const string AssemblyItemName="PipeSupportAssembly_N1_CANTILEVER";
        internal static string ComponentItemName(string role)
        {return "PipeSupportComponent_N1_CANTILEVER_"+role;}
        private static readonly N1CantileverVariant[] Items={
            V('A',"equal_angle","L50x50x6","L50x50x6","∠50×6","∠50×6",0,new[]{1.4,0.5,0}),
            V('B',"equal_angle","L75x75x7","L75x75x7","∠75×7","∠75×7",1,new[]{3.6,1.8,0.9}),
            V('C',"equal_angle","L100x100x10","L100x100x10","∠100×10","∠100×10",1,new[]{5.0,2.4,2}),
            V('D',"parallel_channel","12.6","16a","[12.6","[16a",1,new[]{12.0,6,2.4}),
            V('E',"parallel_channel","16a","20a","[16a","[20a",2,new[]{20.0,10,5})};
        private static N1CantileverVariant V(char key,string family,string a,string b,string sa,string sb,int plate,double[] loads)
        {return new N1CantileverVariant{Key=key,Family=family,ProfileA=a,ProfileB=b,
            SectionA=sa,SectionB=sb,PlateType=plate,LoadsKn=loads};}
        internal static N1CantileverVariant Require(char key)
        {foreach(var v in Items)if(v.Key==key)return v;throw new InvalidOperationException("N1 子项应为 A～E。");}
        internal static double AllowableLoad(N1CantileverVariant v,double arm)
        {
            if(double.IsNaN(arm)||double.IsInfinity(arm)||arm<=0||arm>750)
                throw new InvalidOperationException("设备外壁至立管中心距离 a 必须在 0～750 mm 内。");
            int column=arm<=250?0:arm<=500?1:2;
            double load=v.LoadsKn[column];
            if(load<=0)throw new InvalidOperationException("该子项在当前 a 范围内没有允许荷载，请选择其他子项。");
            return load;
        }
        internal static double BTopOffset(N1CantileverVariant v)
        {
            if(v.Family=="equal_angle")return BFlangeThickness(v);
            var a=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileA);
            var b=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileB);
            if(a==null||b==null)throw new InvalidOperationException("型钢目录缺少槽钢 A/B。");
            return (b.Dimensions["H"]-a.Dimensions["H"])/2;
        }
        internal static double AEndSetback(N1CantileverVariant v)
        {
            if(v.Family=="equal_angle")return 10;
            var b=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileB);
            if(b==null)throw new InvalidOperationException("型钢目录缺少槽钢 B。");
            return b.Dimensions["tw"];
        }
        internal static double BFlangeThickness(N1CantileverVariant v)
        {
            var profile=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileB);
            if(profile==null)throw new InvalidOperationException("型钢目录缺少构件 B。");
            return profile.Dimensions[v.Family=="equal_angle"?"t":"tf"];
        }
        internal static ModeData Mode(N1CantileverVariant v,bool memberB)
        {return ProfileLookup.Mode(RuntimeData.Families,v.Family,memberB?v.ProfileB:v.ProfileA,
            v.Family=="equal_angle"?"outer_corner":"lower_left");}
    }
}
