using System;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.Interop.MicroStationDGN;
using Bentley.MstnPlatformNET;
using App = Bentley.Interop.MicroStationDGN.Application;
using Pt = Bentley.Interop.MicroStationDGN.Point3d;
using DgnElement = Bentley.DgnPlatformNET.Elements.Element;
using ComplexShapeElement = Bentley.Interop.MicroStationDGN.ComplexShapeElement;

namespace SteelSectionProbe
{
    internal static class GenericProfile
    {
        internal static CurveVector Curves(ModeData mode, double x, double y, double z, double scale)
        {
            Func<double,double,DPoint3d> point=(px,py)=>new DPoint3d(x+px*scale,y+py*scale,z);
            CurveVector result=CurveVector.Create(CurveVector.BoundaryType.Outer);
            foreach (SegmentData segment in mode.Segments)
            {
                DPoint3d start=point(segment.X0,segment.Y0),end=point(segment.X1,segment.Y1);
                if (!segment.IsArc)
                    result.Add(CurvePrimitive.CreateLine(new DSegment3d(start,end)));
                else
                {
                    DEllipse3d arc;
                    if (!DEllipse3d.TryCircularArcFromStartMiddleEnd(start,point(segment.Xm,segment.Ym),end,out arc))
                        throw new InvalidOperationException("Arc construction failed");
                    result.Add(CurvePrimitive.CreateArc(arc));
                }
            }
            return result;
        }
        internal static DgnElement Native(ModeData mode,double x,double y,double z,double scale)
        {
            return DraftingElementSchema.ToElement(Session.Instance.GetActiveDgnModel(),Curves(mode,x,y,z,scale),null);
        }
        internal static ComplexShapeElement Preview(App app, ModeData mode, Pt basePoint)
        {
            var info=Session.Instance.GetActiveDgnModel().GetModelInfo();
            double masterPerMm=info.UorPerMeter/info.UorPerMaster/1000.0;
            Func<double,double,Pt> point=(px,py)=>app.Point3dFromXYZ(basePoint.X+px*masterPerMm,basePoint.Y+py*masterPerMm,basePoint.Z);
            ChainableElement[] parts=new ChainableElement[mode.Segments.Length];
            for (int i=0;i<parts.Length;i++)
            {
                SegmentData segment=mode.Segments[i];
                Pt start=point(segment.X0,segment.Y0),end=point(segment.X1,segment.Y1);
                if (!segment.IsArc) parts[i]=app.CreateLineElement2(null,ref start,ref end);
                else
                {
                    Pt middle=point(segment.Xm,segment.Ym);
                    parts[i]=app.CreateArcElement3(null,ref start,ref middle,ref end);
                }
            }
            return app.CreateComplexShapeElement1(ref parts,MsdFillMode.NotFilled);
        }
        internal static ComplexShapeElement SweepProfile(App app, ModeData mode, Pt start, Pt next, double rotationDegrees)
        {
            double tx=next.X-start.X,ty=next.Y-start.Y,tz=next.Z-start.Z;
            double length=Math.Sqrt(tx*tx+ty*ty+tz*tz);
            if (length<1e-10) throw new InvalidOperationException("Path start tangent is zero");
            tx/=length; ty/=length; tz/=length;
            double ux=0,uy=0,uz=1;
            if (Math.Abs(tz)>1-1e-9) { ux=0;uy=1;uz=0; }
            double xx=uy*tz-uz*ty,xy=uz*tx-ux*tz,xz=ux*ty-uy*tx;
            length=Math.Sqrt(xx*xx+xy*xy+xz*xz); xx/=length;xy/=length;xz/=length;
            double yx=ty*xz-tz*xy,yy=tz*xx-tx*xz,yz=tx*xy-ty*xx;
            double angle=rotationDegrees*Math.PI/180.0,c=Math.Cos(angle),s=Math.Sin(angle);
            double rx=xx*c+yx*s,ry=xy*c+yy*s,rz=xz*c+yz*s;
            double vx=yx*c-xx*s,vy=yy*c-xy*s,vz=yz*c-xz*s;
            var info=Session.Instance.GetActiveDgnModel().GetModelInfo();
            double masterPerMm=info.UorPerMeter/info.UorPerMaster/1000.0;
            Func<double,double,Pt> point=(px,py)=>app.Point3dFromXYZ(
                start.X+masterPerMm*(px*rx+py*vx),
                start.Y+masterPerMm*(px*ry+py*vy),
                start.Z+masterPerMm*(px*rz+py*vz));
            ChainableElement[] parts=new ChainableElement[mode.Segments.Length];
            for(int i=0;i<parts.Length;i++)
            {
                SegmentData seg=mode.Segments[i];
                Pt first=point(seg.X0,seg.Y0),last=point(seg.X1,seg.Y1);
                if(!seg.IsArc) parts[i]=app.CreateLineElement2(null,ref first,ref last);
                else { Pt middle=point(seg.Xm,seg.Ym); parts[i]=app.CreateArcElement3(null,ref first,ref middle,ref last); }
            }
            return app.CreateComplexShapeElement1(ref parts,MsdFillMode.NotFilled);
        }
    }
}
