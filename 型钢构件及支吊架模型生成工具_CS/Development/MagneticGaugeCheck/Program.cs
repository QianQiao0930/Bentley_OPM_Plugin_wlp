using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Web.Script.Serialization;
using SteelSectionProbe;
internal static class Program
{
    private static int checks;
    private static void Check(bool v,string label){checks++;if(!v)throw new Exception(label);}
    private static void Equal(double a,double b,string label){Check(Math.Abs(a-b)<1e-7,label+": "+a+" vs "+b);}
    private static double Number(object v){return Convert.ToDouble(v,System.Globalization.CultureInfo.InvariantCulture);}
    private static void Point(MagneticGaugePoint p,object v,string label)
    {var a=(object[])v;Equal(p.X,Number(a[0]),label+" X");Equal(p.Y,Number(a[1]),label+" Y");Equal(p.Z,Number(a[2]),label+" Z");}
    private static int Main()
    {
        try{Run();Console.WriteLine("MagneticGaugeCheck: "+checks+" checks passed.");return 0;}catch(Exception ex){Console.Error.WriteLine(ex);return 1;}
    }
    private static void Run()
    {
        var cases=new JavaScriptSerializer{MaxJsonLength=10000000}.Deserialize<List<ReferenceCase>>(File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"python_reference.json")));
        foreach(var c in cases)
        {
            var input=new MagneticGaugeParameters{ConnectionSpacingMm=c.L1,HeadingDegrees=450};var plan=MagneticGaugeCalculator.Calculate(input);
            Check(plan.Parts.Length==c.Parts.Length,"Python part count");Equal(plan.Parameters.HeadingDegrees,90,"heading normalization");
            for(int i=0;i<c.Parts.Length;i++)
            {
                var r=c.Parts[i];var p=plan.Parts[i];string type=(string)r[0];
                Check(p.Kind.ToString().ToLowerInvariant()==type,"part kind");Point(p.Start,r[1],"start");
                if(type=="cylinder"){Point(p.End,r[2],"end");Equal(p.RadiusMm,Number(r[3]),"cylinder radius");Check(p.RadiusMm>0,"positive radius");}
                else if(type=="box"){Point(p.Size,r[2],"size");Check(p.Size.X>0&&p.Size.Y>0&&p.Size.Z>0,"positive box dimensions");}
                else{Equal(p.RadiusMm,Number(r[2]),"wheel major radius");Equal(p.TubeRadiusMm,Number(r[3]),"wheel tube radius");Check(p.RadiusMm>p.TubeRadiusMm,"wheel opening");}
                var color=(object[])r[r.Length-1];var rgb=MagneticGaugeCatalog.Rgb(p.Color);for(int j=0;j<3;j++)Equal(rgb[j],Number(color[j]),"RGB");
            }
            Check(plan.FlipCount%2==0,"even flips");Check(plan.Parts.Count(p=>p.Color==MagneticGaugeColor.Red)==plan.FlipCount/2,"lower half red");
            var flips=plan.Parts.Where(p=>p.Kind==MagneticGaugeKind.Box&&p.Start.X==-20).ToArray();
            Check(flips.Length==plan.FlipCount,"flip count");Equal(flips[plan.FlipCount/2].Start.Z-.4,c.L1/2,"exact 50 percent boundary");
            Equal(flips.Last().Start.Z+flips.Last().Size.Z,c.L1-.4,"last flip margin");
            Check(plan.TickCount==(int)Math.Floor(c.L1/10)+1,"tick count");Check(plan.Parts.Count(p=>p.Kind==MagneticGaugeKind.Torus)==2,"two circular handwheels");
            Check(plan.CellName.StartsWith("MAGNETIC_LEVEL_GAUGE_L1_"),"cell prefix");
            input.ConnectionSpacingMm=999;Equal(plan.Parameters.ConnectionSpacingMm,c.L1,"parameter snapshot");
        }
        foreach(double l in new[]{0d,349.999,6000.001,double.NaN,double.PositiveInfinity,double.NegativeInfinity})Reject(()=>MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters{ConnectionSpacingMm=l}));
        Reject(()=>MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters{HeadingDegrees=double.NaN}));Reject(()=>MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters{HeadingDegrees=double.PositiveInfinity}));
        PreviewChecks.Run(Check);BuilderChecks.Run(Check);
    }
    private static void Reject(Action a){bool rejected=false;try{a();}catch(InvalidOperationException){rejected=true;}Check(rejected,"invalid inputs rejected");}
#pragma warning disable 0649
    public sealed class ReferenceCase {public double L1;public object[][] Parts;}
#pragma warning restore 0649
}
