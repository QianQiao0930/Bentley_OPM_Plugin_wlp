using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class WallLadderCalculator
    {
        private static readonly WallLadderPoint N=new WallLadderPoint(1,0,0), T=new WallLadderPoint(0,1,0), Z=new WallLadderPoint(0,0,1);
        internal static WallLadderParameters Snapshot(WallLadderParameters p)
        {
            if(p==null)throw new ArgumentNullException("p");
            Positive(p.WidthMm,5000,"梯宽"); Positive(p.StandoffMm,5000,"距墙"); Positive(p.BracketSpacingMm,6000,"支架间距");
            if(!Finite(p.FirstRungMm)||p.FirstRungMm<0||p.FirstRungMm>6000)throw new InvalidOperationException("最低横担离地须在0～6000 mm之间。");
            if(!Finite(p.HeadingDegrees))throw new InvalidOperationException("出梯角度无效。");
            if(p.CageEnabled&&(p.WidthMm<=120||p.WidthMm>=830||p.StandoffMm<=105))
                throw new InvalidOperationException("护笼需120<梯宽<830 mm，立柱距墙大于105 mm，避免端头回环退化。");
            return new WallLadderParameters { WidthMm=p.WidthMm,StandoffMm=p.StandoffMm,FirstRungMm=p.FirstRungMm,
                BracketSpacingMm=p.BracketSpacingMm,HeadingDegrees=p.HeadingDegrees%360,CageEnabled=p.CageEnabled };
        }
        internal static WallLadderPlan Calculate(double height,WallLadderParameters input)
        {
            Positive(height,WallLadderCatalog.MaxHeightMm,"竖直线高度");
            var p=Snapshot(input); double thick=height<=4500+1e-6?12:height<=5500+1e-6?16:20;
            var rungs=RungLevels(height,p.FirstRungMm); var brackets=new List<double>();
            for(double z=p.BracketSpacingMm;z<height-1e-9;z+=p.BracketSpacingMm)
            { if(brackets.Count>WallLadderCatalog.MaxParts)throw new InvalidOperationException("支架过密，请增大支架间距。"); brackets.Add(z); }
            var ladder=new List<WallLadderPart>(); double stileHeight=height+1200;
            foreach(double side in new[]{-1d,1d}) ladder.Add(Box(new WallLadderPoint(p.StandoffMm,side*p.WidthMm/2,stileHeight/2),N,T,Z,new WallLadderPoint(75,thick,stileHeight)));
            double rungLength=p.WidthMm+thick+20;
            foreach(double z in rungs)ladder.Add(new WallLadderPart { Kind=WallLadderPartKind.Cylinder,Center=new WallLadderPoint(p.StandoffMm,0,z),W=T,Size=new WallLadderPoint(24,0,rungLength) });
            foreach(double z in brackets)foreach(double side in new[]{-1d,1d})
            {
                double edge=side*(p.WidthMm+thick)/2;
                // Catalog outer-corner axes: outward across width, then up; axis N gives the original wall-to-stile extent.
                ladder.Add(new WallLadderPart { Kind=WallLadderPartKind.Angle,Center=new WallLadderPoint(0,edge,z-37.5),U=T*side,V=Z,W=N,Size=new WallLadderPoint(75,10,p.StandoffMm+37.5) });
                ladder.Add(Box(new WallLadderPoint(5,edge+side*37.5,z),N,T,Z,new WallLadderPoint(10,100,100)));
            }
            var plan=new WallLadderPlan { Parameters=p,HeightMm=height,StileWidthMm=75,StileThicknessMm=thick,RungLengthMm=rungLength,
                RungLevels=rungs,BracketLevels=brackets.ToArray(),LadderParts=ladder.ToArray(),CageParts=new WallLadderPart[0],
                HoopLevels=new double[0],HoopRungs=new double[0],CageStations=new WallLadderPoint[0],CageTangents=new WallLadderPoint[0] };
            if(p.CageEnabled) Cage(plan);
            if(plan.LadderParts.Length+plan.CageParts.Length>WallLadderCatalog.MaxParts)throw new InvalidOperationException("构件超过500个，请调整尺寸或间距。");
            return plan;
        }
        internal static double[] RungLevels(double height,double first)
        {
            double available=height-50-first;
            if(available < -1e-9)return new double[0];
            if(available<250-1e-9)return new[]{first};
            int lo=Math.Max(1,(int)Math.Ceiling(available/300-1e-9)),hi=(int)Math.Floor(available/250+1e-9);
            int n=lo<=hi?lo:(Math.Max(0,250-available/lo)<=Math.Max(0,available/hi-300)?lo:hi);
            n=Math.Max(1,n);return Enumerable.Range(0,n+1).Select(i=>first+i*available/n).ToArray();
        }
        private static void Cage(WallLadderPlan plan)
        {
            var p=plan.Parameters; var hr=new List<double>(); var r=plan.RungLevels;
            if(r.Length>0)
            {
                int index=0;for(int i=1;i<r.Length;i++)if(Math.Abs(r[i]-2000)<Math.Abs(r[index]-2000))index=i;
                hr.Add(r[index]);
                while(true){int advance=index;for(int i=index+1;i<r.Length&&r[i]-hr[hr.Count-1]<=1500+1e-9;i++)advance=i;
                    if(advance==index)break;index=advance;hr.Add(r[index]);}
            }
            var levels=hr.Select(z=>z-37).ToList(); double top=plan.HeightMm+1200-25;
            double next=levels.Count>0?levels[levels.Count-1]+1500:2000-37;
            while(next<top-1e-9){levels.Add(next);next+=1500;}levels.Add(top);
            var parts=new List<WallLadderPart>();
            for(int i=0;i<levels.Count-1;i++)parts.Add(new WallLadderPart { Kind=WallLadderPartKind.Sweep,Path=HoopPath(p,levels[i]),Size=new WallLadderPoint(50,5,0) });
            parts.Add(new WallLadderPart { Kind=WallLadderPartKind.Sweep,Path=TopPath(p,plan.HeightMm),Size=new WallLadderPoint(50,5,0),Spatial=true });
            var path=HoopPath(p,0); var outer=path.Skip(3).Take(4).ToArray(); double total=outer.Sum(Length);
            var stations=new WallLadderPoint[11]; var tangents=new WallLadderPoint[11];
            for(int i=0;i<11;i++) PointAt(outer,total*(i+.5)/11,out stations[i],out tangents[i]);
            for(int h=0;h<levels.Count-1;h++)for(int i=0;i<11;i++)
            {
                var tangent=tangents[i]; var radial=new WallLadderPoint(tangent.Y,-tangent.X,0);
                var center=stations[i]+radial*5+Z*((levels[h]+levels[h+1])/2);
                parts.Add(Box(center,radial,tangent,Z,new WallLadderPoint(5,30,levels[h+1]-levels[h])));
            }
            plan.HoopRungs=hr.ToArray();plan.HoopLevels=levels.ToArray();plan.CageParts=parts.ToArray();plan.CageStations=stations;plan.CageTangents=tangents;
        }
        internal static WallLadderSegment[] HoopPath(WallLadderParameters p,double z)
        {
            double n=p.StandoffMm,h=n-105,c=n+410,t=p.WidthMm/2-60,B=355;
            var points=new[]{new WallLadderPoint(n,p.WidthMm/2,z),new WallLadderPoint(n,t,z),new WallLadderPoint(h,t,z),new WallLadderPoint(h,B,z),new WallLadderPoint(c,B,z),
                new WallLadderPoint(c,-B,z),new WallLadderPoint(h,-B,z),new WallLadderPoint(h,-t,z),new WallLadderPoint(n,-t,z),new WallLadderPoint(n,-p.WidthMm/2,z)};
            var list=new List<WallLadderSegment>();for(int i=0;i<4;i++)list.Add(WallLadderSegment.Line(points[i],points[i+1]));
            list.Add(WallLadderSegment.Arc(c,z,90,0));list.Add(WallLadderSegment.Arc(c,z,0,-90));
            for(int i=5;i<9;i++)list.Add(WallLadderSegment.Line(points[i],points[i+1]));return list.ToArray();
        }
        internal static WallLadderSegment[] TopPath(WallLadderParameters p,double height)
        {
            double z=height+1200,ring=z-25,h=p.StandoffMm-105,c=p.StandoffMm+410;
            var a=new WallLadderPoint(-700,-355,height);var b=new WallLadderPoint(-700,-355,z);var d=new WallLadderPoint(h,-355,ring);var e=new WallLadderPoint(c,-355,ring);
            var f=new WallLadderPoint(c,355,ring);var g=new WallLadderPoint(h,355,ring);var j=new WallLadderPoint(-700,355,z);var k=new WallLadderPoint(-700,355,height);
            return new[]{WallLadderSegment.Line(a,b),WallLadderSegment.Line(b,d),WallLadderSegment.Line(d,e),WallLadderSegment.Arc(c,ring,-90,0),WallLadderSegment.Arc(c,ring,0,90),
                WallLadderSegment.Line(f,g),WallLadderSegment.Line(g,j),WallLadderSegment.Line(j,k)};
        }
        private static double Length(WallLadderSegment s) { return s.IsArc?s.RadiusMm*Math.PI/2:(s.End-s.Start).Length; }
        private static void PointAt(WallLadderSegment[] path,double distance,out WallLadderPoint at,out WallLadderPoint tangent)
        {
            foreach(var s in path){double l=Length(s);if(distance>l+1e-9){distance-=l;continue;}
                if(!s.IsArc){tangent=(s.End-s.Start).Unit();at=s.Start+tangent*distance;return;}
                // All outer arcs run clockwise from +Y through +X to -Y; exact arc-length evaluation, no chord sampling.
                double start=s.Start.Y>1e-8?Math.PI/2:0,angle=start-distance/s.RadiusMm;
                double centerN=s.Start.X-(start==0?s.RadiusMm:0);
                at=new WallLadderPoint(centerN+s.RadiusMm*Math.Cos(angle),s.RadiusMm*Math.Sin(angle),s.Start.Z);
                tangent=new WallLadderPoint(Math.Sin(angle),-Math.Cos(angle),0);return;
            }throw new InvalidOperationException("护笼竖杆站位超出路径。");
        }
        private static WallLadderPart Box(WallLadderPoint center,WallLadderPoint u,WallLadderPoint v,WallLadderPoint w,WallLadderPoint size)
        {return new WallLadderPart { Kind=WallLadderPartKind.Box,Center=center,U=u,V=v,W=w,Size=size };}
        private static bool Finite(double v){return !double.IsNaN(v)&&!double.IsInfinity(v);}
        private static void Positive(double v,double max,string name){if(!Finite(v)||v<=0||v>max)throw new InvalidOperationException(name+"须大于0且不超过"+max+" mm。");}
    }
}
