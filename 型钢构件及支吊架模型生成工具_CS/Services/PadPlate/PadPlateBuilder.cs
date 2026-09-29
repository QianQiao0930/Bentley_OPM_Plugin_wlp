using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class PadPlateBuilder
    {
        internal static IList<Element> Build(PadPlatePlan plan)
        {
            if(plan==null)throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("垫板需要三维活动模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000;
            VectorMm origin,ex,ey,ez;
            CurveVector path=CurveVector.Create(CurveVector.BoundaryType.Open);
            if(plan.Kind==PadPlateKind.Y2)
            {
                ex=plan.Axis.Unit();ey=Cross(new VectorMm(0,0,1),ex).Unit();
                ez=Cross(ex,ey).Unit();
                origin=plan.Center-ex*(plan.LengthMm/2);
                path.Add(CurvePrimitive.CreateLine(new DSegment3d(P(origin,scale),P(origin+ex*plan.LengthMm,scale))));
            }
            else
            {
                double start=45-plan.CoverageDeg/2,end=45+plan.CoverageDeg/2;
                VectorMm center=plan.Origin+plan.AxisZ*plan.BendRadiusMm;
                Func<double,VectorMm> outward=t=>plan.AxisX*Math.Sin(t*Math.PI/180)-plan.AxisZ*Math.Cos(t*Math.PI/180);
                Func<double,VectorMm> point=t=>center+outward(t)*plan.BendRadiusMm;
                origin=point(start);ex=(plan.AxisZ*Math.Sin(start*Math.PI/180)+plan.AxisX*Math.Cos(start*Math.PI/180)).Unit();
                ez=outward(start)*-1;ey=Cross(ez,ex).Unit();
                DEllipse3d arc;
                if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(P(point(start),scale),P(point(45),scale),P(point(end),scale),out arc))
                    throw new InvalidOperationException("弯头垫板圆弧路径无效。");
                path.Add(CurvePrimitive.CreateArc(arc));
            }
            var profile=Profile(plan,origin,ey,ez,scale);
            var body=SolidPrimitiveFactory.Sweep(profile,path);
            if(plan.VentHole)
            {
                VectorMm inner,outer;
                if(plan.Kind==PadPlateKind.Y2)
                {outer=plan.Center-ez*(plan.OuterRadiusMm+1);inner=plan.Center-ez*(plan.InnerRadiusMm-1);}
                else
                {
                    VectorMm outward=plan.AxisX*Math.Sin(Math.PI/4)-plan.AxisZ*Math.Cos(Math.PI/4);
                    VectorMm middle=plan.Origin+plan.AxisZ*plan.BendRadiusMm+outward*plan.BendRadiusMm;
                    outer=middle+outward*(plan.OuterRadiusMm+1);
                    inner=middle+outward*(plan.InnerRadiusMm-1);
                }
                try
                {
                    var hole=SolidPrimitiveFactory.Cylinder(P(outer,scale),P(inner,scale),3*scale);
                    SolidPrimitiveFactory.Subtract(ref body,new[]{hole},"垫板气孔");
                }
                catch(InvalidOperationException){/* 与 Python 一致：通气孔失败仍保留垫板实体。 */}
            }
            return new[]{SolidPrimitiveFactory.Element(body,7)};
        }
        private static CurveVector Profile(PadPlatePlan plan,VectorMm origin,VectorMm ey,VectorMm ez,double scale)
        {
            double half=plan.AlphaDeg*Math.PI/360;
            Func<double,double,DPoint3d> polar=(r,angle)=>P(origin+ey*(r*Math.Sin(angle))-ez*(r*Math.Cos(angle)),scale);
            double ri=plan.InnerRadiusMm,ro=plan.OuterRadiusMm;
            var innerStart=polar(ri,-half);var innerMid=polar(ri,0);var innerEnd=polar(ri,half);
            var outerStart=polar(ro,-half);var outerMid=polar(ro,0);var outerEnd=polar(ro,half);
            DEllipse3d inner,outer;
            if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(innerStart,innerMid,innerEnd,out inner)||
                !DEllipse3d.TryCircularArcFromStartMiddleEnd(outerEnd,outerMid,outerStart,out outer))
                throw new InvalidOperationException("垫板圆弧截面无效。");
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            profile.Add(CurvePrimitive.CreateArc(inner));
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(innerEnd,outerEnd)));
            profile.Add(CurvePrimitive.CreateArc(outer));
            profile.Add(CurvePrimitive.CreateLine(new DSegment3d(outerStart,innerStart)));
            return profile;
        }
        private static VectorMm Cross(VectorMm a,VectorMm b)
        {return new VectorMm(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);}
        private static DPoint3d P(VectorMm p,double s){return new DPoint3d(p.X*s,p.Y*s,p.Z*s);}
    }
}
