using System;
using System.Linq;
namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static int checks;
        private static void True(bool value,string label)
        {checks++;if(!value)throw new Exception(label);}
        private static void Equal(double a,double b,string label)
        {True(Math.Abs(a-b)<0.000001,label+": "+a+" != "+b);}
        private static void Reject(Action action,string label)
        {checks++;try{action();}catch(InvalidOperationException){return;}throw new Exception(label);}
        private static void Main()
        {
            double?[,] loads={{1.4,0.5,null,null},{3.6,1.8,0.9,0.5},{10,5,2,1.2},
                {12,5.8,2.5,1.4},{20,10,5,2.8},{39,19,13,7.6},{65,32,22,15},
                {null,70,46,33},{null,120,83,60}};
            double[] heights={50,75,100,126,160,125,150,200,250};
            double[] widths={50,75,100,53,63,125,150,200,250};
            for(int row=0;row<9;row++)
            {
                char key=D2CantileverCatalog.Keys[row];
                var v=D2CantileverCatalog.Require(key);
                var mode=D2CantileverCatalog.Mode(v);
                True(mode.Segments.Length>=6,"真实型钢轮廓 "+key);
                True(mode.Segments.Any(x=>x.IsArc),"保留轧制圆角 "+key);
                for(int col=0;col<4;col++)
                {
                    double b=D2CantileverCatalog.LoadColumns[col];
                    foreach(double distance in new[]{b, col==0?0.001:D2CantileverCatalog.LoadColumns[col-1]+0.001})
                    {
                        var p=new D2CantileverParameters{Subtype=key,LoadDistanceMm=distance};
                        var plan=D2CantileverCalculator.Calculate(p,1150,0);
                        True(plan.VerticalLoadKn==loads[row,col],"荷载边界 "+key+" B="+distance);
                        True(plan.HorizontalLoadKn.HasValue==plan.VerticalLoadKn.HasValue,"空档不外推");
                        if(plan.VerticalLoadKn.HasValue)Equal(plan.HorizontalLoadKn.Value,loads[row,col].Value*0.3,"水平荷载0.3倍");
                        Equal(plan.SectionHeightMm,heights[row],"目录高度");
                        Equal(plan.SectionWidthMm,widths[row],"目录宽度");
                    }
                }
                var standard=D2CantileverCalculator.Calculate(new D2CantileverParameters{Subtype=key},400,0);
                Equal(standard.BeamLengthMm,400,"不带板实长");
                True(standard.Number=="D2-"+key+"-400","不带筋板编号省略h×w");
                foreach(string plate in new[]{"A","B","C","D"})
                {
                    var p=new D2CantileverParameters{Subtype=key,AddPlate=true,PlateSubtype=plate,PlateOffsetMm=20};
                    var plan=D2CantileverCalculator.Calculate(p,600,45);
                    Equal(plan.BeamStartMm,20+plan.Plate.PlateThicknessMm,"板厚和外移");
                    Equal(plan.BeamStartMm+plan.BeamLengthMm,600,"末端保持L");
                    True(plan.Plate.SpacingMm>Math.Max(heights[row],widths[row]),"孔中心在型钢外");
                    Equal(plan.Plate.Parameters.HeadingDegrees,45,"板随辅助线方向");
                    True(plan.Number=="D2-"+key+"-600","连接板不改D2编号");
                }
            }
            double?[,] sideLoads={{1.4,0.5,null,null},{3.6,1.8,0.9,0.5},{10,5,2,1.2},
                {12,5.8,2.5,1.4},{20,10,5,2.8},{31,15,8.8,5},{40,20,12,6.8}};
            for(int row=0;row<7;row++)
            {
                char key="ABCDEFG"[row];
                var v=D2CantileverCatalog.Require("D3",key);
                var mode=D2CantileverCatalog.Mode(v);
                var points=mode.Segments.SelectMany(x=>new[]{new[]{x.X0,x.Y0},new[]{x.X1,x.Y1}}).ToArray();
                for(int type=1;type<=2;type++)
                {
                    for(int col=0;col<4;col++)
                    {
                        double distance=D2CantileverCatalog.LoadColumns[col];
                        foreach(double bValue in new[]{distance,col==0?0.001:D2CantileverCatalog.LoadColumns[col-1]+0.001})
                        {
                            double length=type==2?2300:1150;
                            var p=new D2CantileverParameters{Kind="D3",Type=type,Subtype=key,Name="D3",LoadDistanceMm=bValue};
                            var plan=D2CantileverCalculator.Calculate(p,length,0);
                            True(plan.VerticalLoadKn==sideLoads[row,col],"D3荷载边界");
                            True(plan.HorizontalLoadKn.HasValue==plan.VerticalLoadKn.HasValue,"D3空档无外推");
                            if(plan.VerticalLoadKn.HasValue)Equal(plan.HorizontalLoadKn.Value,plan.VerticalLoadKn.Value*0.3,"D3水平荷载");
                            Equal(plan.BeamLengthMm,length,"D3整段连续构件");
                            Equal(plan.RootStationMm,type==2?length/2:0,"D3生根站位");
                            Equal(plan.SectionAnchorYmm,0,"D3角点无半宽偏移");
                            Equal(plan.SectionAnchorZmm,0,"D3角点标高");
                            True(plan.Number=="D3-"+type+"-"+key+"-"+length,"D3编号含类型");
                            Equal(points.Min(x=>x[0])+plan.SectionAnchorYmm,0,"截面外角位于轴线");
                            Equal(points.Min(x=>x[1]),0,"翻转后翼缘顶面标高为零");
                            True(points.Any(x=>Math.Abs(x[0])<0.000001&&Math.Abs(x[1])<0.000001),"角点是实际轮廓顶点");
                        }
                    }
                }
            }
            var side=new D2CantileverParameters{Kind="D3",Type=2,Name="D3"};
            Equal(D2CantileverCalculator.Calculate(side,800,0).RootStationMm,400,"双悬臂边界通过");
            Reject(()=>D2CantileverCalculator.Calculate(side,799.999,0),"双悬臂余量不足拒绝");
            side.Subtype='H';Reject(()=>D2CantileverCalculator.Calculate(side,800,0),"D3无H子项");
            side.Subtype='A';side.Type=3;Reject(()=>D2CantileverCalculator.Calculate(side,800,0),"D3不支持类型3");
            side.Type=1;side.AddPlate=true;Reject(()=>D2CantileverCalculator.Calculate(side,800,0),"D3不允许端板");
            side.AddPlate=false;side.Kind="D4";Reject(()=>D2CantileverCalculator.Calculate(side,800,0),"未知架型拒绝");
            True(D2CantileverCatalog.AssemblyItemNameFor("D3")!="PipeSupportAssembly_D2_CANTILEVER","D2/D3统计隔离");
            True(D2CantileverCatalog.CellNameFor("D3")!=D2CantileverCatalog.CellName,"D2/D3单元隔离");
            var parameters=new D2CantileverParameters();
            Reject(()=>D2CantileverCalculator.Calculate(parameters,399.999,0),"150余量不足拒绝");
            foreach(double invalid in new[]{0.0,-1.0,1000.001,double.NaN,double.PositiveInfinity})
            {
                parameters.LoadDistanceMm=invalid;
                Reject(()=>D2CantileverCalculator.Calculate(parameters,1150,0),"非法B拒绝");
            }
            parameters.LoadDistanceMm=250;
            foreach(double invalid in new[]{0.0,150.0,double.NaN,double.PositiveInfinity})
                Reject(()=>D2CantileverCalculator.Calculate(parameters,invalid,0),"非法L拒绝");
            Reject(()=>D2CantileverCalculator.Calculate(parameters,400,double.NaN),"非法方向拒绝");
            parameters.Subtype='I';Reject(()=>D2CantileverCalculator.Calculate(parameters,400,0),"无I子项");
            parameters.Subtype='A';parameters.AddPlate=true;
            foreach(double invalid in new[]{-1.0,250.0,double.NaN,double.PositiveInfinity})
            {
                parameters.PlateOffsetMm=invalid;
                Reject(()=>D2CantileverCalculator.Calculate(parameters,600,0),"非法端板外移拒绝");
            }
            parameters.AddPlate=false;parameters.Name=" ";
            True(D2CantileverCalculator.Calculate(parameters,400,0).Number=="D2-A-400","空前缀回落D2");
            CheckG11();
            Console.WriteLine("D2CantileverCheck: "+checks+" checks passed.");
        }
    }
}
