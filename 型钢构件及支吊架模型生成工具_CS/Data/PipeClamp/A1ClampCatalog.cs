using System;
using System.Linq;

namespace SteelSectionProbe
{
    internal sealed class A1ClampRow
    {
        internal int Dn,B,C,D,E,Bolt;
        internal string Nps;
        internal double OutsideMm,AxialKn,WeightKg;
        internal double? LateralKn;
    }

    /// <summary>HG/T 21629 A1 表 1。DN15 的 C 按 B+M6 修正为 31，与 Python 版一致。</summary>
    internal static class A1ClampCatalog
    {
        internal const string SupportType="A1-[U型管卡]";
        internal const string SupportCode="A1_U_BOLT_CLAMP";
        internal const string CellName="A1_U_BOLT_CLAMP";
        internal const uint BoltColor=3,NutColor=3;

        // DN, B, C, D, E, M, 外径, 正向荷载, 横向荷载(无数据为 -1), 重量, NPS
        private static A1ClampRow Row(int dn,int b,int c,int d,int e,int bolt,double od,
            double axial,double lateral,double weight,string nps)
        {return new A1ClampRow{Dn=dn,B=b,C=c,D=d,E=e,Bolt=bolt,OutsideMm=od,
            AxialKn=axial,LateralKn=lateral<0?(double?)null:lateral,WeightKg=weight,Nps=nps};}
        internal static readonly A1ClampRow[] All={
            Row(15,25,31,70,65,6,21.3,2.4,.6,.05,"1/2\""),
            Row(20,33,39,70,65,6,26.7,2.4,.6,.05,"3/4\""),
            Row(25,39,45,70,65,6,33.4,2.4,.6,.05,"1\""),
            Row(32,48,58,75,65,10,42.2,2.4,.6,.13,"1 1/4\""),
            Row(40,54,64,75,65,10,48.3,6.4,1.6,.14,"1 1/2\""),
            Row(50,66,76,85,70,10,60.3,6.4,1.6,.15,"2\""),
            Row(65,79,91,95,80,12,73,12,3,.32,"2 1/2\""),
            Row(80,95,107,100,80,12,88.9,12,3,.35,"3\""),
            Row(90,108,120,115,80,12,101.6,12,3,.38,"3 1/2\""),
            Row(100,120,132,115,80,12,114.3,12,3,.41,"4\""),
            Row(125,147,159,130,80,12,141.3,12,3,.47,"5\""),
            Row(150,174,190,155,95,16,168.3,18,4.5,.91,"6\""),
            Row(200,225,241,180,95,16,219.1,18,4.5,1,"8\""),
            Row(250,279,299,215,110,20,273,28,7,2.2,"10\""),
            Row(300,330,350,245,110,20,323.9,28,7,3.5,"12\""),
            Row(350,362,382,260,110,20,355.6,28,7,3.8,"14\""),
            Row(400,412,432,285,110,20,406.4,28,7,4.2,"16\""),
            Row(450,461,485,320,125,24,457.2,52,-1,6.1,"18\""),
            Row(500,514,538,345,125,24,508,52,-1,6.6,"20\""),
            Row(550,565,589,375,125,24,558.8,52,-1,7.1,"22\""),
            Row(600,616,640,400,125,24,609.6,52,-1,7.7,"24\""),
            Row(650,666,690,425,125,24,660.4,52,-1,8.1,"26\""),
            Row(700,717,741,450,125,24,711.2,52,-1,8.4,"28\""),
            Row(750,768,792,475,125,24,762,52,-1,8.7,"30\""),
            Row(800,819,843,500,125,24,812.8,52,-1,9.3,"32\""),
            Row(850,870,894,525,125,24,863.6,52,-1,9.8,"34\""),
            Row(900,920,944,550,125,24,914.4,52,-1,10.5,"36\"")
        };
        internal static A1ClampRow Require(int dn)
        {var row=All.FirstOrDefault(x=>x.Dn==dn);if(row==null)throw new InvalidOperationException("A1 表 1 没有 DN"+dn);return row;}
        internal static int? MatchDn(double? nominal)
        {
            if(!nominal.HasValue||nominal.Value<=0||double.IsNaN(nominal.Value))return null;
            var row=All.OrderBy(x=>Math.Abs(x.Dn-nominal.Value)).First();
            return Math.Abs(row.Dn-nominal.Value)<=Math.Max(5,nominal.Value*.15)?row.Dn:(int?)null;
        }
    }
}
