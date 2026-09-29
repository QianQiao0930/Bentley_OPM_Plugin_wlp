using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal sealed class TrunnionSize
    {
        internal int Dn;
        internal double OutsideMm, WallMm, SquarePlateMm, PlateThicknessMm;
    }

    internal static class ElbowTrunnionCatalog
    {
        /// <summary>同一元素可能同时暴露管道基类和 HVAC 实际类，优先读取实际类。</summary>
        internal static string SelectElbowClass(IDictionary<string,Dictionary<string,string>> groups)
        {
            string best=null;
            int bestScore=-1;
            foreach(var group in groups)
            {
                string key=group.Key;
                if(!key.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase) ||
                    key.IndexOf("ELBOW",StringComparison.OrdinalIgnoreCase)<0) continue;
                int score=(key.IndexOf("HVAC",StringComparison.OrdinalIgnoreCase)>=0?100:0)+
                    (key.IndexOf("90_DEGREE",StringComparison.OrdinalIgnoreCase)>=0?3:0)+
                    (group.Value.ContainsKey("ANGLE")?1:0)+
                    (group.Value.ContainsKey("OUTSIDE_DIAMETER")?1:0);
                if(score>bestScore) { bestScore=score; best=key; }
            }
            return best;
        }
        private static readonly Dictionary<int, double[]> Pipe = new Dictionary<int, double[]>
        {
            {15,new[]{21.3,2.77}}, {20,new[]{26.9,2.87}}, {25,new[]{33.7,3.38}},
            {32,new[]{42.4,3.56}}, {40,new[]{48.3,3.68}}, {50,new[]{60.3,3.91}},
            {65,new[]{76.1,5.16}}, {80,new[]{88.9,5.49}}, {100,new[]{114.3,6.02}},
            {125,new[]{139.7,6.55}}, {150,new[]{168.3,7.11}}, {200,new[]{219.1,8.18}},
            {250,new[]{273.0,9.27}}, {300,new[]{323.9,9.53}}, {350,new[]{355.6,9.53}},
            {400,new[]{406.4,9.53}}, {450,new[]{457.2,9.53}}, {500,new[]{508.0,9.53}},
            {550,new[]{559.0,9.53}}, {600,new[]{610.0,9.53}}, {650,new[]{660.0,18.89}},
            {700,new[]{711.0,19.05}}, {750,new[]{762.0,19.05}}, {800,new[]{813.0,19.05}},
            {850,new[]{864.0,19.05}}, {900,new[]{914.0,19.05}}, {950,new[]{965.0,19.05}},
            {1000,new[]{1016.0,19.05}}, {1050,new[]{1067.0,19.05}},
            {1100,new[]{1118.0,19.05}}, {1200,new[]{1219.2,19.05}}
        };
        private static readonly int[] MainDns = { 15,20,25,32,40,50,100,150,200,250,300,350,400,
            450,500,550,600,650,700,750,800,850,900,950,1000,1050,1100,1200 };
        private static readonly double[,] Table = {
            {50,0,200,10}, {100,50,200,10}, {150,80,200,10}, {200,100,200,12},
            {300,150,250,12}, {400,200,300,12}, {500,250,350,16},
            {600,300,400,16}, {700,350,450,20}, {800,400,500,20},
            {900,450,550,20}, {1000,500,600,25}, {1200,600,700,25}
        };
        internal static int MainDn(double nominalMm)
        {
            foreach (int dn in MainDns)
                if (Math.Abs(nominalMm - dn) <= Math.Max(0.6, dn * 0.005)) return dn;
            throw new InvalidOperationException("弯头公称直径不在四个原脚本支持的规格内：" + nominalMm + " mm。");
        }
        /// <summary>风管按实际外径选表 1 档位；鞍口仍使用实际外径。</summary>
        internal static int DuctMainDn(double outsideMm,out string note)
        {
            if(double.IsNaN(outsideMm)||double.IsInfinity(outsideMm)||outsideMm<=0)
                throw new InvalidOperationException("风管外径必须大于 0。");
            foreach(int dn in MainDns)
                if(Math.Abs(outsideMm-dn)<=0.5) { note=""; return dn; }
            int nearest=MainDns[0];
            double distance=double.MaxValue;
            foreach(int dn in MainDns)
            {
                double delta=Math.Abs(outsideMm-Pipe[dn][0]);
                if(delta<distance) { distance=delta; nearest=dn; }
            }
            double pipeOd=Pipe[nearest][0];
            if(distance<=pipeOd*0.05)
            {
                note="风管外径无对应管道 DN，按外径就近匹配到 DN"+nearest+
                    " 档，仅用于选耳轴和底板；鞍口按风管实际外径建模，请复核。";
                return nearest;
            }
            int maximum=MainDns[MainDns.Length-1];
            if(outsideMm>Math.Max(maximum,Pipe[maximum][0]))
            {
                note="风管外径超出现有选型表范围，采用 DN"+maximum+
                    " 最大档保底选耳轴和底板；鞍口按实际外径建模，承载能力需另行校核。";
                return maximum;
            }
            throw new InvalidOperationException("风管外径未匹配到表 1 的任何管道档位，无法自动选耳轴。");
        }
        internal static TrunnionSize ForMainDn(int mainDn)
        {
            for (int i=0;i<Table.GetLength(0);i++)
            {
                if (mainDn > Table[i,0]) continue;
                int dn = Table[i,1] == 0 ? mainDn : (int)Table[i,1];
                double[] pipe;
                if (!Pipe.TryGetValue(dn,out pipe)) break;
                return new TrunnionSize { Dn=dn, OutsideMm=pipe[0], WallMm=pipe[1],
                    SquarePlateMm=Table[i,2], PlateThicknessMm=Table[i,3] };
            }
            throw new InvalidOperationException("主弯头超出耳轴选型表 DN1200 上限。");
        }
        internal static double EndPlateThickness(int dn, char plate)
        {
            if (plate == 'C') return 0;
            if (plate == 'A') return 6;
            if (plate != 'B') throw new InvalidOperationException("未知端板类型。");
            if (dn <= 80) return 10;
            if (dn <= 200) return 12;
            if (dn <= 300) return 16;
            if (dn <= 450) return 20;
            if (dn <= 600) return 25;
            return 30;
        }

        /// <summary>四个组合的 ASCII 代号，与 Python 各脚本的 <c>SUPPORT_CODE</c> 一致。
        /// 只用于 ItemType 命名，不写入属性值。</summary>
        internal const string F2VerticalCode="F2_VERTICAL_ELBOW_TRUNNION";
        internal const string F2HorizontalCode="F2_HORIZONTAL_ELBOW_TRUNNION";
        internal const string F4VerticalCode="F4_VERTICAL_ELBOW_HORIZONTAL_TRUNNION";
        internal const string F5HorizontalCode="F5_HORIZONTAL_ELBOW_HORIZONTAL_TRUNNION";

        /// <summary>
        /// 组合代号 -> 写入 <c>PipeSupportComponents</c> 的中文类型名，
        /// 与 Python 各脚本的 <c>SUPPORT_TYPE</c> 逐字一致（统计按该属性聚合套数）。
        /// </summary>
        internal static string SupportType(string supportCode)
        {
            switch(supportCode)
            {
                case F2VerticalCode: return "F2-[竖直弯头的竖直耳轴]";
                case F2HorizontalCode: return "F2-[水平弯头的竖直耳轴]";
                case F4VerticalCode: return "F4-[竖直弯头的水平耳轴]";
                case F5HorizontalCode: return "F5-[水平弯头的水平耳轴]";
                default: throw new InvalidOperationException("未知的耳轴组合代号："+supportCode);
            }
        }
    }
}
