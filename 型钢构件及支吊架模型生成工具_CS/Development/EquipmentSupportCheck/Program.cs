using System;
using SteelSectionProbe;

namespace SteelSectionProbe
{
    internal enum G2MountFace {Wall,FloorTop,CeilingBottom}
    internal sealed class PipeClampSelection
    { internal double AxisX,AxisY,AxisZ; internal bool IsPipe; }
}
internal static class Program
{
    private static void Check(bool ok,string name){if(!ok)throw new Exception(name);}
    private static void Main()
    {
        var plate=N8Catalog.Resolve(4,"C",0,G2MountFace.Wall);
        Check(plate.E==480&&plate.F==380&&plate.G==33&&plate.BoltCount==8&&
            plate.Number=="N8-4-C","N8 cold table");
        Check(N8Catalog.HolePositions(plate).GetLength(0)==8,"N8 holes");
        Check(N8Catalog.Resolve(1,"N",0,G2MountFace.Wall).Number=="N8-1",
            "N8 uninsulated number");
        var n3=BracketCalculator.Calculate(new BracketParameters {
            Subtype='A',Type=1,HeightMm=390},1200);
        Check(n3.Number=="N3-1-A-390-1200"&&n3.BeamLength==1184&&
            n3.BraceRun==250,"N3 dimensions");
        Check(BracketCalculator.N3EndMargin(1200,16,390)==794,"N3 E calculation");
        Check(BracketCalculator.Calculate(new BracketParameters {
            Subtype='A',Type=1,HeightMm=390},556).BeamLength==540,
            "N3 E equals 150 accepted");
        bool shortEndRejected=false;
        try {BracketCalculator.Calculate(new BracketParameters {
            Subtype='A',Type=1,HeightMm=390},555);}
        catch(InvalidOperationException){shortEndRejected=true;}
        Check(shortEndRejected,"N3 E below 150 rejected");
        var n4=BracketCalculator.Calculate(new BracketParameters {
            Double=true,Subtype='A',Type=1,HeightMm=390,L2Mm=390,
            EquipmentOdMm=1000,PreweldMm=100,L3Mm=300,L4Mm=100},
            1300);
        double expected=1300-Math.Sqrt(500*500-390*390/4.0)-100;
        Check(Math.Abs(n4.L1-expected)<1e-9&&n4.BeamLength==n4.L1+300+50+58,
            "N4 L1 and beam length");
        Check(n4.Number.StartsWith("N4-1-A-390-"),"N4 number");
        bool rejected=false;
        try {BracketCalculator.Calculate(new BracketParameters {
            Double=true,Subtype='A',Type=1,HeightMm=390,L2Mm=390,
            EquipmentOdMm=1000,PreweldMm=100,L3Mm=300,L4Mm=100},2500);}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,"N4 maximum span");
        BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=1000});
        rejected=false;
        try {BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=1000,AxisZ=1000});}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,"horizontal axis");
        Console.WriteLine("N3/N4/N8 checks passed.");
    }
}
