using System;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>L2 表 1 的保冷管托尺寸与荷载；几何中未列的耳板和底板宽沿用 T4。</summary>
    internal sealed class L2ShoeRow
    {
        internal int Dn;
        internal string Bolt;
        internal double LengthMm,SpacingFMm,EndEMm,T1Mm,T2Mm,T3Mm;
        internal double UpperDensityKgM3,LowerDensityKgM3;
        internal double VerticalLoadKn,LateralLoadKn,AxialMovementMm;
    }

    internal static class L2ShoeCatalog
    {
        internal const string SupportType="L2-[最小长度的保冷管托]";
        internal const string SupportCode="L2_COLD_PIPE_SHOE";
        internal const string CellName="L2_COLD_PIPE_SHOE";
        internal const int DefaultDn=200;
        internal const double DefaultColdMm=50.0;
        internal const string DefaultFCode="";

        private static readonly L2ShoeRow[] Rows={
            Make(15,"M10",150,80,35,6,6,6,160,160,.6,.2,50),
            Make(20,"M10",150,80,35,6,6,6,160,160,.8,.25,50),
            Make(25,"M10",150,80,35,6,6,6,160,160,1,.32,50),
            Make(40,"M10",150,80,35,6,6,6,160,160,1.5,.45,50),
            Make(50,"M10",150,80,35,6,6,6,160,160,1.9,.55,50),
            Make(80,"M12",150,80,35,8,6,6,160,160,3.3,1,50),
            Make(100,"M12",150,80,35,8,6,6,160,160,4.2,1.2,50),
            Make(125,"M12",150,80,35,8,6,8,160,160,9,3.2,50),
            Make(150,"M12",150,80,35,8,6,8,160,160,10,3.5,50),
            Make(200,"M16",300,150,75,10,10,10,160,225,32,9.7,100),
            Make(250,"M16",300,150,75,10,10,10,160,225,40,12,100),
            Make(300,"M16",300,150,75,10,10,10,160,225,48,14,100),
            Make(350,"M16",300,150,75,10,10,10,160,225,52,15,100),
            Make(400,"M16",300,150,75,10,10,10,160,225,60,18,100),
            Make(450,"M20",300,150,75,12,10,12,160,225,66,22,100),
            Make(500,"M20",300,150,75,12,10,12,160,225,80,26,100),
            Make(550,"M20",300,150,75,12,10,12,160,225,100,30,100),
            Make(600,"M20",300,150,75,12,10,12,160,225,100,30,100)
        };
        private static L2ShoeRow Make(int dn,string bolt,double length,double f,double e,
            double t1,double t2,double t3,double upper,double lower,double vertical,
            double lateral,double movement)
        { return new L2ShoeRow {Dn=dn,Bolt=bolt,LengthMm=length,SpacingFMm=f,EndEMm=e,
            T1Mm=t1,T2Mm=t2,T3Mm=t3,UpperDensityKgM3=upper,LowerDensityKgM3=lower,
            VerticalLoadKn=vertical,LateralLoadKn=lateral,AxialMovementMm=movement}; }

        internal static L2ShoeRow[] All { get { return Rows; } }
        internal static int[] DnChoices { get { return Rows.Select(x=>x.Dn).ToArray(); } }
        internal static L2ShoeRow Require(int dn)
        {
            var row=Rows.FirstOrDefault(x=>x.Dn==dn);
            if(row==null) throw new InvalidOperationException("L2 本阶段仅支持 DN15~600 的表列管径。");
            return row;
        }
        internal static double HeightForCold(double cold)
        {
            if(double.IsNaN(cold)||double.IsInfinity(cold)||cold<1||cold>275)
                throw new InvalidOperationException("L2 保冷厚度须在 1~275 mm 内。");
            if(cold<=25) return 100;
            if(cold<=75) return 150;
            if(cold<=125) return 200;
            if(cold<=175) return 250;
            if(cold<=225) return 300;
            return 350;
        }
        internal static string BuildNumber(int dn,double cold,string fCode)
        {
            string number="L2-DN"+dn+"-"+cold.ToString("0.#",System.Globalization.CultureInfo.InvariantCulture);
            string code=(fCode??"").Trim();
            return code.Length>0?number+"-"+code:number;
        }
    }
}
