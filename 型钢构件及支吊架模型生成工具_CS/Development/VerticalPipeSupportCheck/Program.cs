using System;
using SteelSectionProbe;

namespace SteelSectionProbe
{
    internal sealed class PipeClampSelection
    {
        internal double AxisX,AxisY,AxisZ;
    }
}
internal static class Program
{
    private static void Assert(bool condition,string label)
    { if(!condition) throw new Exception(label); }
    private static void Main()
    {
        Assert(VerticalPipeSupportCatalog.SupportType(VerticalPipeSupportKind.F6)==
            "F6_F7-[立管的耳轴]","F6 Python SupportType");
        Assert(VerticalPipeSupportCatalog.SupportType(VerticalPipeSupportKind.F7)==
            "F6_F7-[立管的耳轴]","F7 Python SupportType");
        Assert(VerticalPipeSupportCatalog.SupportType(VerticalPipeSupportKind.F10)==
            "F10-[小管径立管耳板]","F10 Python SupportType");
        var f7=VerticalPipeSupportCalculator.Calculate(new VerticalPipeSupportParameters {
            Kind=VerticalPipeSupportKind.F7,PipeDn=100,TrunnionDn=100,BuildPad=true,
            Material="C1",EndType="B",LengthMm=500,AzimuthDegrees=190},false,null,"");
        Assert(f7.Count==2 && f7.EndPlateThicknessMm==12 &&
            f7.Number=="F7-DN100-DN100-C1-500-B-10-5" &&
            f7.Specification=="F7 DN100×DN100 耳轴 L500",
            "F7 DN 编号/规格、端板与对称性");
        var f10=VerticalPipeSupportCalculator.Calculate(new VerticalPipeSupportParameters {
            Kind=VerticalPipeSupportKind.F10,PipeDn=25,F10Length="3",F10Height="D",
            F10Fixed=false,AzimuthDegrees=195},false,null,"");
        Assert(f10.EarWidthMm==200 && f10.EarHeightMm==200 &&
            f10.Number=="F10-3-D-C1-15-N" &&
            f10.Specification=="DN25 耳板 L200 H200","F10 尺寸与 DN 规格");
        Assert(VerticalPipeSupportCatalog.MatchDn(25,VerticalPipeSupportKind.F10)==25,
            "F10 nominal DN");
        VerticalPipeSupportCalculator.ValidateVertical(new PipeClampSelection {AxisZ=1000});
        bool rejected=false;
        try { VerticalPipeSupportCalculator.ValidateVertical(new PipeClampSelection {
            AxisX=1000,AxisZ=1000}); }
        catch(InvalidOperationException) { rejected=true; }
        Assert(rejected,"reject nonvertical axis");
        CheckSliding();
        Console.WriteLine("VerticalPipeSupport checks passed.");
    }
    private static void CheckSliding()
    {
        var bottom=new[]{10.0,20.0,100.0};
        var top=new[]{10.0,20.0,1100.0};
        var center=new[]{10.0,20.0,500.0};
        foreach(bool reverse in new[]{false,true})
        {
            var start=reverse?top:bottom;
            var end=reverse?bottom:top;
            foreach(double offset in new[]{0.0,150.0,-150.0,2000.0,-2000.0})
            {
                var actual=VerticalPipeSupportPositionCalculator.ShiftAlongAxis(center,start,end,offset);
                Assert(Math.Abs(actual[0]-10)<1e-9 && Math.Abs(actual[1]-20)<1e-9 &&
                    Math.Abs(actual[2]-Math.Max(100,Math.Min(1100,500+offset)))<1e-9,
                    "vertical slide direction and endpoint clamp, reverse="+reverse+", offset="+offset);
            }
        }
        // 允许范围内的斜立管：偏移为三维轴向距离，交换端点结果相同。
        bottom=new[]{10.0,20.0,100.0};top=new[]{40.0,60.0,1100.0};
        center=new[]{25.0,40.0,600.0};
        foreach(double offset in new[]{100.0,-100.0,2000.0,-2000.0})
        {
            var forward=VerticalPipeSupportPositionCalculator.ShiftAlongAxis(center,bottom,top,offset);
            var reverse=VerticalPipeSupportPositionCalculator.ShiftAlongAxis(center,top,bottom,offset);
            double t=Math.Max(0,Math.Min(1,0.5+offset/Math.Sqrt(1002500)));
            for(int i=0;i<3;i++)
                Assert(Math.Abs(forward[i]-reverse[i])<1e-9 &&
                    Math.Abs(forward[i]-(bottom[i]+t*(top[i]-bottom[i])))<1e-9,
                    "inclined slide distance and reversed endpoint equivalence");
        }
    }
}
