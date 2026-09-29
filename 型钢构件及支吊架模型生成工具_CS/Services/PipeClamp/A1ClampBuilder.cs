using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>A1：真半圆扫掠 U 形螺杆、四颗独立六角螺母。局部 Y 是开口方向。</summary>
    internal static class A1ClampBuilder
    {
        private sealed class Frame
        {
            internal readonly DPoint3d Center;
            internal readonly double Scale;
            private readonly double[] ex,open,across;
            internal Frame(DPoint3d center,double scale,DVector3d axis,double angleDeg)
            {
                Center=center;Scale=scale;
                double[] side,up;
                PipeClampFrame.Axes(axis.X,axis.Y,axis.Z,out ex,out side,out up);
                double radians=angleDeg*Math.PI/180,co=Math.Cos(radians),si=Math.Sin(radians);
                open=new double[3];across=new double[3];
                for(int i=0;i<3;i++)
                {open[i]=co*up[i]-si*side[i];across[i]=-si*up[i]-co*side[i];}
            }
            internal DPoint3d Point(double x,double y,double z)
            {return new DPoint3d(Center.X+Scale*(x*ex[0]+y*open[0]+z*across[0]),
                Center.Y+Scale*(x*ex[1]+y*open[1]+z*across[1]),
                Center.Z+Scale*(x*ex[2]+y*open[2]+z*across[2]));}
            internal DVector3d Vector(double x,double y,double z)
            {return new DVector3d(Scale*(x*ex[0]+y*open[0]+z*across[0]),
                Scale*(x*ex[1]+y*open[1]+z*across[1]),
                Scale*(x*ex[2]+y*open[2]+z*across[2]));}
        }

        internal static List<Element> Build(A1ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            if(plan==null)throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("A1 管卡需要三维模型。");
            var frame=new Frame(center,model.GetModelInfo().UorPerMeter/1000.0,axis,plan.AngleDeg);
            double radius=plan.Row.C/2.0,tip=plan.Row.D;
            var first=frame.Point(0,tip,radius);
            var path=new[]{
                SolidPathSegment.Line(first,frame.Point(0,0,radius)),
                SolidPathSegment.Arc(frame.Point(0,0,radius),frame.Point(0,-radius,0),
                    frame.Point(0,0,-radius)),
                SolidPathSegment.Line(frame.Point(0,0,-radius),frame.Point(0,tip,-radius))};
            var result=new List<Element>();
            result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.RoundPath(first,
                frame.Vector(0,-1,0),plan.Row.Bolt/2.0*frame.Scale,path),A1ClampCatalog.BoltColor));
            foreach(double sign in new[]{1.0,-1.0})
            {
                result.Add(Nut(frame,plan,sign,plan.NutLow1Mm,plan.NutCenterMm));
                result.Add(Nut(frame,plan,sign,plan.NutLow2Mm,
                    plan.NutCenterMm+plan.NutHeightMm));
            }
            return result;
        }
        private static Element Nut(Frame frame,A1ClampPlan plan,double sign,double low,double high)
        {
            double radius=plan.NutAcrossFlatsMm/(2*Math.Cos(Math.PI/6));
            var points=new List<DPoint3d>();
            for(int i=0;i<6;i++)
            {double theta=Math.PI/6+i*Math.PI/3;
                points.Add(frame.Point(radius*Math.Cos(theta),low,
                    sign*plan.Row.C/2.0+radius*Math.Sin(theta)));}
            var solid=SolidPrimitiveFactory.PolygonPrism(points,frame.Vector(0,high-low,0));
            double hole=(plan.Row.Bolt+2.0)/2.0;
            SolidPrimitiveFactory.Subtract(ref solid,new[]{SolidPrimitiveFactory.Cylinder(
                frame.Point(0,low-5,sign*plan.Row.C/2.0),
                frame.Point(0,high+5,sign*plan.Row.C/2.0),hole*frame.Scale)},"A1 螺母中心孔");
            return SolidPrimitiveFactory.Element(solid,A1ClampCatalog.NutColor);
        }
    }
}
