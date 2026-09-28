using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class VerticalPipeSupportBuilder
    {
        private sealed class Frame
        {
            internal DPoint3d Center;
            internal DVector3d X,Y,Z;
            internal double Scale;
            internal DPoint3d P(double x,double y,double z)
            { return new DPoint3d(Center.X+Scale*(x*X.X+y*Y.X+z*Z.X),
                Center.Y+Scale*(x*X.Y+y*Y.Y+z*Z.Y),Center.Z+Scale*(x*X.Z+y*Y.Z+z*Z.Z)); }
            internal DVector3d V(double x,double y,double z)
            { return new DVector3d(Scale*(x*X.X+y*Y.X+z*Z.X),
                Scale*(x*X.Y+y*Y.Y+z*Z.Y),Scale*(x*X.Z+y*Y.Z+z*Z.Z)); }
        }
        private static Frame MakeFrame(DPoint3d center,DVector3d axis,double angle,double scale,
            bool f10)
        {
            double length=Math.Sqrt(axis.X*axis.X+axis.Y*axis.Y+axis.Z*axis.Z);
            if(length<=0) throw new InvalidOperationException("立管轴线长度无效。");
            var z=new DVector3d(axis.X/length,axis.Y/length,axis.Z/length);
            double radians=angle*Math.PI/180;
            // F6/F7: 0° = +Y, clockwise; F10: 0° = +X, counterclockwise.
            var refX=f10?new DVector3d(Math.Cos(radians),Math.Sin(radians),0):
                new DVector3d(Math.Sin(radians),Math.Cos(radians),0);
            double dot=refX.X*z.X+refX.Y*z.Y+refX.Z*z.Z;
            double x0=refX.X-dot*z.X,y0=refX.Y-dot*z.Y,z0=refX.Z-dot*z.Z;
            double xLength=Math.Sqrt(x0*x0+y0*y0+z0*z0);
            var x=new DVector3d(x0/xLength,y0/xLength,z0/xLength);
            var y=new DVector3d(z.Y*x.Z-z.Z*x.Y,z.Z*x.X-z.X*x.Z,z.X*x.Y-z.Y*x.X);
            return new Frame {Center=center,X=x,Y=y,Z=z,Scale=scale};
        }
        private static SolidKernelEntity Box(Frame f,double x0,double x1,double y0,double y1,double z0,double z1)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{f.P(x0,y0,z0),f.P(x1,y0,z0),
                f.P(x1,y1,z0),f.P(x0,y1,z0)},f.V(0,0,z1-z0));
        }
        private static SolidKernelEntity Cylinder(Frame f,double x0,double y0,double z0,
            double x1,double y1,double z1,double radius)
        { return SolidPrimitiveFactory.Cylinder(f.P(x0,y0,z0),f.P(x1,y1,z1),radius*f.Scale); }
        internal static IList<Element> Build(VerticalPipeSupportPlan plan,DPoint3d center,DVector3d axis)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d) throw new InvalidOperationException("请在三维模型中放置立管耳轴。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var parts=new List<Element>();
            for(int side=0;side<plan.Count;side++)
            {
                var f=MakeFrame(center,axis,plan.AzimuthDegrees+side*180,scale,
                    plan.Kind==VerticalPipeSupportKind.F10);
                if(plan.Kind==VerticalPipeSupportKind.F10) BuildF10Side(plan,f,parts);
                else BuildTrunnionSide(plan,f,parts);
            }
            return parts;
        }
        private static void BuildF10Side(VerticalPipeSupportPlan p,Frame f,IList<Element> parts)
        {
            double inner=p.PipeOd/2,outer=inner+p.EarWidthMm;
            parts.Add(SolidPrimitiveFactory.Element(Box(f,inner,outer,-5,5,0,p.EarHeightMm),3));
            double baseInner=outer-70,baseOuter=outer;
            var baseBody=Box(f,baseInner,baseOuter,-60,60,-10,0);
            if(p.Fixed)
            {
                double holeX=(baseInner+baseOuter)/2;
                var holes=new List<SolidKernelEntity> {
                    Cylinder(f,holeX,-40,-12,holeX,-40,2,7),
                    Cylinder(f,holeX,40,-12,holeX,40,2,7)};
                SolidPrimitiveFactory.Subtract(ref baseBody,holes,"F10 底板开孔");
                foreach(double y in new[]{-40.0,40.0})
                {
                    parts.Add(SolidPrimitiveFactory.Element(Cylinder(f,holeX,y,-40,holeX,y,0,6),5));
                    // Simplified hex head, matching the Python script's separate bolt solids.
                    var hex=new DPoint3d[6];
                    double radius=18/(2*Math.Cos(Math.PI/6));
                    for(int i=0;i<6;i++) hex[i]=f.P(holeX+radius*Math.Cos(i*Math.PI/3),
                        y+radius*Math.Sin(i*Math.PI/3),0);
                    parts.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(hex,
                        f.V(0,0,8.4)),5));
                }
            }
            parts.Add(SolidPrimitiveFactory.Element(baseBody,3));
        }
        private static void BuildTrunnionSide(VerticalPipeSupportPlan p,Frame f,IList<Element> parts)
        {
            var outer=Cylinder(f,-10,0,0,p.LengthMm,0,0,p.TrunnionOd/2);
            var bore=Cylinder(f,-20,0,0,p.LengthMm+10,0,0,p.TrunnionOd/2-p.WallMm);
            SolidPrimitiveFactory.Subtract(ref outer,new[]{bore},"耳轴空心");
            if(p.EndPlateThicknessMm>0)
            {
                var end=Cylinder(f,p.LengthMm-p.EndPlateThicknessMm,0,0,p.LengthMm,0,0,
                    (p.TrunnionOd+12)/2);
                SolidPrimitiveFactory.Union(ref outer,new[]{end},"耳轴端板");
            }
            double pipeRadius=p.PipeOd/2+(p.TrunnionOd>=p.PipeOd-1?0.1:0);
            var saddle=Cylinder(f,0,0,-p.LengthMm-p.PipeOd,0,0,p.LengthMm+p.PipeOd,pipeRadius);
            SolidPrimitiveFactory.Subtract(ref outer,new[]{saddle},"耳轴鞍口");
            parts.Add(SolidPrimitiveFactory.Element(outer,3));
            if(p.PadThicknessMm>0)
            {
                double half=p.TrunnionOd/2+p.PadWidthMm+10;
                var shell=Cylinder(f,0,0,-half,0,0,half,p.PipeOd/2+p.PadThicknessMm);
                var core=Cylinder(f,0,0,-half-10,0,0,half+10,p.PipeOd/2);
                SolidPrimitiveFactory.Subtract(ref shell,new[]{core},"补强板圆环");
                double reach=p.PipeOd/2+p.PadThicknessMm+10;
                double radius=p.TrunnionOd/2+p.PadWidthMm;
                var disc=Cylinder(f,0,0,0,reach,0,0,radius);
                var outside=Cylinder(f,0,0,0,reach,0,0,radius);
                SolidPrimitiveFactory.Subtract(ref outside,new[]{shell},"补强板外侧");
                SolidPrimitiveFactory.Subtract(ref disc,new[]{outside},"补强板求交");
                SolidPrimitiveFactory.Subtract(ref disc,new[]{Box(f,-half,0,-half,half,-half,half)},
                    "补强板中心线齐平");
                parts.Add(SolidPrimitiveFactory.Element(disc,3));
            }
        }
    }
}
