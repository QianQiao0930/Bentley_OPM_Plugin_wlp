using System;
using System.Collections.Generic;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>A2 标准型 2 螺栓管夹表 1 的一行。尺寸单位 mm。</summary>
    internal sealed class A2ClampRow
    {
        internal int Dn;
        internal string Nps;
        /// <summary>内孔直径 A。</summary>
        internal double A;
        /// <summary>螺栓孔心距中心的距离 B（半径向）。</summary>
        internal double B;
        /// <summary>管夹板宽 C（垂直于管轴的箱体宽度方向）。</summary>
        internal double C;
        /// <summary>螺栓中心到管夹端部的距离 D。</summary>
        internal double D;
        /// <summary>螺栓规格，如 M16。</summary>
        internal string Bolt;
        /// <summary>板厚 t（G 列 × 前的数字）。</summary>
        internal double PlateThickness;
        /// <summary>板宽 w（G 列 × 后的数字，也是沿管轴的厚度）。</summary>
        internal double Width;
        internal double BoltDiameterMm
        {
            get
            {
                string digits=new string(Bolt.Where(char.IsDigit).ToArray());
                return double.Parse(digits,System.Globalization.CultureInfo.InvariantCulture);
            }
        }
    }

    /// <summary>A2 标准型 2 螺栓管夹的表 1 与建模常量。纯数据，不引用 Bentley API。</summary>
    internal static class A2ClampCatalog
    {
        internal const string SupportType="A2-[标准型2螺栓管夹]";
        internal const string SupportCode="STD_2BOLT_CLAMP";
        internal const string CellName="STD_2BOLT_CLAMP";
        /// <summary>兜底管径：管道公称直径读不到或不在表 1 时使用。</summary>
        internal const int FallbackDn=100;
        /// <summary>保温管是否按保温层外径放大内孔（内孔 A′ = A + 2×保温厚度）。</summary>
        internal const bool AccommodateInsulation=true;
        internal const double ThroughMarginMm=5.0;
        internal const double HexAcrossFlatsRatio=1.5;
        internal const double BoltHeadHeightRatio=0.625;
        internal const double NutHeightRatio=0.8;
        internal const double BoltTipExtraMm=4.0;
        /// <summary>管夹本体颜色（与 Python 一致取 3 号索引）。</summary>
        internal const uint BodyColor=3,BoltColor=7;

        private static readonly A2ClampRow[] Rows={
            Make(15,"1/2\"",25,28,12,30,"M10",5,30),
            Make(20,"3/4\"",30,30,12,30,"M10",5,30),
            Make(25,"1\"",37,34,12,30,"M10",5,30),
            Make(32,"1 1/4\"",45,38,12,30,"M10",5,30),
            Make(40,"1 1/2\"",51,41,12,30,"M10",5,30),
            Make(50,"2\"",63,52,15,40,"M12",6,40),
            Make(65,"2 1/2\"",79,60,15,40,"M12",6,40),
            Make(80,"3\"",92,66,15,40,"M12",6,40),
            Make(90,"3 1/2\"",105,73,15,40,"M12",6,40),
            Make(100,"4\"",117,84,20,50,"M16",8,50),
            Make(125,"5\"",143,97,20,50,"M16",8,50),
            Make(150,"6\"",171,116,25,60,"M20",10,60),
            Make(200,"8\"",222,141,25,60,"M20",10,60),
            Make(250,"10\"",276,176,25,75,"M24",12,75),
            Make(300,"12\"",328,202,25,75,"M24",12,75),
            Make(350,"14\"",359,217,30,75,"M24",12,75),
            Make(400,"16\"",409,242,30,75,"M24",12,75),
            Make(450,"18\"",460,268,35,75,"M24",16,75),
            Make(500,"20\"",511,301,35,90,"M30",16,90),
            Make(550,"22\"",563,327,35,90,"M30",16,90),
            Make(600,"24\"",613,352,40,90,"M30",16,90),
            Make(650,"26\"",663,387,50,110,"M36",20,110),
            Make(700,"28\"",714,412,50,110,"M36",20,110),
            Make(750,"30\"",765,438,50,110,"M36",20,110)
        };

        private static A2ClampRow Make(int dn,string nps,double a,double b,double c,double d,
            string bolt,double plateThickness,double width)
        {
            return new A2ClampRow {Dn=dn,Nps=nps,A=a,B=b,C=c,D=d,Bolt=bolt,
                PlateThickness=plateThickness,Width=width};
        }

        internal static A2ClampRow[] All { get { return Rows; } }

        internal static int[] Dns { get { return Rows.Select(x=>x.Dn).ToArray(); } }

        internal static A2ClampRow Require(int dn)
        {
            var row=Rows.FirstOrDefault(x=>x.Dn==dn);
            if(row==null) throw new InvalidOperationException("表 1 中无 DN"+dn+"。");
            return row;
        }

        /// <summary>把管道公称直径（mm）匹配到表 1 的 DN；匹配不上返回 null。</summary>
        internal static int? MatchDn(double? nominalMm)
        {
            if(!nominalMm.HasValue) return null;
            double value=nominalMm.Value;
            if(double.IsNaN(value) || double.IsInfinity(value) || value<=0) return null;
            int best=Rows[0].Dn;
            double error=double.MaxValue;
            foreach(var row in Rows)
            {
                double e=Math.Abs(row.Dn-value);
                if(e<error) { error=e; best=row.Dn; }
            }
            return error<=Math.Max(5.0,0.15*value)?(int?)best:null;
        }
    }
}
