using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>A22 / A24 共用相切圆角剖面；按孔位生成两套或四套紧固件。</summary>
    internal static class A22ClampBuilder
    {
        internal static List<Element> Build(A22ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)
                throw new InvalidOperationException("A22 管夹需要在三维 DGN 模型中放置。");
            var frame=new PipeClampFrame(center,model.GetModelInfo().UorPerMeter/1000.0,
                axis.X,axis.Y,axis.Z);
            var result=new List<Element>();
            result.Add(SolidPrimitiveFactory.Element(Half(frame,plan,true),A22ClampCatalog.BodyColor));
            result.Add(SolidPrimitiveFactory.Element(Half(frame,plan,false),A22ClampCatalog.BodyColor));
            foreach(double y in plan.BoltCentersYmm)
                Fastener(result,frame,plan,y);
            return result;
        }

        private static SolidKernelEntity Half(PipeClampFrame f,A22ClampPlan p,bool upper)
        {
            double margin=A22ClampCatalog.ThroughMarginMm;
            double halfWidth=p.W/2.0;
            double outer=p.OuterRadiusMm;
            double innerFace=p.C-p.T;
            double inner=p.A/2.0;
            double ty=p.TransitionTangentYmm,tz=p.TransitionTangentZmm;
            double endY=p.TransitionEndYmm,filletCenterZ=p.C+p.RMinMm;
            double outerAngle=Math.Atan2(tz,ty);
            double filletStartAngle=Math.Atan2(tz-filletCenterZ,ty-endY);
            double filletMidAngle=(filletStartAngle-Math.PI/2.0)/2.0;
            double filletMidY=endY+p.RMinMm*Math.Cos(filletMidAngle);
            double filletMidZ=filletCenterZ+p.RMinMm*Math.Sin(filletMidAngle);
            double x=-halfWidth;
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            Arc(profile,f,upper,x,0,outer,
                outer*Math.Cos((Math.PI/2.0+outerAngle)/2.0),
                outer*Math.Sin((Math.PI/2.0+outerAngle)/2.0),ty,tz);
            Arc(profile,f,upper,x,ty,tz,filletMidY,filletMidZ,endY,p.C);
            Line(profile,f,upper,x,endY,p.C,p.FlangeEndMm,p.C);
            Line(profile,f,upper,x,p.FlangeEndMm,p.C,p.FlangeEndMm,innerFace);
            Line(profile,f,upper,x,p.FlangeEndMm,innerFace,p.FlangeRootMm,innerFace);
            Arc(profile,f,upper,x,p.FlangeRootMm,innerFace,0,inner,
                -p.FlangeRootMm,innerFace);
            Line(profile,f,upper,x,-p.FlangeRootMm,innerFace,-p.FlangeEndMm,innerFace);
            Line(profile,f,upper,x,-p.FlangeEndMm,innerFace,-p.FlangeEndMm,p.C);
            Line(profile,f,upper,x,-p.FlangeEndMm,p.C,-endY,p.C);
            Arc(profile,f,upper,x,-endY,p.C,-filletMidY,filletMidZ,-ty,tz);
            Arc(profile,f,upper,x,-ty,tz,
                outer*Math.Cos((Math.PI-outerAngle+Math.PI/2.0)/2.0),
                outer*Math.Sin((Math.PI-outerAngle+Math.PI/2.0)/2.0),0,outer);
            var body=SolidPrimitiveFactory.Prism(profile,f.Point(x,0,upper?outer:-outer),
                f.Direction(p.W,0,0));

            double z0=upper?innerFace:-outer-p.RMinMm-margin;
            double z1=upper?outer+p.RMinMm+margin:-innerFace;
            var holes=new List<SolidKernelEntity>();
            foreach(double y in p.BoltCentersYmm)
                holes.Add(SolidPrimitiveFactory.Cylinder(f.Point(0,y,z0-margin),
                    f.Point(0,y,z1+margin),p.G/2.0*f.Scale));
            SolidPrimitiveFactory.Subtract(ref body,holes,p.Code+" 两端螺栓孔");
            // 大圆角可能延伸到螺栓附近；按垫圈外径在法兰外表面整平座面。
            double seatRadius=p.BoltDiameterMm*A22ClampCatalog.WasherOdRatio/2.0;
            if(p.TransitionEndYmm>p.B-seatRadius)
            {
                var seats=new List<SolidKernelEntity>();
                foreach(double side in new[]{-1.0,1.0})
                    seats.Add(SolidPrimitiveFactory.Cylinder(
                        f.Point(0,side*p.B,upper?p.C:-outer-p.RMinMm-margin),
                        f.Point(0,side*p.B,upper?outer+p.RMinMm+margin:-p.C),
                        seatRadius*f.Scale));
                SolidPrimitiveFactory.Subtract(ref body,seats,p.Code+" 垫圈座面整平");
            }
            return body;
        }

        private static void Line(CurveVector profile,PipeClampFrame f,bool upper,double x,
            double y0,double z0,double y1,double z1)
        {
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(
                f.Point(x,y0,upper?z0:-z0),f.Point(x,y1,upper?z1:-z1))));
        }

        private static void Arc(CurveVector profile,PipeClampFrame f,bool upper,double x,
            double y0,double z0,double ym,double zm,double y1,double z1)
        {
            DEllipse3d arc;
            if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(
                f.Point(x,y0,upper?z0:-z0),f.Point(x,ym,upper?zm:-zm),
                f.Point(x,y1,upper?z1:-z1),out arc))
                throw new InvalidOperationException("A22 过渡圆角构造失败。");
            profile.Add(CurvePrimitive.CreateArc(arc));
        }

        private static void Fastener(List<Element> result,PipeClampFrame f,A22ClampPlan p,double y)
        {
            double d=p.BoltDiameterMm;
            double washer=A22ClampCatalog.WasherThicknessMm;
            double head=d*A22ClampCatalog.BoltHeadHeightRatio;
            double nutHeight=d*A22ClampCatalog.NutHeightRatio;
            double across=d*A22ClampCatalog.HexAcrossFlatsRatio;
            double margin=A22ClampCatalog.ThroughMarginMm;
            var shank=SolidPrimitiveFactory.Cylinder(
                f.Point(0,y,-p.C-washer-nutHeight-A22ClampCatalog.BoltTipExtraMm),
                f.Point(0,y,p.C+washer+head),d/2.0*f.Scale);
            result.Add(SolidPrimitiveFactory.Element(shank,A22ClampCatalog.BoltColor));
            result.Add(SolidPrimitiveFactory.Element(
                Hex(f,y,p.C+washer,p.C+washer+head,across),A22ClampCatalog.BoltColor));
            var nut=Hex(f,y,-p.C-washer-nutHeight,-p.C-washer,across);
            SolidPrimitiveFactory.Subtract(ref nut,new[]{SolidPrimitiveFactory.Cylinder(
                f.Point(0,y,-p.C-washer-nutHeight-margin),
                f.Point(0,y,-p.C-washer+margin),p.G/2.0*f.Scale)},"A22 螺母中心孔");
            result.Add(SolidPrimitiveFactory.Element(nut,A22ClampCatalog.BoltColor));
            foreach(var span in new[]{new[]{p.C,p.C+washer},new[]{-p.C-washer,-p.C}})
            {
                var ring=SolidPrimitiveFactory.Cylinder(f.Point(0,y,span[0]),
                    f.Point(0,y,span[1]),d*A22ClampCatalog.WasherOdRatio/2.0*f.Scale);
                SolidPrimitiveFactory.Subtract(ref ring,new[]{SolidPrimitiveFactory.Cylinder(
                    f.Point(0,y,span[0]-margin),f.Point(0,y,span[1]+margin),
                    p.G/2.0*f.Scale)},"A22 垫圈中心孔");
                result.Add(SolidPrimitiveFactory.Element(ring,A22ClampCatalog.BoltColor));
            }
        }

        private static SolidKernelEntity Box(PipeClampFrame f,double x0,double x1,
            double y0,double y1,double z0,double z1)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{f.Point(x0,y0,z0),
                f.Point(x0,y1,z0),f.Point(x0,y1,z1),f.Point(x0,y0,z1)},
                f.Direction(x1-x0,0,0));
        }

        private static SolidKernelEntity Hex(PipeClampFrame f,double y,double z0,double z1,
            double acrossFlats)
        {
            double radius=acrossFlats/(2.0*Math.Cos(Math.PI/6.0));
            var points=new DPoint3d[6];
            for(int i=0;i<6;i++)
            {
                double angle=Math.PI/6.0+i*Math.PI/3.0;
                points[i]=f.Point(radius*Math.Cos(angle),y+radius*Math.Sin(angle),z0);
            }
            return SolidPrimitiveFactory.PolygonPrism(points,f.Direction(0,0,z1-z0));
        }
    }
}
