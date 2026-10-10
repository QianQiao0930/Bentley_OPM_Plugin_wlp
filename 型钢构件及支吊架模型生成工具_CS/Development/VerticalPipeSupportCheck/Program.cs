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
        Console.WriteLine("VerticalPipeSupport checks passed.");
    }
}
