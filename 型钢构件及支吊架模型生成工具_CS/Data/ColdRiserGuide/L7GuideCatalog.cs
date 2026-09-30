using System;

namespace SteelSectionProbe
{
    internal enum ColdRiserGuideSeries {L7,L8}
    internal enum L7GuideKind {Type1,Type2}
    internal static class L7GuideCatalog
    {
        internal static string SupportType(L7GuideKind kind)
        {return kind==L7GuideKind.Type2?"L7 类型2 保冷立管导向架":"L7 类型1 保冷立管导向架";}
        internal static string CellName(L7GuideKind kind)
        {return kind==L7GuideKind.Type2?"L7_COLD_RISER_GUIDE_TYPE2":"L7_COLD_RISER_GUIDE_TYPE1";}
        internal static string SupportType(L7GuidePlan p)
        {return p.Code+" 类型"+(p.Kind==L7GuideKind.Type2?"2":"1")+" 保冷立管导向架";}
        internal static string CellName(L7GuidePlan p)
        {return p.Code+"_COLD_RISER_GUIDE_TYPE"+(p.Kind==L7GuideKind.Type2?"2":"1");}
        internal static readonly int[] Dns={15,20,25,40,50,80,100,125,150};
        private static readonly double[] Loads={0.4,0.51,0.64,0.92,1.1,1.9,2.5,6.2,7.5};
        internal static double AllowableLoad(int dn)
        {
            int i=Array.IndexOf(Dns,dn);
            if(i<0)throw new InvalidOperationException("导向架仅支持 DN15、20、25、40、50、80、100、125、150。");
            return Loads[i];
        }
        internal static double? AxialTravel(double l)
        {return l==300?30:(l==450?100:(l==600?(double?)180:null));}
        internal static string Material(string code)
        {
            switch(code) {
                case "L":return "低温碳钢（-40～-21℃）；防滑挡环 Q345R";
                case "C1":return "碳钢（-20～120℃）；防滑挡环 Q235B";
                case "S":return "不锈钢（-196～120℃）；防滑挡环 06Cr19Ni10";
                default:throw new InvalidOperationException("材料代码应为 L、C1 或 S。");
            }
        }
        internal static int EquipmentMember(double d,out string family,out string profile,out string label)
        {
            if(d<=100){family="equal_angle";profile="L75x75x7";label="∠75×7";return 1;}
            if(d<=700){family="parallel_channel";profile=d<=450?"12.6":"14a";label="["+profile;return d<=450?1:2;}
            throw new InvalidOperationException("L8 管夹直径超过表 1 的 700 mm 上限。");
        }
        internal const double MinLengthMm=300,MaxLengthMm=1000;
        internal const double DefaultBearingLengthMm=300;

        internal static void Member(double clampDiameter,out string family,out string profile,
            out string label)
        {
            if(clampDiameter<=100) {family="equal_angle";profile="L75x75x7";label="∠75×7";}
            else if(clampDiameter<=450) {family="hot_rolled_h";profile="H100x100x6x8xr8";label="H100×100×6×8";}
            else if(clampDiameter<=700) {family="hot_rolled_h";profile="H125x125x6.5x9xr8";label="H125×125×6.5×9";}
            else throw new InvalidOperationException("L7 类型1 的管夹直径超过表 1 的 700 mm 上限。");
        }
    }
}
