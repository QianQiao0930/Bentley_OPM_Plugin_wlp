using System;

namespace SteelSectionProbe
{
    internal static class N8Catalog
    {
        internal const string SupportType="N8-[设备预焊件连接板]";
        internal const string SupportCode="N8_CONNECTION_PLATE";
        // E, F, G(H), G(C), T, bolt diameter, L(H), L(C), count.
        private static readonly double[,] Table={
            {180,100,18,24,10,16,40,120,4},
            {290,200,22,28,12,20,50,120,4},
            {370,270,27,33,16,24,60,140,4},
            {460,340,33,39,20,30,80,160,4},
            {480,380,27,33,20,24,70,150,8},
            {570,450,33,39,25,30,90,170,8}};
        internal static N8Plan Resolve(int type,string mode,double heading,G2MountFace mount)
        {
            if(type<0||type>5) throw new InvalidOperationException("N8 类型应为 0～5。");
            if(mode!="H"&&mode!="C"&&mode!="N") throw new InvalidOperationException("N8 工况应为 H/C/N。");
            if(double.IsNaN(heading)||double.IsInfinity(heading)) throw new InvalidOperationException("朝向角无效。");
            double d=Table[type,5];
            var p=new N8Plan {Type=type,Mode=mode,HeadingDegrees=heading,MountFace=mount,
                E=Table[type,0],F=Table[type,1],G=Table[type,mode=="C"?3:2],
                T=Table[type,4],BoltDiameter=d,BoltLength=Table[type,mode=="C"?7:6],
                BoltCount=(int)Table[type,8]};
            switch((int)d)
            {
                case 16:p.HeadAcross=p.NutAcross=24;p.HeadHeight=10;p.NutHeight=13;
                    p.WasherOutside=30;p.WasherThickness=3;break;
                case 20:p.HeadAcross=p.NutAcross=30;p.HeadHeight=12.5;p.NutHeight=16;
                    p.WasherOutside=37;p.WasherThickness=3;break;
                case 24:p.HeadAcross=p.NutAcross=36;p.HeadHeight=15;p.NutHeight=19;
                    p.WasherOutside=44;p.WasherThickness=4;break;
                default:p.HeadAcross=p.NutAcross=46;p.HeadHeight=18.7;p.NutHeight=24;
                    p.WasherOutside=56;p.WasherThickness=4;break;
            }
            p.Number="N8-"+type+(mode=="N"?"":"-"+mode);
            p.Specification="连接板 "+p.E+"×"+p.E+"×"+p.T+"；"+
                p.BoltCount+"-Φ"+p.G+" 孔；M"+d+"×"+p.BoltLength;
            return p;
        }
        internal static double[,] HolePositions(N8Plan p)
        {
            double h=p.F/2;
            return p.BoltCount==4?new double[,] {{-h,-h},{h,-h},{h,h},{-h,h}}:
                new double[,] {{-h,-h},{0,-h},{h,-h},{h,0},{h,h},{0,h},{-h,h},{-h,0}};
        }
    }
}
