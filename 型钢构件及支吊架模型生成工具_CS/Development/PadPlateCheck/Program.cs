using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    // Pure stubs for catalog tests; production versions are backed by Bentley geometry.
    internal struct VectorMm
    {
        internal double X,Y,Z;
        internal VectorMm(double x,double y,double z){X=x;Y=y;Z=z;}
        internal VectorMm Unit(){double n=Math.Sqrt(X*X+Y*Y+Z*Z);if(n<=0)throw new Exception("zero axis");return new VectorMm(X/n,Y/n,Z/n);}
    }
    internal sealed class PipeClampSelection
    {
        internal double AxisX,AxisY,AxisZ;
        internal bool IsPipe;
        internal double? NominalMm;
        internal string PipeNumber="";
        internal double[] ProjectedCenter(){return new[]{0.0,0.0,0.0};}
    }
    internal static class Program
    {
        private static void Equal(double actual,double expected,string label)
        {if(Math.Abs(actual-expected)>1e-6)throw new Exception(label+": "+actual+" != "+expected);}
        private static void Equal(string actual,string expected,string label)
        {if(actual!=expected)throw new Exception(label+": "+actual+" != "+expected);}
        private static void Main()
        {
            Equal(PadPlateCatalog.Outside(100),114.3,"DN100 外径");
            Equal(PadPlateCatalog.Thickness(200),6,"DN200 板厚");
            Equal(PadPlateCatalog.Thickness(250),8,"DN250 板厚");
            Equal(PadPlateCatalog.Thickness(500),10,"DN500 板厚");
            Equal(PadPlateCatalog.DuctThickness(2000),6,"风管 2000 板厚");
            Equal(PadPlateCatalog.DuctThickness(2000.1),10,"风管超过 2000 板厚");
            Equal(PadPlateCatalog.MatchDn(114.3).Value,100,"外径匹配 DN100");
            var p=new PadPlateParameters();
            var line=new PipeClampSelection{IsPipe=true,NominalMm=100,AxisX=1};
            var y=PadPlateCatalog.Y2(p,line);
            Equal(y.Number,"Y2-100-300-C1-120","Y2 编号");
            Equal(y.InnerRadiusMm,57.15,"Y2 内弧");
            Equal(y.OuterRadiusMm,63.15,"Y2 外弧");
            var hvac=PadPlateHvacCatalog.Resolve(new[]{
                new KeyValuePair<string,string>("OpenPlant_3D.HVAC_ROUND_DUCT.MAIN_DIAMETER","450"),
                new KeyValuePair<string,string>("OpenPlant_3D.HVAC_ROUND_DUCT.UNIT_OF_MEASURE","MM")});
            Equal(hvac.OutsideMm,450,"直风管实际外径");
            Equal(hvac.SizeLabel,"D450","直风管尺寸文字");
            y=PadPlateCatalog.Y2(p,line,hvac);
            Equal(y.Number,"Y2-D450-300-C1-120","Y2 风管编号");
            Equal(y.InnerRadiusMm,225,"Y2 风管内弧");
            Equal(y.ThicknessMm,6,"Y2 风管板厚");
            Equal(y.Specification.StartsWith("D450 OD450" )?1:0,1,"Y2 风管规格");
            hvac=PadPlateHvacCatalog.Resolve(new[]{
                new KeyValuePair<string,string>("OpenPlant_3D.HVAC_ROUND_DUCT.OUTSIDE_DIAMETER","2.1"),
                new KeyValuePair<string,string>("OpenPlant_3D.HVAC_ROUND_DUCT.UNIT_OF_MEASURE","M")});
            y=PadPlateCatalog.Y2(p,line,hvac);
            Equal(y.OutsideMm,2100,"Y2 风管米制单位");
            Equal(y.ThicknessMm,10,"Y2 大风管板厚");
            Equal(y.Number,"Y2-D2100-300-C1-120","Y2 大风管编号");
            try{PadPlateHvacCatalog.Resolve(new[]{
                new KeyValuePair<string,string>("OpenPlant_3D.HVAC_RECT_DUCT.MAIN_DIAMETER","450")});
                throw new Exception("矩形风管应被拒绝");}
            catch(InvalidOperationException){}
            var elbow=new PadPlateElbow{Dn=100,OutsideMm=114.3,CenterToEndMm=152.4};
            var e=PadPlateCatalog.Elbow(p,elbow);
            Equal(e.Number,"弯头垫板-100-1.5","弯头编号");
            Equal(e.BendRadiusMm,152.4,"管道弯头半径");
            Equal(e.ArcLengthMm,152.4*75*Math.PI/180,"弯头弧长");
            var duct=new PadPlateElbow{IsDuct=true,OutsideMm=2100,CenterToEndMm=2100,SizeLabel="D2100"};
            e=PadPlateCatalog.Elbow(p,duct);
            Equal(e.Number,"弯头垫板-D2100-1.0","风管编号");
            Equal(e.ThicknessMm,10,"风管板厚");
            Equal(e.InnerRadiusMm,1050,"风管内弧");
            Equal(PadPlateCatalog.AssemblyItemName(PadPlateKind.Y2),"PipeSupportAssembly_Y2_ARC_PAD","Y2 固定类型");
            Equal(PadPlateCatalog.ComponentItemName(PadPlateKind.Elbow),"PipeSupportComponent_ELBOW_PAD_PAD","弯头固定类型");
            Console.WriteLine("PadPlateCheck: Y2 / 弯头垫板尺寸、编号、风管和固定 ItemType 通过。");
        }
    }
}
