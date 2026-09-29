using System;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Check(bool okay,string name){if(!okay)throw new Exception(name);}
        private static void Close(double actual,double expected,string name)
        {if(Math.Abs(actual-expected)>0.001)throw new Exception(name+": "+actual+" != "+expected);}
        private static void Fails(Action action,string name)
        {try{action();}catch(InvalidOperationException){return;}throw new Exception(name);}
        private static LBracketSelection Shape(double h,double l,bool hanger=false)
        {return new LBracketSelection {Corner=new LBracketPoint(0,0,0),
            PostEnd=new LBracketPoint(0,0,hanger?h:-h),ArmEnd=new LBracketPoint(l,0,0),
            HeightMm=h,LengthMm=l,RunX=1,RunY=0};}
        private static void Main()
        {
            var line=LBracketShapeParser.Parse(new[]{
                new[]{new LBracketPoint(800,0,1000),new LBracketPoint(0,0,1000)},
                new[]{new LBracketPoint(0,0,0),new LBracketPoint(0,0,1000)}});
            Close(line.HeightMm,1000,"反向折线 H");Close(line.LengthMm,800,"反向折线 L");
            Close(line.RunX,1,"横担方向");
            var cornerGap=LBracketShapeParser.Parse(new[]{
                new[]{new LBracketPoint(0,0,0),new LBracketPoint(0,0,1000)},
                new[]{new LBracketPoint(0,0,1000.4),new LBracketPoint(500,0,1000.4)}});
            Close(cornerGap.Corner.Z,1000.2,"拐点 0.5 mm 容差");
            Fails(()=>LBracketShapeParser.Parse(new[]{
                new[]{new LBracketPoint(0,0,0),new LBracketPoint(0,0,1000)}}),"只一段无效");
            Fails(()=>LBracketShapeParser.Parse(new[]{
                new[]{new LBracketPoint(0,0,0),new LBracketPoint(0,0,1000)},
                new[]{new LBracketPoint(200,0,1000),new LBracketPoint(800,0,1000)}}),"不相连无效");
            var a=LBracketCatalog.Require('A');
            Check(LBracketCatalog.AssemblyItemName=="PipeSupportAssembly_L_PIPE_RACK","Assembly 名固定");
            Check(LBracketCatalog.ComponentItemName("Post")=="PipeSupportComponent_L_PIPE_RACK_Post","立杆名固定");
            foreach(char key in LBracketCatalog.Keys)
            {
                var v=LBracketCatalog.Require(key);
                Check(ProfileLookup.Mode(RuntimeData.Families,v.Family,v.Profile,
                    v.Family=="equal_angle"?"outer_corner":
                    v.Family=="parallel_channel"?"lower_left":"geometric_center")!=null,
                    key+" 型钢截面存在");
                var p=new LBracketParameters {Variant=key,Type=1,WidthMm=250,Name="D7"};
                var plan=LBracketCalculator.Calculate(p,Shape(500,600));
                Check(plan.Number=="D7-1-"+key+"-500-600",key+" 编号");
                Check(plan.AllowableLoadKn.HasValue,key+" 荷载");
                Close(plan.AllowableLoadKn.Value,v.Loads[0][0].Value,key+" 表值");
                Fails(()=>LBracketCalculator.Calculate(p,Shape(v.MaxHeightMm+2,600)),key+" H 上限");
                p.WidthMm=v.MaxWidthMm+1;
                Fails(()=>LBracketCalculator.Calculate(p,Shape(500,600)),key+" B 上限");
            }
            var c=new LBracketParameters {Variant='C',Type=2,WidthMm=500,Name=""};
            var cc=LBracketCalculator.Calculate(c,Shape(1000,800));
            Check(cc.Number=="","空名称不编号");Close(cc.AllowableLoadKn.Value,1,"C 荷载");
            var e=new LBracketParameters {Variant='E',Type=3,WidthMm=750,Name="D7"};
            var ep=LBracketCalculator.Calculate(e,Shape(1000,700,true));
            Close(ep.PostCutLengthMm,1000,"E 吊架立杆下料");
            Close(ep.ArmCutLengthMm,777.5,"E 横担下料");
            Fails(()=>LBracketCalculator.Calculate(e,Shape(1000,700)),"吊架方向");
            e.Type=4;Fails(()=>LBracketCalculator.Calculate(e,Shape(1000,700,true)),"E/F 侧焊无效");
            var d=new LBracketParameters {Variant='D',Type=1,WidthMm=500,Name="D7"};
            var dp=LBracketCalculator.Calculate(d,Shape(3000,650));
            Close(dp.AllowableLoadKn.Value,0.5,"D 最大 H/B 档位");
            Console.WriteLine("LBracketCheck: A-F 规格、荷载、上下限、几何下料、类型与固定附加项名通过。");
        }
    }
}
