using System;
using System.Linq;
using SteelSectionProbe;

namespace SteelSectionProbe
{
    internal enum G2MountFace {Wall,FloorTop,CeilingBottom}
    internal sealed class PipeClampSelection
    { internal double AxisX,AxisY,AxisZ,StartX,StartY,StartZ,EndX,EndY,EndZ; internal bool IsPipe; }
}
internal static class Program
{
    private static int checks;
    private static void Check(bool ok,string name){checks++;if(!ok)throw new Exception(name);}
    private static void RejectN3(double d,double length,string name)
    {
        bool rejected=false;
        try {BracketCalculator.Calculate(new BracketParameters {
            ShowPreweld=true,PreweldMm=d,HeightMm=390},length);}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,name);
    }
    /// <summary>检查真实型钢轮廓的整个原始端面是否被两剪切面完全消除。</summary>
    private static void CheckBraceCuts()
    {
        for(int i=0;i<6;i++)
        {
            string spec=BracketCatalog.B[i];
            bool channel=spec.StartsWith("[");
            var family=ProfileLookup.Family(RuntimeData.Families,channel?"parallel_channel":"hot_rolled_h");
            var profile=family.Profiles.Single(p=>channel?p.Name==spec.Substring(1):p.Name.StartsWith(spec+"xr"));
            double height=profile.Dimensions["H"];
            var mode=ProfileLookup.Mode(RuntimeData.Families,family.Id,profile.Name,"geometric_center");
            double[] ordinates=mode.Segments.SelectMany(s=>s.IsArc?new[]{s.Y0,s.Ym,s.Y1}:new[]{s.Y0,s.Y1})
                .Concat(new[]{-height/2,height/2}).ToArray();
            Check(ordinates.All(y=>Math.Abs(y)<=height/2+1e-6),"brace height bounds actual profile "+spec);
            foreach(bool doubleBracket in new[]{false,true})
            {
                foreach(int type in new[]{1,2})
                {
                    var plan=BracketCalculator.Calculate(new BracketParameters {Double=doubleBracket,
                        Subtype=(char)('A'+i),Type=type,EquipmentOdMm=2000,PreweldMm=100},2000);
                    double vr=plan.BraceRun,vz=plan.BraceContactZMm-plan.BracePlateCenterZMm;
                    double length=Math.Sqrt(vr*vr+vz*vz),ur=vr/length,uz=vz/length;
                    double nr=-uz,nz=ur;
                    double overrun=BracketCalculator.BraceCutOverrunMm(height,vr,vz);
                    // Original root-face cap must lie entirely behind the plate plane.
                    // Original far cap must lie entirely across the beam-contact plane.
                    foreach(double y in ordinates)
                    {
                        Check(-overrun*ur+y*nr<-1e-6,"root cap removed "+spec+doubleBracket+type);
                        double beamCapZ=overrun*uz+y*nz;
                        Check(type==1?beamCapZ>1e-6:beamCapZ<-1e-6,
                            "beam cap removed "+spec+doubleBracket+type);
                    }
                    double r0=doubleBracket?0:plan.PlateThickness;
                    // Ideal cut stations for both outer edges must stay within the sweep.
                    foreach(double y in new[]{-height/2,height/2})
                    {
                        double rootStation=-y*nr/ur;
                        double beamStation=length-y*nz/uz;
                        Check(rootStation>-overrun&&rootStation<length+overrun,
                            "full root edge available "+spec+doubleBracket+type);
                        Check(beamStation>-overrun&&beamStation<length+overrun,
                            "full beam edge available "+spec+doubleBracket+type);
                        Check(Math.Abs((r0+rootStation*ur+y*nr)-r0)<1e-8,
                            "root edge lies on plate face "+spec+doubleBracket+type);
                        Check(Math.Abs(plan.BracePlateCenterZMm+beamStation*uz+y*nz-
                            plan.BraceContactZMm)<1e-8,"beam edge lies on contact face "+spec+doubleBracket+type);
                    }
                }
            }
            Console.WriteLine(spec+": height="+height+" mm, end extension="+
                BracketCalculator.BraceCutOverrunMm(height,1,1)+" mm.");
        }
        Check(-50/Math.Sqrt(2)+100/Math.Sqrt(2)>0,"old 50mm extension leaves H200 root cap");
        foreach(double slope in new[]{0.5,1,2})
        {
            double extension=BracketCalculator.BraceCutOverrunMm(200,1,slope);
            Check(extension>100*slope&&extension>100/slope,"both cutting planes covered "+slope);
        }
        foreach(double invalid in new[]{0d,-1,double.NaN,double.PositiveInfinity})
        {
            bool rejected=false;
            try {BracketCalculator.BraceCutOverrunMm(invalid,1,1);}
            catch(InvalidOperationException){rejected=true;}
            Check(rejected,"invalid section height rejected "+invalid);
        }
    }
    private static int Main()
    {
        try {Run();return 0;}
        catch(Exception ex){Console.Error.WriteLine(ex.GetType().Name+": "+ex.Message);return 1;}
    }
    private static void Run()
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
            n3.BraceRun==320,"N3 dimensions");
        Check(n3.BeamCenterZMm==-70&&n3.BracePlateCenterZMm==-460,
            "N3 type1 H390 is plate centre distance");
        Check(n3.BraceContactZMm==-140&&n3.EndOverhang==864,
            "N3 type1 brace reaches beam underside at 45 degrees");
        var n3Upper=BracketCalculator.Calculate(new BracketParameters {Type=2,HeightMm=390},1200);
        Check(n3Upper.BeamCenterZMm==-70&&n3Upper.BracePlateCenterZMm==320&&n3Upper.BraceRun==320,
            "N3 drawing type2 H390 is plate centre distance");
        Check(n3Upper.BraceContactZMm==0&&n3Upper.EndOverhang==864,
            "N3 type2 brace reaches beam top at 45 degrees");
        Check(BracketCalculator.N3EndMargin(1200,16,390)==794,"N3 E calculation");
        Check(BracketCalculator.Calculate(new BracketParameters {
            Subtype='A',Type=1,HeightMm=390},556).BeamLength==540,
            "N3 E equals 150 accepted");
        bool shortEndRejected=false;
        try {BracketCalculator.Calculate(new BracketParameters {
            Subtype='A',Type=1,HeightMm=390},555);}
        catch(InvalidOperationException){shortEndRejected=true;}
        Check(shortEndRejected,"N3 E below 150 rejected");
        var occupied=BracketCalculator.Calculate(new BracketParameters {
            ShowPreweld=true,PreweldMm=100,Subtype='A',Type=1,HeightMm=390},1200);
        Check(occupied.L==1100&&occupied.BeamLength==1084&&occupied.RootOffsetMm==100,
            "N3 subtracts preweld from support and material lengths");
        Check(occupied.Number=="N3-1-A-390-1100"&&occupied.Specification.Contains("D=100"),
            "N3 effective length number and preweld specification");
        Check(occupied.BraceRun==n3.BraceRun&&occupied.VerticalLoad==n3.VerticalLoad,
            "N3 brace and load unchanged");
        Check(occupied.RootOffsetMm+occupied.PlateThickness+occupied.BeamLength==1200,
            "N3 keeps the original beam endpoint");
        var disabled=BracketCalculator.Calculate(new BracketParameters {
            ShowPreweld=false,PreweldMm=double.NaN,HeightMm=390},1200);
        Check(disabled.Number==n3.Number&&disabled.BeamLength==n3.BeamLength&&
            disabled.Preweld==0&&disabled.RootOffsetMm==0,"N3 unchecked ignores saved D");
        Check(BracketCalculator.Calculate(new BracketParameters {
            ShowPreweld=true,PreweldMm=100,HeightMm=390},656).BeamLength==540,
            "N3 preweld E equals 150 accepted");
        RejectN3(100,655,"N3 preweld E below 150 rejected");
        foreach(double d in new[]{-100d,0,16,double.NaN,double.PositiveInfinity,double.NegativeInfinity,1200,1300})
            RejectN3(d,1200,"N3 invalid D "+d);
        foreach(char subtype in "ABCDEF")
        {
            int i=subtype-'A';
            foreach(int type in new[]{1,2})
            {
                var p=new BracketParameters {Subtype=subtype,Type=type,HeightMm=BracketCatalog.MinH[i],
                    ShowPreweld=true,PreweldMm=100,Reverse=true};
                var plan=BracketCalculator.Calculate(p,1600);
                Check(plan.Reverse&&plan.L==1500&&plan.BeamLength==1500-plan.PlateThickness,
                    "N3 all subtypes/types reverse dimensions "+subtype+type);
                var connection=N8Catalog.Resolve(plan.PlateType,"N",0,G2MountFace.Wall);
                double centreDistance=Math.Abs(plan.BracePlateCenterZMm-plan.BeamCenterZMm);
                Check(centreDistance==plan.H,"N3 centre distance equals H "+subtype+type);
                Check(centreDistance-connection.E==20,"N3 all MIN.H plate gaps are 20 mm "+subtype+type);
                Check(Math.Abs(plan.BraceContactZMm-plan.BracePlateCenterZMm)==plan.BraceRun,
                    "N3 brace remains 45 degrees "+subtype+type);
                var noPlaceholder=BracketCalculator.Calculate(new BracketParameters {
                    Subtype=subtype,Type=type,HeightMm=plan.H},1600);
                Check(noPlaceholder.BracePlateCenterZMm==plan.BracePlateCenterZMm&&
                    noPlaceholder.BeamCenterZMm==plan.BeamCenterZMm,
                    "N3 preweld toggle keeps plate heights "+subtype+type);
                // In either direction: placeholder begins at the chosen root; beam ends at the other end.
                foreach(double direction in new[]{1d,-1})
                {
                    double root=direction>0?300:1900;
                    double frameOrigin=root+direction*plan.RootOffsetMm;
                    Check(Math.Abs(frameOrigin-direction*plan.Preweld-root)<1e-9,
                        "N3 placeholder begins at root "+subtype+type+direction);
                    Check(Math.Abs(frameOrigin+direction*(plan.PlateThickness+plan.BeamLength)-
                        (root+direction*1600))<1e-9,"N3 preserves endpoint "+subtype+type+direction);
                }
            }
        }
        var serializer=new System.Web.Script.Serialization.JavaScriptSerializer();
        var saved=serializer.Deserialize<BracketLastChoice.Data>(serializer.Serialize(new BracketLastChoice.Data {
            N3Preweld="150",N3ShowPreweld=true,N4Preweld="250",N4ShowPreweld=false}));
        Check(saved.N3Preweld=="150"&&saved.N3ShowPreweld&&saved.N4Preweld=="250"&&!saved.N4ShowPreweld,
            "N3/N4 preweld preferences independent");
        var legacy=serializer.Deserialize<BracketLastChoice.Data>("{\"N3Height\":\"390\"}");
        Check(legacy.N3Preweld=="100"&&!legacy.N3ShowPreweld,"old preferences retain unchecked N3 default");
        var n4=BracketCalculator.Calculate(new BracketParameters {
            Double=true,Subtype='A',Type=1,HeightMm=390,L2Mm=390,
            EquipmentOdMm=1000,PreweldMm=100,L3Mm=300,L4Mm=100},
            1300);
        double expected=1300-Math.Sqrt(500*500-390*390/4.0)-100;
        Check(Math.Abs(n4.L1-expected)<1e-9&&n4.BeamLength==n4.L1+300+50+58,
            "N4 L1 and beam length");
        Check(n4.Number.StartsWith("N4-1-A-390-"),"N4 number");
        Check(n4.BeamCenterZMm==-70&&n4.BracePlateCenterZMm==-460&&n4.BraceRun==320,
            "N4 H390 is plate centre distance");
        Check(Math.Abs(n4.RootOffsetMm-(1300-expected))<1e-9,"N4 placement unchanged");
        var n4Shown=BracketCalculator.Calculate(new BracketParameters {
            Double=true,ShowPreweld=true,Subtype='A',Type=1,HeightMm=390,L2Mm=390,
            EquipmentOdMm=1000,PreweldMm=100,L3Mm=300,L4Mm=100},1300);
        Check(n4Shown.L1==n4.L1&&n4Shown.Number==n4.Number&&n4Shown.Preweld==100,
            "N4 display toggle keeps deduction behavior");
        foreach(char subtype in "ABCDEF")
        {
            int i=subtype-'A';
            foreach(int type in new[]{1,2})
            foreach(bool show in new[]{false,true})
            foreach(bool reverse in new[]{false,true})
            {
                var plan=BracketCalculator.Calculate(new BracketParameters {Double=true,Subtype=subtype,
                    Type=type,HeightMm=BracketCatalog.MinH[i],L2Mm=BracketCatalog.MinL2[i],
                    EquipmentOdMm=2000,PreweldMm=100,ShowPreweld=show,Reverse=reverse},2000);
                double plateSize=N8Catalog.Resolve(plan.PlateType,"N",0,G2MountFace.Wall).E;
                Check(Math.Abs(plan.BracePlateCenterZMm-plan.BeamCenterZMm)==plan.H,
                    "N4 H centre distance "+subtype+type+show+reverse);
                Check(plan.H-plateSize==20&&plan.L2-plateSize==20,
                    "N4 minimum vertical and lateral gaps 20 mm "+subtype+type+show+reverse);
                Check(plan.BraceRun==plan.H-plan.SectionAHeight/2,
                    "N4 brace projection matches plate centres "+subtype+type);
                double[,] centres={{-plan.L2/2,plan.BeamCenterZMm},{plan.L2/2,plan.BeamCenterZMm},
                    {-plan.L2/2,plan.BracePlateCenterZMm},{plan.L2/2,plan.BracePlateCenterZMm}};
                for(int a=0;a<4;a++)for(int b=a+1;b<4;b++)
                {
                    double horizontalGap=Math.Abs(centres[a,0]-centres[b,0])-plateSize;
                    double verticalGap=Math.Abs(centres[a,1]-centres[b,1])-plateSize;
                    Check(Math.Max(horizontalGap,verticalGap)>=20,
                        "N4 four N8 plates have clear separation "+subtype+type+a+b);
                }
            }
        }
        BracketCalculator.ValidateN8PlateSpacing(390,370,"H");
        Check(true,"N8 exact 20 mm gap accepted");
        foreach(string dimension in new[]{"H","L2"})
        foreach(double distance in new[]{389.999,370,360,double.NaN,double.PositiveInfinity})
        {
            bool spacingRejected=false;
            try {BracketCalculator.ValidateN8PlateSpacing(distance,370,dimension);}
            catch(InvalidOperationException){spacingRejected=true;}
            Check(spacingRejected,"N8 inadequate spacing rejected "+dimension+distance);
        }
        bool rejected=false;
        try {BracketCalculator.Calculate(new BracketParameters {
            Double=true,Subtype='A',Type=1,HeightMm=390,L2Mm=390,
            EquipmentOdMm=1000,PreweldMm=100,L3Mm=300,L4Mm=100},2500);}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,"N4 maximum span");
        BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=1000});
        BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=600,AxisY=800});
        Check(true,"diagonal horizontal line accepted");
        rejected=false;
        try {BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=1000,IsPipe=true});}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,"equipment brackets require auxiliary line");
        rejected=false;
        try {BracketCalculator.ValidateHorizontal(new PipeClampSelection {AxisX=1000,AxisZ=1000});}
        catch(InvalidOperationException){rejected=true;}
        Check(rejected,"horizontal axis");
        CheckBraceCuts();
        ChannelOrientationChecks.Run(Check);
        Console.WriteLine("N3/N4/N8 checks passed: "+checks+".");
    }
}
