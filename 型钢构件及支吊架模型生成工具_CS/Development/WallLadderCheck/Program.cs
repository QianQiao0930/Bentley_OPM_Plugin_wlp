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
    private static void Point(WallLadderPoint p,double[] r,string label){Equal(p.X,r[0],label+" X");Equal(p.Y,r[1],label+" Y");Equal(p.Z,r.Length>2?r[2]:0,label+" Z");}
    private static int Main()
    {
        try{Run();Console.WriteLine("WallLadderCheck: "+checks+" checks passed.");return 0;}catch(Exception ex){Console.Error.WriteLine(ex);return 1;}
    }
    private static void Run()
    {
        var cases=new JavaScriptSerializer { MaxJsonLength=10000000 }.Deserialize<List<ReferenceCase>>(File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"python_reference.json")));
        foreach(var c in cases)
        {
            var input=new WallLadderParameters { WidthMm=c.Width,StandoffMm=c.Standoff,FirstRungMm=c.First,BracketSpacingMm=c.Spacing,CageEnabled=c.Cage };
            var p=WallLadderCalculator.Calculate(c.Height,input);var r=c.Layout;
            Equal(p.StileThicknessMm,r.stile_flat[1],"stile selection");Equal(p.RungLengthMm,r.rung_length,"rung protrusion");
            Levels(p.RungLevels,r.rung_levels,"rungs");Levels(p.BracketLevels,r.bracket_levels,"brackets");
            int cursor=0;
            for(int i=0;i<2+p.RungLevels.Length;i++)Part(p.LadderParts[cursor++],r.primitives[i]);
            // Original angle was two overlapping rectangular legs. Catalog replacement retains the L's extents and placement.
            for(int i=2+p.RungLevels.Length;i<r.ladder_primitive_count;i+=3)
            {
                var angle=p.LadderParts[cursor++];var vertical=r.primitives[i];var horizontal=r.primitives[i+1];
                Check(angle.Kind==WallLadderPartKind.Angle,"catalog angle");Equal(angle.Center.X,0,"angle wall start");Equal(angle.Size.Z,vertical.size[0],"angle length");
                Equal(angle.Center.Y+angle.U.Y*5,vertical.center[1],"vertical leg t");Equal(angle.Center.Z+37.5,vertical.center[2],"vertical leg z");
                Equal(angle.Center.Y+angle.U.Y*37.5,horizontal.center[1],"horizontal leg t");Equal(angle.Center.Z+5,horizontal.center[2],"horizontal leg z");
                Part(p.LadderParts[cursor++],r.primitives[i+2]);
            }
            Check(cursor==p.LadderParts.Length,"ladder grouped part count");
            if(c.Cage)
            {
                Levels(p.HoopLevels,r.cage.hoop_levels,"hoop levels");Levels(p.HoopRungs,r.cage.hoop_rungs,"snapped rungs");
                Check(p.CageParts.Length==r.cage.primitives.Length,"cage part count");
                for(int i=0;i<p.CageParts.Length;i++)Part(p.CageParts[i],r.cage.primitives[i]);
                for(int i=0;i<11;i++)
                {
                    var station=r.cage.stations[i];Equal(p.CageStations[i].X,Convert.ToDouble(station[0]),"station n");Equal(p.CageStations[i].Y,Convert.ToDouble(station[1]),"station t");
                    var tangent=(object[])station[2];Equal(p.CageTangents[i].X,Convert.ToDouble(tangent[0]),"station tangent n");Equal(p.CageTangents[i].Y,Convert.ToDouble(tangent[1]),"station tangent t");
                }
                foreach(var part in p.CageParts.Where(x=>x.Kind==WallLadderPartKind.Sweep))
                {
                    Check(part.Path.Count(s=>s.IsArc)==2,"two true quarter arcs per hoop");
                    for(int i=1;i<part.Path.Length;i++)Check((part.Path[i].Start-part.Path[i-1].End).Length<1e-8,"path continuity");
                    foreach(var arc in part.Path.Where(s=>s.IsArc))
                    {Equal(arc.RadiusMm,355,"R355");Check((arc.Middle-(arc.Start+arc.End)*.5).Length>100,"arc midpoint differs from chord");var back=arc.Reversed();Check((back.Middle-arc.Middle).Length==0,"reverse preserves arc");}
                }
                for(int i=1;i<p.HoopLevels.Length;i++)Check(p.HoopLevels[i]-p.HoopLevels[i-1]<=1500+1e-8,"max hoop gap");
                Equal(p.HoopLevels.Last()+25,c.Height+1200,"top hoop height");
            }
            else Check(p.CageParts.Length==0,"cage off");
            input.WidthMm=999;Check(p.Parameters.WidthMm==c.Width,"parameter snapshot independent");
        }
        var mode=ProfileLookup.Mode(RuntimeData.Families,"equal_angle",WallLadderCatalog.AngleProfile,"outer_corner");
        Check(mode.Segments.Any(s=>s.IsArc),"catalog angle contains genuine fillets");
        Equal(mode.Segments.SelectMany(s=>new[]{s.X0,s.X1}).Max(),75,"catalog width");
        Reject(()=>WallLadderCalculator.Calculate(6000.01,new WallLadderParameters()));Reject(()=>WallLadderCalculator.Calculate(double.NaN,new WallLadderParameters()));
        foreach(var p in new[]{new WallLadderParameters{WidthMm=0},new WallLadderParameters{WidthMm=120},new WallLadderParameters{WidthMm=830},new WallLadderParameters{StandoffMm=105},
            new WallLadderParameters{BracketSpacingMm=.01},new WallLadderParameters{FirstRungMm=-1},new WallLadderParameters{HeadingDegrees=double.PositiveInfinity}})
            Reject(()=>WallLadderCalculator.Calculate(3000,p));
        var selection=WallLadderSelection.FromPoints(new[]{new WallLadderPoint(100,200,3400),new WallLadderPoint(100,200,400)});
        Equal(selection.HeightMm,3000,"reversed line height");Equal(selection.BasePointMm.Z,400,"low endpoint");
        Reject(()=>WallLadderSelection.FromPoints(new[]{new WallLadderPoint(0,0,0),new WallLadderPoint(6,0,3000)}));
        Reject(()=>WallLadderSelection.FromPoints(new[]{new WallLadderPoint(0,0,0),new WallLadderPoint(0,0,0)}));
        Reject(()=>WallLadderSelection.FromPoints(new[]{new WallLadderPoint(0,0,0),new WallLadderPoint(0,0,double.NaN)}));
        PreviewChecks.Run(Check);
        BuilderChecks.Run(Check);
    }
    private static void Levels(double[] a,double[] b,string label){Check(a.Length==b.Length,label+" count");for(int i=0;i<a.Length;i++)Equal(a[i],b[i],label);}
    private static void Part(WallLadderPart p,ReferencePart r)
    {
        if(r.type=="box"){Check(p.Kind==WallLadderPartKind.Box,"box kind");Point(p.Center,r.center,"box center");Point(p.Size,r.size,"box size");Axis(p.U,r.axes[0]);Axis(p.V,r.axes[1]);Axis(p.W,r.axes[2]);}
        else if(r.type=="cylinder"){Check(p.Kind==WallLadderPartKind.Cylinder,"rung kind");Point(p.Center,r.center,"rung center");Equal(p.Size.Z,r.length,"rung length");Equal(p.Size.X,r.diameter,"rung diameter");}
        else
        {
            Check(p.Kind==WallLadderPartKind.Sweep,"sweep kind");Check(p.Path.Length==r.path.Length,"segment count");Equal(p.Size.X,r.flat_width,"flat width");Equal(p.Size.Y,r.flat_thickness,"flat thickness");
            for(int i=0;i<p.Path.Length;i++)
            {
                var a=p.Path[i];var b=r.path[i];double z=r.type=="sweep"?r.level:b.type=="arc"?b.center[2]:b.start[2];
                if(b.type=="line"){Check(!a.IsArc,"straight segment");Point(a.Start,b.start.Length==3?b.start:To3(b.start,z),"line start");Point(a.End,b.end.Length==3?b.end:To3(b.end,z),"line end");}
                else {Check(a.IsArc,"true arc descriptor");Equal(a.RadiusMm,b.radius,"radius");Point(a.Start,Arc(b,b.start_angle,z),"arc start");Point(a.Middle,Arc(b,(b.start_angle+b.end_angle)/2,z),"arc middle");Point(a.End,Arc(b,b.end_angle,z),"arc end");}
            }
        }
    }
    private static double[] Arc(ReferenceSegment s,double angle,double z){return new[]{s.center[0]+s.radius*Math.Cos(angle*Math.PI/180),s.center[1]+s.radius*Math.Sin(angle*Math.PI/180),z};}
    private static double[] To3(double[] p,double z){return new[]{p[0],p[1],z};}
    private static void Axis(WallLadderPoint a,object spec)
    {
        if(spec is string){string s=(string)spec;Point(a,s=="n"?new[]{1d,0,0}:s=="t"?new[]{0d,1,0}:new[]{0d,0,1},"axis");}
        else Point(a,((object[])spec).Select(Convert.ToDouble).ToArray(),"axis");
    }
    private static void Reject(Action action){bool v=false;try{action();}catch(InvalidOperationException){v=true;}Check(v,"invalid input rejected");}
    // JSON serializer populates these fields via reflection.
#pragma warning disable 0649
    public sealed class ReferenceCase{public double Height,Width,Standoff,First,Spacing;public bool Cage;public ReferenceLayout Layout;}
    public sealed class ReferenceLayout{public double[] stile_flat,rung_levels,bracket_levels;public double rung_length;public int ladder_primitive_count;public ReferencePart[] primitives;public ReferenceCage cage;}
    public sealed class ReferenceCage{public double[] hoop_rungs,hoop_levels;public object[][] stations;public ReferencePart[] primitives;}
    public sealed class ReferencePart{public string type;public double[] center,size;public object[] axes;public double length,diameter,level,flat_width,flat_thickness;public ReferenceSegment[] path;}
    public sealed class ReferenceSegment{public string type;public double[] start,end,center;public double radius,start_angle,end_angle;}
#pragma warning restore 0649
}
