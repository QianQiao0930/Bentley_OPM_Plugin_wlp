using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using App=Bentley.Interop.MicroStationDGN.Application;
using Pt=Bentley.Interop.MicroStationDGN.Point3d;
using ComElement=Bentley.Interop.MicroStationDGN.Element;
namespace SteelSectionProbe
{
    internal static class SteelMemberFactory
    {
        internal static Bentley.Interop.MicroStationDGN.SmartSolidElement SweepAlongPath(
            App app,ModeData mode,Pt start,Pt near,double rotation,ComElement path)
        {
            var section=GenericProfile.SweepProfile(app,mode,start,near,rotation);
            var solid=app.SmartSolid.SweepProfileAlongPath(section,path);
            if(solid==null)throw new InvalidOperationException("型钢扫掠失败。");
            return solid;
        }
        /// <summary>沿任意坐标架扫掠型钢截面：截面 2D 点 (x, y) 映射到 origin + x·axisX + y·axisY，
        /// 再沿 axisZ 拉伸 lengthMm。<paramref name="axisX"/> / <paramref name="axisY"/> /
        /// <paramref name="axisZ"/> 为单位向量，截面轮廓坐标与 lengthMm 均为毫米。
        /// 截面里的真圆弧保留为真圆弧（不会留下成排分面棱）。</summary>
        internal static Element AlongAxis(ModeData mode,DPoint3d origin,double uorPerMm,
            DVector3d axisX,DVector3d axisY,DVector3d axisZ,double lengthMm,uint color)
        {return SolidPrimitiveFactory.Element(AlongAxisBody(mode,origin,uorPerMm,
            axisX,axisY,axisZ,lengthMm),color);}
        internal static SolidKernelEntity AlongAxisBody(ModeData mode,DPoint3d origin,double uorPerMm,
            DVector3d axisX,DVector3d axisY,DVector3d axisZ,double lengthMm)
        {
            if(mode==null || mode.Segments==null || mode.Segments.Length<3)
                throw new InvalidOperationException("型钢轮廓无效。");
            Func<double,double,DPoint3d> point=(x,y)=>new DPoint3d(
                origin.X+(x*axisX.X+y*axisY.X)*uorPerMm,
                origin.Y+(x*axisX.Y+y*axisY.Y)*uorPerMm,
                origin.Z+(x*axisX.Z+y*axisY.Z)*uorPerMm);
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            foreach(var segment in mode.Segments)
            {
                var a=point(segment.X0,segment.Y0);
                var b=point(segment.X1,segment.Y1);
                if(segment.IsArc)
                {
                    DEllipse3d arc;
                    if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(a,point(segment.Xm,segment.Ym),b,out arc))
                        throw new InvalidOperationException("型钢轮廓圆弧无效。");
                    profile.Add(CurvePrimitive.CreateArc(arc));
                }
                else profile.Add(CurvePrimitive.CreateLine(new DSegment3d(a,b)));
            }
            var a0=point(mode.Segments[0].X0,mode.Segments[0].Y0);
            var lengthUor=lengthMm*uorPerMm;
            var b0=new DPoint3d(a0.X+axisZ.X*lengthUor,a0.Y+axisZ.Y*lengthUor,
                a0.Z+axisZ.Z*lengthUor);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(a0,b0)));
            return SolidPrimitiveFactory.Sweep(profile,path);
        }
        internal static Element Vertical(ModeData mode,double ox,double oy,double oz,
            double xx,double xy,double yx,double yy,double heightMm,int direction,double uorPerMm)
        {
            Func<double,double,DPoint3d> point=(x,y)=>new DPoint3d(
                (ox+x*xx+y*yx)*uorPerMm,(oy+x*xy+y*yy)*uorPerMm,oz*uorPerMm);
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            foreach(var segment in mode.Segments)
            {
                var a=point(segment.X0,segment.Y0);
                var b=point(segment.X1,segment.Y1);
                if(segment.IsArc)
                {
                    DEllipse3d arc;
                    if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(a,point(segment.Xm,segment.Ym),b,out arc))
                        throw new InvalidOperationException("型钢轮廓圆弧无效。");
                    profile.Add(CurvePrimitive.CreateArc(arc));
                }
                else profile.Add(CurvePrimitive.CreateLine(new DSegment3d(a,b)));
            }
            var a0=point(mode.Segments[0].X0,mode.Segments[0].Y0);
            var b0=new DPoint3d(a0.X,a0.Y,a0.Z+direction*heightMm*uorPerMm);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(a0,b0)));
            return SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Sweep(profile,path),7);
        }
    }
}
