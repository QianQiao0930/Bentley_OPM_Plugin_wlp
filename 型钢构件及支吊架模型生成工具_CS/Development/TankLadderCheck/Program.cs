using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;
using SteelSectionProbe;

internal static class Program
{
    private static int checks;
    private static void Check(bool pass, string name) { checks++; if (!pass) throw new Exception(name); }
    private static void Equal(double a, double b, string name) { Check(Math.Abs(a - b) < 1e-7, name); }
    private static void Point(TankLadderPoint a, double[] b, string name)
    { Equal(a.X, b[0], name + " X"); Equal(a.Y, b[1], name + " Y"); Equal(a.Z, b[2], name + " Z"); }
    private static void Reject(TankLadderParameters p)
    {
        bool rejected = false;
        try { TankLadderCalculator.Calculate(p); } catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "invalid ladder parameters rejected");
    }
    private static int Main()
    {
        try { Run(); Console.WriteLine("TankLadderCheck: " + checks + " checks passed."); return 0; }
        catch (Exception ex) { Console.Error.WriteLine(ex.Message); return 1; }
    }
    private static void Run()
    {
        var cases = new JavaScriptSerializer().Deserialize<List<ReferenceCase>>(File.ReadAllText(
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "python_reference.json")));
        foreach (var reference in cases)
        {
            var p = new TankLadderParameters { TankHeightMm = reference.TankHeightMm, WidthMm = reference.WidthMm,
                ReinforcementSpacingMm = reference.SpacingMm };
            var plan = TankLadderCalculator.Calculate(p);
            Check(plan.ComponentCount == reference.ComponentCount, "Python component count");
            Check(plan.RungCenters.Length == reference.Rungs.Length && plan.ReinforcementOrigins.Length == reference.Supports.Length,
                "Python member counts");
            for (int i = 0; i < 2; i++)
            {
                var leg = plan.Legs[i]; var expected = reference.Legs[i];
                Point(leg.Start, expected.Origin, "Python leg start"); Point(leg.ShortEnd, expected.ShortEnd, "Python short segment");
                Point(leg.VerticalStart, expected.VerticalStart, "Python arc endpoint"); Point(leg.Bottom, expected.Bottom, "Python leg bottom");
                Equal(plan.LegVerticalHeightMm, expected.VerticalHeight, "Python vertical drop");
                double dy = leg.ArcMiddle.Y - expected.ArcCenter[1], dz = leg.ArcMiddle.Z - expected.ArcCenter[2];
                Equal(Math.Sqrt(dy * dy + dz * dz), 150, "arc middle preserves exact R150");
                Equal(leg.Start.X, -plan.Legs[1 - i].Start.X, "mirrored leg");
                Equal(leg.Bottom.Z + p.TankHeightMm, 40, "original bottom clearance");
            }
            foreach (var angle in reference.Angles)
            {
                Equal(angle.Width, 50, "original angle width"); Equal(angle.Thickness, 5, "original angle thickness");
                if (angle.Axis == "X") { Point(plan.BottomAngleOrigin, angle.Origin, "bottom angle origin"); Equal(plan.BottomAngleLengthMm, angle.Length, "bottom angle length"); }
                else { Point(plan.PostOrigins[angle.Origin[0] < 0 ? 0 : 1], angle.Origin, "post origin"); Equal(angle.Length, 600, "post height"); }
            }
            for (int i = 0; i < reference.Supports.Length; i++) Point(plan.ReinforcementOrigins[i], reference.Supports[i].Origin, "Python support");
            for (int i = 0; i < reference.Rungs.Length; i++)
            {
                Point(plan.RungCenters[i], reference.Rungs[i].Center, "Python rung");
                Equal(plan.RungLengthMm, reference.Rungs[i].Length, "Python rung length");
                Equal(reference.Rungs[i].Diameter, 18, "rung diameter");
                Check(plan.RungCenters[i].Z <= 0, "rung remains below tank top");
            }
            p.WidthMm = 999;
            Equal(plan.Parameters.WidthMm, reference.WidthMm, "plan is an independent parameter snapshot");
        }
        var mode = ProfileLookup.Mode(RuntimeData.Families, "equal_angle", TankLadderCatalog.AngleProfile, "outer_corner");
        Check(mode.Segments.Length >= 6, "shared real angle profile exists");
        var standard = TankLadderCalculator.Calculate(new TankLadderParameters());
        Check(standard.ComponentCount == 17 && standard.RungCenters.Length == 6 && standard.ReinforcementOrigins.Length == 6,
            "default ladder has 17 members");
        Equal(standard.LegClearWidthMm, 400, "flat-bar leg clearance differs from angle spacing");
        foreach (double bad in new[] { 0d, -1, double.NaN, double.PositiveInfinity, 50001 }) Reject(new TankLadderParameters { TankHeightMm = bad });
        foreach (double bad in new[] { 0d, 20, double.NaN, double.NegativeInfinity, 5001 }) Reject(new TankLadderParameters { WidthMm = bad });
        foreach (double bad in new[] { 0d, -1, double.NaN, double.PositiveInfinity, 0.01 }) Reject(new TankLadderParameters { ReinforcementSpacingMm = bad });
        Reject(new TankLadderParameters { HeadingDegrees = double.NaN });
        var turned = TankLadderCalculator.Calculate(new TankLadderParameters { HeadingDegrees = -90, MergeComponents = false });
        Equal(turned.Parameters.HeadingDegrees, 270, "negative heading normalized"); Check(!turned.Parameters.MergeComponents, "unmerged cell option retained");
        PreviewChecks.Run(Check);
    }
    public sealed class ReferenceCase
    {
        public double TankHeightMm { get; set; } public double WidthMm { get; set; } public double SpacingMm { get; set; }
        public int ComponentCount { get; set; } public ReferenceAngle[] Angles { get; set; } public ReferenceLeg[] Legs { get; set; }
        public ReferenceSupport[] Supports { get; set; } public ReferenceRung[] Rungs { get; set; }
    }
    public sealed class ReferenceAngle { public double Width { get; set; } public double Thickness { get; set; } public double Length { get; set; } public double[] Origin { get; set; } public string Axis { get; set; } }
    public sealed class ReferenceLeg { public double[] Origin { get; set; } public double[] ShortEnd { get; set; } public double[] ArcCenter { get; set; } public double[] VerticalStart { get; set; } public double[] Bottom { get; set; } public double VerticalHeight { get; set; } }
    public sealed class ReferenceSupport { public double[] Origin { get; set; } }
    public sealed class ReferenceRung { public double[] Center { get; set; } public double Diameter { get; set; } public double Length { get; set; } }
}
