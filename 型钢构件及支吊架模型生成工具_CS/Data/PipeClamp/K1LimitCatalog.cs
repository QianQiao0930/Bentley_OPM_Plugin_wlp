using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>K1 限位架的一个子项。尺寸单位 mm。</summary>
    internal sealed class K1LimitSubitem
    {
        internal string Key;
        internal int MinDn,MaxDn;
        internal string Nps;
        /// <summary>true = 子项 A 的半片 T 形（竖直）；false = 完整 H 型钢（水平、沿管轴）。</summary>
        internal bool IsHalfT;
        internal string FamilyId,ProfileName,ModeId;
        /// <summary>子项 A 的立柱竖直长度。</summary>
        internal double HeightMm;
        /// <summary>子项 B/C 的型钢沿管轴长度。</summary>
        internal double LengthMm;
        /// <summary>子项 B/C 的两翼缘净距基准（型钢高度 H）。</summary>
        internal double CrossHeightMm;
        /// <summary>子项 B/C 的翼缘宽度 B。</summary>
        internal double CrossWidthMm;
        /// <summary>子项 B/C 的翼缘厚度 t2（用于算两翼缘净距 b = H − 2×t2）。</summary>
        internal double FlangeThicknessMm;
        /// <summary>底板 (边长, 边长, 厚)；null 表示无底板。</summary>
        internal double[] Plate;
        internal string Specification;
        /// <summary>子项 A 半片 T 形的截面尺寸（翼缘宽、翼缘厚、腹板厚、腹板长）。</summary>
        internal double TFlangeWidthMm,TFlangeThicknessMm,TWebThicknessMm,TWebLengthMm;

        internal double MainSizeMm { get { return IsHalfT?HeightMm:LengthMm; } }
        internal string MainSizeLabel { get { return IsHalfT?"立柱高 H":"型钢沿管轴长 L"; } }
    }

    /// <summary>
    /// K1 不保温管限位架的子项表、DN/外径表与几何常量。
    /// 纯数据，不引用 Bentley API。来源：<c>管道支吊架/模块/K1限位架/K1限位架_几何.py</c>。
    /// </summary>
    internal static class K1LimitCatalog
    {
        internal const string SupportType="K1-[不保温管的限位架]";
        internal const string SupportCode="K1_LIMIT_FRAME";
        internal const string CellName="K1_LIMIT_FRAME";
        internal const string DefaultSubitemKey="A";
        internal const int FallbackDn=150;
        internal const double WeldLegMaxMm=6.0;
        internal const double GapMm=3.0;
        internal const double DefaultExistingWidthMm=100.0;
        internal const string DefaultMaterial="Q235B";
        /// <summary>限位块颜色（与 Python 一致，型钢 7 号索引）。</summary>
        internal const uint BlockColor=7,PlateColor=7;

        private static readonly int[] Dns={15,20,25,32,40,50,65,80,90,100,125,150,200,250,300,
            350,400,450,500,600,650,700,750,800,850,900};
        private static readonly double[] Ods={21.3,26.7,33.4,42.2,48.3,60.3,73.0,88.9,101.6,114.3,
            141.3,168.3,219.1,273.0,323.8,355.6,406.4,457.0,508.0,609.6,660.4,711.2,762.0,812.8,
            863.6,914.4};
        private static readonly Dictionary<int,string> NpsByDn=new Dictionary<int,string>{
            {15,"1/2\""},{20,"3/4\""},{25,"1\""},{32,"1 1/4\""},{40,"1 1/2\""},{50,"2\""},
            {65,"2 1/2\""},{80,"3\""},{100,"4\""},{125,"5\""},{150,"6\""},{200,"8\""},
            {250,"10\""},{300,"12\""},{350,"14\""},{400,"16\""},{450,"18\""},{500,"20\""},
            {600,"24\""},{650,"26\""},{700,"28\""},{750,"30\""},{800,"32\""},{850,"34\""},
            {900,"36\""}
        };

        private static readonly K1LimitSubitem[] Subitems={
            new K1LimitSubitem {
                Key="A",MinDn=15,MaxDn=80,Nps="1/2\"~3\"",IsHalfT=true,
                ProfileName="H100x100x6x8xr8",HeightMm=100.0,
                Specification="1/2 H100×100×6×8",
                TFlangeWidthMm=100.0,TFlangeThicknessMm=8.0,TWebThicknessMm=6.0,
                TWebLengthMm=42.0 },
            new K1LimitSubitem {
                Key="B",MinDn=100,MaxDn=250,Nps="4\"~10\"",IsHalfT=false,
                FamilyId="hot_rolled_h",ProfileName="H100x100x6x8xr8",ModeId="geometric_center",
                LengthMm=150.0,CrossHeightMm=100.0,CrossWidthMm=100.0,FlangeThicknessMm=8.0,
                Plate=new[]{150.0,150.0,10.0},Specification="H100×100×6×8" },
            new K1LimitSubitem {
                Key="C",MinDn=300,MaxDn=900,Nps="12\"~36\"",IsHalfT=false,
                FamilyId="hot_rolled_h",ProfileName="H150x150x7x10xr8",ModeId="geometric_center",
                LengthMm=200.0,CrossHeightMm=150.0,CrossWidthMm=150.0,FlangeThicknessMm=10.0,
                Plate=new[]{200.0,200.0,10.0},Specification="H150×150×7×10" }
        };

        internal static K1LimitSubitem[] All { get { return Subitems; } }
        internal static int[] DnChoices { get { return Dns; } }

        internal static double Od(int dn)
        {
            int index=Array.IndexOf(Dns,dn);
            if(index<0) throw new InvalidOperationException("未知公称直径：DN"+dn);
            return Ods[index];
        }

        internal static string Nps(int dn)
        {
            string text;
            return NpsByDn.TryGetValue(dn,out text)?text:"";
        }

        internal static string DnLabel(int dn)
        {
            string nps=Nps(dn);
            return nps.Length>0?"DN"+dn+"（"+nps+"）":"DN"+dn;
        }

        /// <summary>把管道信息里的直径（公称值或外径）匹配到最近 DN；超出容差返回 null。</summary>
        internal static int? MatchDn(double value,double tolerance=5.0,double ratio=0.05)
        {
            if(double.IsNaN(value) || double.IsInfinity(value)) return null;
            int bestDn=Dns[0],bestOdIndex=0;
            double errorDn=double.MaxValue,errorOd=double.MaxValue;
            for(int i=0;i<Dns.Length;i++)
            {
                double e=Math.Abs(Dns[i]-value);
                if(e<errorDn) { errorDn=e; bestDn=Dns[i]; }
                double e2=Math.Abs(Ods[i]-value);
                if(e2<errorOd) { errorOd=e2; bestOdIndex=i; }
            }
            int chosen;double error;
            if(errorDn<=errorOd) { chosen=bestDn; error=errorDn; }
            else { chosen=Dns[bestOdIndex]; error=errorOd; }
            return error<=Math.Max(tolerance,ratio*Ods[Array.IndexOf(Dns,chosen)])?(int?)chosen:null;
        }

        internal static K1LimitSubitem Require(string key)
        {
            var item=Find(key);
            if(item==null) throw new InvalidOperationException("未知子项："+key);
            return item;
        }
        internal static K1LimitSubitem Find(string key)
        {
            if(string.IsNullOrEmpty(key)) return null;
            return Subitems.FirstOrDefault(x=>string.Equals(x.Key,key.Trim().ToUpperInvariant(),
                StringComparison.Ordinal));
        }
        internal static bool IsKnownKey(string key) { return Find(key)!=null; }

        /// <summary>按 DN 选子项；超出全部区间时取最近的一个。</summary>
        internal static string SubitemForDn(int dn)
        {
            foreach(var item in Subitems)
                if(dn>=item.MinDn && dn<=item.MaxDn) return item.Key;
            var nearest=Subitems.OrderBy(item=>dn<item.MinDn?item.MinDn-dn:dn-item.MaxDn).First();
            return nearest.Key;
        }

        /// <summary>管架编号：<c>K1-子项-管径</c>（子项 A 省略管径，图注 5）。</summary>
        internal static string BuildNumber(string subitem,int dn)
        {
            var item=Require(subitem);
            return item.IsHalfT?"K1-"+item.Key
                :"K1-"+item.Key+"-"+dn.ToString(CultureInfo.InvariantCulture);
        }

        internal static string SubitemLabel(string key)
        {
            var item=Require(key);
            string plate=item.Plate!=null
                ?" + 底板 "+F0(item.Plate[0])+"×"+F0(item.Plate[1])+"×"+F0(item.Plate[2]):"";
            return item.Key+"：DN"+item.MinDn+"~"+item.MaxDn+"（"+item.Nps+"）· "+item.Specification+
                "（"+(item.IsHalfT?"H":"L")+" "+F0(item.MainSizeMm)+"）"+plate;
        }

        private static string F0(double value)
        { return value.ToString("0",CultureInfo.InvariantCulture); }
    }
}
