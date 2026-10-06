using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    // 迁移Python毫米布局；焊接U形板200×100×6，并非目录中的轧制槽钢。
    internal static class SpiralStairCalculator
    {
        private static bool Finite(double v){return !double.IsNaN(v)&&!double.IsInfinity(v);}
        internal static HandrailPoint Point(double r,double a,double z){return new HandrailPoint(r*Math.Cos(a),r*Math.Sin(a),z);}
        private static List<HandrailPoint> Sample(double r,double a,double b,double z0,double z1)
        {
            double samples=Math.Ceiling(Math.Abs(b-a)/Math.Sqrt(4/r));
            if(!Finite(samples)||samples>4096)throw new InvalidOperationException("梯梁截面过多，请减小盘梯高度。");
            int count=Math.Max(1,(int)samples);
            return Enumerable.Range(0,count+1).Select(i=>Point(r,a+(b-a)*i/count,z0+(z1-z0)*i/count)).ToList();
        }
        private static List<HandrailPoint> Ccw(List<HandrailPoint> points)
        {
            double area=0;for(int i=0;i<points.Count;i++){var a=points[i];var b=points[(i+1)%points.Count];area+=a.X*b.Y-b.X*a.Y;}
            if(area<0)points.Reverse();return points;
        }
        private static List<HandrailPoint> Sector(double inner,double outer,double a,double b,double z)
        {
            if(b<a){double t=a;a=b;b=t;}var q=Sample(outer,a,b,z,z);var inside=Sample(inner,a,b,z,z);inside.Reverse();q.AddRange(inside);return Ccw(q);
        }
        private static void Plate(SpiralStairPlan plan,string name,List<HandrailPoint> corners,double thickness)
        {plan.Plates.Add(new SpiralStairPlate{Name=name,Corners=Ccw(corners),ThicknessMm=thickness});}
        private static List<HandrailPoint> Band(double inner,double outer,double angle,double into,double z)
        {return new List<HandrailPoint>{Point(inner,angle,z),Point(outer,angle,z),Point(outer,angle+into*4/outer,z),Point(inner,angle+into*4/inner,z)};}
        internal static SpiralStairPlan Calculate(SpiralStairParameters input)
        {
            if(input==null)throw new InvalidOperationException("缺少盘梯参数。");var p=input.Snapshot();
            var positive=new[]{p.TankDiameterMm,p.LandingIntervalMm,p.RiserMm,p.TreadDepthMm,p.ClearWidthMm,p.LandingLengthMm,p.TopLengthMm};
            if(positive.Any(v=>!Finite(v)||v<=0)||!Finite(p.StartZmm)||!Finite(p.EndZmm)||!Finite(p.StartAngleDegrees)||!Finite(p.WallGapMm))
                throw new InvalidOperationException("盘梯尺寸必须为有限数字，长度及高度间隔必须大于零。");
            if(p.EndZmm<=p.StartZmm||p.WallGapMm<0||(p.Direction!=1&&p.Direction!=-1))throw new InvalidOperationException("终点须高于起点，罐壁间隙不得为负，方向须为正向或反向。");
            if(p.ClearWidthMm<650||Math.Min(p.LandingLengthMm,p.TopLengthMm)<p.ClearWidthMm)throw new InvalidOperationException("梯宽不得小于650mm，平台长度不得小于梯宽。");
            HandrailCalculator.ModularSpans(1000,p.MaxPostSpacingMm);
            if(!Enum.IsDefined(typeof(HandrailConnection),p.Connection)||!Finite(p.StructureOffsetMm)||p.Connection==HandrailConnection.Type2&&p.StructureOffsetMm<=83.01)
                throw new InvalidOperationException("栏杆连接参数无效；类型2连接板距离须大于83mm。");
            double slope=Math.Atan(p.RiserMm/p.TreadDepthMm)*180/Math.PI;
            if(slope>=50)throw new InvalidOperationException("梯段倾角必须小于50°。");
            double height=p.EndZmm-p.StartZmm;
            if(height/p.RiserMm>2000||height/p.LandingIntervalMm>100)throw new InvalidOperationException("单次最多2000级踏步、100个梯段，请拆分盘梯。");
            var plan=new SpiralStairPlan{Parameters=p,InnerRadiusMm=p.TankDiameterMm/2+100+p.WallGapMm,SlopeDegrees=slope};
            plan.OuterRadiusMm=plan.InnerRadiusMm+p.ClearWidthMm;
            if(!Finite(plan.OuterRadiusMm))throw new InvalidOperationException("盘梯半径超出有效范围。");
            double r=plan.InnerRadiusMm,outer=plan.OuterRadiusMm,delta=p.Direction*p.TreadDepthMm/r;
            var levels=new List<double>{p.StartZmm};
            for(int i=1;p.StartZmm+i*p.LandingIntervalMm<p.EndZmm-1e-6;i++)levels.Add(p.StartZmm+i*p.LandingIntervalMm);
            levels.Add(p.EndZmm);plan.RestPlatformCount=levels.Count-2;
            var innerBeam=new SpiralStairBeam{Name="内侧梯梁"};var outerBeam=new SpiralStairBeam{Name="外侧梯梁"};
            plan.Beams.Add(innerBeam);plan.Beams.Add(outerBeam);
            double angle=p.StartAngleDegrees*Math.PI/180;
            for(int f=0;f<levels.Count-1;f++)
            {
                double z0=levels[f],z1=levels[f+1];int n=(int)Math.Round((z1-z0)/p.RiserMm);
                if(n<1||Math.Abs(n*p.RiserMm-(z1-z0))>1e-6)throw new InvalidOperationException("每个梯段的高度必须是踏步高度的整数倍。");
                plan.FlightCounts.Add(n);double end=angle+n*delta;
                double exit=end+p.Direction*(f==levels.Count-2?p.TopLengthMm:p.LandingLengthMm)/r;
                foreach(var beam in plan.Beams)
                {
                    double radius=beam==innerBeam?r:outer;var points=Sample(radius,angle,end,z0,z1);
                    beam.Points.AddRange(beam.Points.Count==0?points:points.Skip(1));beam.Points.Add(Point(radius,exit,z1));
                }
                for(int step=1;step<=n;step++)
                {
                    double a=angle+(step-1)*delta,b=a+delta,z=z0+step*p.RiserMm;int number=++plan.TreadCount;
                    Plate(plan,"踏步"+number+"水平板",Sector(r,outer,a,b,z-4),4);
                    Plate(plan,"踏步"+number+"前长边下折",Band(r,outer,a,p.Direction,z-40),40);
                    Plate(plan,"踏步"+number+"后长边上折",Band(r,outer,b,-p.Direction,z-4),44);
                }
                Plate(plan,f==levels.Count-2?"顶部平台平板":"休息平台"+(f+1)+"平板",new List<HandrailPoint>{Point(r,end,z1+196),Point(outer,end,z1+196),Point(outer,exit,z1+196),Point(r,exit,z1+196)},4);
                angle=exit;
            }
            outerBeam.ReturnStart=outerBeam.Points.Count-1;outerBeam.Points.Add(innerBeam.Points.Last());
            for(int side=0;side<2;side++)
            {
                var beam=plan.Beams[side];beam.Profiles=Profiles(beam,side==0);
                plan.RailingPaths.Add(beam.Profiles.Select(q=>q[1]).ToList());
            }
            return plan;
        }
        private static List<List<HandrailPoint>> Profiles(SpiralStairBeam beam,bool inner)
        {
            double[,] outline={{0,200},{100,200},{100,194},{6,194},{6,6},{100,6},{100,0},{0,0}};
            HandrailPoint returnNormal=new HandrailPoint();
            if(beam.ReturnStart>=0)
            {
                var start=beam.Points[beam.ReturnStart];var end=beam.Points[beam.ReturnStart+1];var tangent=(end-start).Horizontal();
                returnNormal=tangent.Normal(1);var incoming=start-beam.Points[beam.ReturnStart-1];
                if(HandrailPoint.Dot(returnNormal,incoming)<0)returnNormal=returnNormal*(-1);
            }
            var profiles=new List<List<HandrailPoint>>();
            for(int i=0;i<beam.Points.Count;i++)
            {
                var q=beam.Points[i];var normal=new HandrailPoint(q.X,q.Y,0).Unit();
                if(beam.ReturnStart>=0&&i>=beam.ReturnStart)
                {
                    if(i==beam.ReturnStart){double d=1+HandrailPoint.Dot(normal,returnNormal);if(d<=1e-8)throw new InvalidOperationException("顶部折回角度无法斜接。");normal=(normal+returnNormal)*(1/d);}
                    else normal=returnNormal;
                }
                normal=normal*(inner?-1:1);var profile=new List<HandrailPoint>();
                for(int j=0;j<8;j++)profile.Add(q+normal*outline[j,0]+HandrailPoint.Up*outline[j,1]);profiles.Add(profile);
            }
            return profiles;
        }
        internal static HandrailPlan Railing(SpiralStairPlan plan,bool inner)
        {
            var p=plan.Parameters;
            return HandrailCalculator.CalculateArc(new HandrailParameters{Side=inner?-p.Direction:p.Direction,Connection=p.Connection,
                Closure=HandrailClosure.None,MaxPostSpacingMm=p.MaxPostSpacingMm,StructureOffsetMm=p.StructureOffsetMm},
                new HandrailArcInput{MixedPoints=plan.RailingPaths[inner?0:1]});
        }
    }
}
