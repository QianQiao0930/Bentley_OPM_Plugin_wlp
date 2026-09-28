using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Creates detached SmartSolids in active-model UOR for equipment parts.</summary>
    internal static class SolidPrimitiveFactory
    {
        internal static SolidKernelEntity Cylinder(DPoint3d a,DPoint3d b,double radius)
        {
            if(radius<=0) throw new InvalidOperationException("圆柱半径无效。");
            var tangent=new DVector3d(b.X-a.X,b.Y-a.Y,b.Z-a.Z);
            var disk=CurveVector.CreateDisk(DEllipse3d.FromCenterRadiusNormal(a,radius,tangent),
                CurveVector.BoundaryType.Outer);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(a,b)));
            return Sweep(disk,path);
        }
        internal static SolidKernelEntity PolygonPrism(IList<DPoint3d> points,DVector3d extrusion)
        {
            if(points==null || points.Count<3) throw new InvalidOperationException("板件轮廓点不足。");
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            for(int i=0;i<points.Count;i++)
                profile.Add(CurvePrimitive.CreateLine(new DSegment3d(points[i],points[(i+1)%points.Count])));
            return Prism(profile,points[0],extrusion);
        }
        /// <summary>闭合剖面沿直线拉伸成棱柱；剖面里可以放真圆弧（圆角面即真圆柱面，
        /// 不会像折线那样留下成排的分面棱）。</summary>
        internal static SolidKernelEntity Prism(CurveVector profile,DPoint3d origin,DVector3d extrusion)
        {
            var target=new DPoint3d(origin.X+extrusion.X,origin.Y+extrusion.Y,origin.Z+extrusion.Z);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(origin,target)));
            return Sweep(profile,path);
        }
        internal static SolidKernelEntity RoundPath(DPoint3d first,DVector3d tangent,
            double radius,IList<SolidPathSegment> segments)
        {
            var disk=CurveVector.CreateDisk(DEllipse3d.FromCenterRadiusNormal(first,radius,tangent),
                CurveVector.BoundaryType.Outer);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            foreach(var segment in segments)
            {
                if(segment.IsArc)
                {
                    DEllipse3d arc;
                    if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(segment.Start,segment.Middle,segment.End,out arc))
                        throw new InvalidOperationException("无法构造圆弧路径。");
                    path.Add(CurvePrimitive.CreateArc(arc));
                }
                else path.Add(CurvePrimitive.CreateLine(new DSegment3d(segment.Start,segment.End)));
            }
            return Sweep(disk,path);
        }
        internal static SolidKernelEntity Sweep(CurveVector profile,CurveVector path)
        {
            SolidKernelEntity body;
            var status=Create.BodyFromSweep(out body,profile,path,
                Session.Instance.GetActiveDgnModelRef(),false,true,false,null,null,null,null);
            if(status!=BentleyStatus.Success || body==null)
                throw new InvalidOperationException("三维实体扫掠失败："+status);
            return body;
        }
        internal static void Union(ref SolidKernelEntity target,IList<SolidKernelEntity> others,string name)
        {
            if(others==null || others.Count==0) return;
            var tools=new SolidKernelEntity[others.Count];
            others.CopyTo(tools,0);
            var status=Modify.BooleanUnion(ref target,ref tools,tools.Length);
            if(status!=BentleyStatus.Success)
                throw new InvalidOperationException(name+" 相并失败："+status);
        }
        internal static void Subtract(ref SolidKernelEntity target,IList<SolidKernelEntity> cutters,string name)
        {
            if(cutters==null || cutters.Count==0) return;
            var tools=new SolidKernelEntity[cutters.Count];
            cutters.CopyTo(tools,0);
            var status=Modify.BooleanSubtract(ref target,ref tools,tools.Length);
            if(status!=BentleyStatus.Success)
                throw new InvalidOperationException(name+" 差集失败："+status);
        }
        internal static Element Element(SolidKernelEntity body,uint color)
        {
            Element result;
            var status=Convert1.BodyToElement(out result,body,null,Session.Instance.GetActiveDgnModelRef());
            if(status!=BentleyStatus.Success || result==null)
                throw new InvalidOperationException("三维实体转 DGN 元素失败："+status);
            var style=new ElementPropertiesSetter();
            style.SetColor(color);
            if(!style.Apply(result)) throw new InvalidOperationException("无法设置人孔构件颜色。");
            return result;
        }
    }
    internal sealed class SolidPathSegment
    {
        internal DPoint3d Start,Middle,End;
        internal bool IsArc;
        internal static SolidPathSegment Line(DPoint3d a,DPoint3d b)
        { return new SolidPathSegment { Start=a,End=b }; }
        internal static SolidPathSegment Arc(DPoint3d a,DPoint3d m,DPoint3d b)
        { return new SolidPathSegment { Start=a,Middle=m,End=b,IsArc=true }; }
    }
}
