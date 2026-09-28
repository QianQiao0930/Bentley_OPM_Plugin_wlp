using System;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class E1GuideCatalog
    {
        /// <summary>写入 <c>PipeSupportComponents</c> 的中文类型名，与 Python <c>SUPPORT_TYPE</c> 一致。</summary>
        internal const string SupportType="E1-[不保温管导向架]";
        /// <summary>ASCII 代号，只用于 ItemType 命名，与 Python <c>SUPPORT_CODE</c> 一致。</summary>
        internal const string SupportCode="E1_RACK";

        internal static readonly int[] Dns={15,20,25,32,40,50,65,80,90,100,125,150,200,250,300,350,400,450,500,600,650,700,750,800,850,900};
        private static readonly double[] Ods={21.3,26.7,33.4,42.2,48.3,60.3,73,88.9,101.6,114.3,141.3,168.3,219.1,273,323.8,355.6,406.4,457,508,609.6,660.4,711.2,762,812.8,863.6,914.4};
        internal static readonly E1GuideItem[] Items={
            new E1GuideItem {Key="A",MinDn=15,MaxDn=65,Specification="□50×50×10",FaceWidthMm=50,DepthMm=10,LinerWidthMm=50,LinerHeightMm=50,LinerThicknessMm=1,LoadKn=1},
            new E1GuideItem {Key="B",MinDn=80,MaxDn=150,FamilyId="equal_angle",ProfileName="L50x50x6",ModeId="outer_corner",Specification="∠50×6",FaceWidthMm=50,DepthMm=50,LinerWidthMm=50,LinerHeightMm=60,LinerThicknessMm=2,LoadKn=4},
            new E1GuideItem {Key="C",MinDn=200,MaxDn=300,FamilyId="parallel_channel",ProfileName="10",ModeId="lower_left",Specification="[10",FaceWidthMm=100,DepthMm=48,LinerWidthMm=100,LinerHeightMm=80,LinerThicknessMm=2,LoadKn=6},
            new E1GuideItem {Key="D",MinDn=350,MaxDn=600,FamilyId="hot_rolled_h",ProfileName="H100x100x6x8xr8",ModeId="geometric_center",Specification="H100×100×6×8",FaceWidthMm=100,DepthMm=100,LinerWidthMm=100,LinerHeightMm=90,LinerThicknessMm=2,LoadKn=35},
            new E1GuideItem {Key="E",MinDn=650,MaxDn=900,FamilyId="hot_rolled_h",ProfileName="H150x150x7x10xr8",ModeId="geometric_center",Specification="H150×150×7×10",FaceWidthMm=150,DepthMm=150,LinerWidthMm=150,LinerHeightMm=100,LinerThicknessMm=2,LoadKn=60}
        };
        internal static double Outside(int dn)
        {
            int i=Array.IndexOf(Dns,dn);
            if(i<0)throw new InvalidOperationException("不支持的公称管径 DN"+dn);
            return Ods[i];
        }
        internal static int? MatchDn(double value)
        {
            int best=-1;double error=double.MaxValue;
            for(int i=0;i<Dns.Length;i++)
            {
                double e=Math.Min(Math.Abs(Dns[i]-value),Math.Abs(Ods[i]-value));
                if(e<error){error=e;best=i;}
            }
            return best>=0 && error<=Math.Max(5,Ods[best]*0.05)?(int?)Dns[best]:null;
        }
        internal static E1GuideItem Item(string key)
        { return Items.First(x=>x.Key==key); }
        internal static E1GuideItem AutomaticItem(int dn)
        { return Items.First(x=>dn>=x.MinDn && dn<=x.MaxDn); }
        internal static ModeData ProfileMode(E1GuideItem item)
        {
            return ProfileLookup.Mode(RuntimeData.Families,item.FamilyId,item.ProfileName,
                item.ModeId);
        }
    }
}
