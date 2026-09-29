using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Check(bool value,string name)
        {if(!value)throw new Exception(name);}
        private static void Close(double a,double b,string name)
        {if(Math.Abs(a-b)>0.01)throw new Exception(name+": "+a+" != "+b);}
        private static void Reject(Action action,string name)
        {try{action();}catch(InvalidOperationException){return;}throw new Exception(name+" 应拒绝");}
        private static TriangleBracketParameters Input(string kind,char variant='A')
        {return new TriangleBracketParameters {Kind=kind,Variant=variant,Type=1,L1Mm=600,
            Name=kind,Reverse=false,PlateOffsetMm=0};}
        private static void Main()
        {
            var codes=new HashSet<string>(StringComparer.Ordinal);
            foreach(string kind in TriangleBracketCatalog.Kinds)
            {
                Check(codes.Add(TriangleBracketCatalog.SupportCode(kind)),"ItemType 组合代号唯一");
                Check(TriangleBracketCatalog.SupportType(kind).StartsWith(kind+"-"),"统计类型中文值");
                Check(TriangleBracketCatalog.AssemblyItemName(kind)==
                    "PipeSupportAssembly_"+TriangleBracketCatalog.SupportCode(kind),"Assembly 固定名");
                Check(TriangleBracketCatalog.ComponentItemName(kind,"A")==
                    "PipeSupportComponent_"+TriangleBracketCatalog.SupportCode(kind)+"_A",
                    "构件固定名");
                for(char variant='A';variant<='D';variant++)
                    Check(TriangleBracketCatalog.Variant(kind,variant)!=null,"四个子项存在");
            }
            var d5=TriangleBracketCalculator.Calculate(Input("D5"),1200,0);
            Check(d5.Number=="D5-1-A-600-1200","D5 编号");
            Close(d5.BeamLengthMm,1200,"D5 横担长");
            Close(d5.BraceLengthMm,600*Math.Sqrt(2),"D5 斜撑长");
            var plate=Input("D5");plate.AddPlate=true;plate.PlateSubtype="B";
            var d5Plate=TriangleBracketCalculator.Calculate(plate,1200,0);
            Check(d5Plate.Plate!=null&&d5Plate.Plate.SpacingMm==150,"D5 端板孔距严格超过横担截面");
            Close(d5Plate.BeamStartMm,12,"D5 横担自端板正面起算");
            var d6=TriangleBracketCalculator.Calculate(Input("D6"),1200,0);
            Check(d6.Variant.SectionA=="[12.6"&&d6.HasLoad,"D6 槽钢与荷载");
            Close(d6.AllowableVerticalKn,6,"D6 L1≤750 荷载档");
            var g12=TriangleBracketCalculator.Calculate(Input("G12"),1200,0);
            Check(g12.Variant.BoltSubtype=="B"&&g12.Variant.BoltSpacing==100,"G12 锚栓子项");
            var d19=TriangleBracketCalculator.Calculate(Input("D19"),1500,0);
            Check(d19.QuantityA==2&&d19.QuantityB==2&&d19.Variant.WebGap==60,
                "D19 双槽钢与间距");
            Check(d19.HasLoad&&d19.AllowableVerticalKn==40,"D19 垂直荷载档");
            Reject(()=>TriangleBracketCalculator.Calculate(Input("D6"),1501,0),"D6 L2 上限");
            var shortL1=Input("G12");shortL1.L1Mm=200;
            Reject(()=>TriangleBracketCalculator.Calculate(shortL1,1000,0),"G12 第二根锚栓位置");
            var tooLong=Input("D5");tooLong.L1Mm=1000;
            Reject(()=>TriangleBracketCalculator.Calculate(tooLong,1200,0),"端部余量");
            Console.WriteLine("TriangleBracketCheck: D5/D6/G12/D19 选型、长度、编号、荷载与锚板通过。");
        }
    }
}
