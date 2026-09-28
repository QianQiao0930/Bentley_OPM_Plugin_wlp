using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Creates the same saddle-cut tube, bore, vent and optional plates as the Python builders.</summary>
    internal static class ElbowTrunnionBuilder
    {
        internal static List<Element> Build(ElbowTrunnionPlan plan)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if (model==null || !model.Is3d) throw new InvalidOperationException("请在三维 DGN 模型中建模。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var f=plan.Selection.Frame;
            VectorMm arcStart=plan.Parameters.Elbow==ElbowOrientation.Vertical ? f.HorizontalPort : f.RunPort;
            VectorMm arcEnd=plan.Parameters.Elbow==ElbowOrientation.Vertical ? f.VerticalPort : f.OutletPort;
            VectorMm tangent=plan.Parameters.Elbow==ElbowOrientation.Vertical ? f.HorizontalDirection : f.AxisX;
            SolidKernelEntity cutter=ArcBody(arcStart,f.ArcCenter,arcEnd,tangent,
                plan.Selection.OutsideDiameterMm/2,scale);
            SolidKernelEntity tube=Cylinder(plan.TubeStartMm,plan.TubeEndMm,plan.TrunnionOdMm/2,scale);
            Subtract(ref tube,cutter,"鞍口");
            if (plan.Parameters.Hollow)
            {
                VectorMm direction=plan.Direction;
                var bore=Cylinder(plan.TubeStartMm-direction,plan.TubeEndMm+direction,
                    plan.TrunnionOdMm/2-plan.WallMm,scale);
                Subtract(ref tube,bore,"空心内孔");
            }
            Subtract(ref tube,Cylinder(plan.VentStartMm,plan.VentEndMm,3,scale),"通气孔");
            var result=new List<Element> { ConvertBody(tube) };
            if (plan.PlateThicknessMm>0)
            {
                SolidKernelEntity plate=plan.Parameters.Trunnion==TrunnionOrientation.Vertical &&
                    plan.Parameters.Plate=='A'
                    ? SquarePlate(plan.PlateStartMm,f.HorizontalDirection,plan.PlateSizeMm,
                        plan.PlateThicknessMm,scale)
                    : Cylinder(plan.PlateStartMm,plan.PlateEndMm,
                        (plan.TrunnionOdMm+25)/2,scale);
                result.Add(ConvertBody(plate));
            }
            if (plan.LinerThicknessMm>0)
            {
                SolidKernelEntity liner=plan.Parameters.Plate=='A'
                    ? SquarePlate(plan.LinerStartMm,f.HorizontalDirection,plan.PlateSizeMm,
                        plan.LinerThicknessMm,scale)
                    : Cylinder(plan.LinerStartMm,plan.LinerEndMm,
                        (plan.TrunnionOdMm+25)/2,scale);
                result.Add(ConvertBody(liner));
            }
            return result;
        }

        private static SolidKernelEntity Cylinder(VectorMm start,VectorMm end,double radiusMm,double scale)
        {
            var axis=end-start;
            if (radiusMm<=0 || axis.Length<1e-6) throw new InvalidOperationException("圆柱尺寸无效。");
            DPoint3d a=Point(start,scale),b=Point(end,scale);
            var ellipse=DEllipse3d.FromCenterRadiusNormal(a,radiusMm*scale,
                new DVector3d(axis.X,axis.Y,axis.Z));
            var profile=CurveVector.CreateDisk(ellipse,CurveVector.BoundaryType.Outer);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(a,b)));
            return Sweep(profile,path,a);
        }

        private static SolidKernelEntity ArcBody(VectorMm start,VectorMm center,VectorMm end,
            VectorMm tangent,double radiusMm,double scale)
        {
            DPoint3d a=Point(start,scale),c=Point(center,scale),b=Point(end,scale);
            DEllipse3d arc;
            if (!DEllipse3d.TryCircularArcFromCenterStartEnd(c,a,b,out arc))
                throw new InvalidOperationException("无法根据弯头两端与圆心重建 90° 弧线。");
            var profile=CurveVector.CreateDisk(
                DEllipse3d.FromCenterRadiusNormal(a,radiusMm*scale,
                    new DVector3d(tangent.X,tangent.Y,tangent.Z)),
                CurveVector.BoundaryType.Outer);
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateArc(arc));
            return Sweep(profile,path,a);
        }

        private static SolidKernelEntity SquarePlate(VectorMm basePoint,VectorMm horizontal,
            double sizeMm,double thicknessMm,double scale)
        {
            var x=new VectorMm(horizontal.X,horizontal.Y,0).Unit();
            var y=new VectorMm(-x.Y,x.X,0);
            double h=sizeMm/2;
            var corners=new[] {
                basePoint-x*h-y*h,basePoint+x*h-y*h,basePoint+x*h+y*h,
                basePoint-x*h+y*h,basePoint-x*h-y*h };
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            for(int i=0;i<4;i++)
                profile.Add(CurvePrimitive.CreateLine(
                    new DSegment3d(Point(corners[i],scale),Point(corners[i+1],scale))));
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            var end=basePoint+new VectorMm(0,0,thicknessMm);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(
                Point(basePoint,scale),Point(end,scale))));
            return Sweep(profile,path,Point(basePoint,scale));
        }

        private static SolidKernelEntity Sweep(CurveVector profile,CurveVector path,DPoint3d start)
        {
            SolidKernelEntity body;
            var status=Create.BodyFromSweep(out body,profile,path,
                Session.Instance.GetActiveDgnModelRef(),false,true,false,null,null,null,null);
            if (status!=BentleyStatus.Success || body==null)
                throw new InvalidOperationException("三维实体扫掠失败：" + status);
            return body;
        }
        private static void Subtract(ref SolidKernelEntity target,SolidKernelEntity cutter,string stage)
        {
            var tools=new[] { cutter };
            var status=Modify.BooleanSubtract(ref target,ref tools,tools.Length);
            if (status!=BentleyStatus.Success)
                throw new InvalidOperationException("三维实体" + stage + "差集失败：" + status);
        }
        private static Element ConvertBody(SolidKernelEntity body)
        {
            Element element;
            var status=Convert1.BodyToElement(out element,body,null,
                Session.Instance.GetActiveDgnModelRef());
            if (status!=BentleyStatus.Success || element==null)
                throw new InvalidOperationException("三维实体转换为 DGN 元素失败：" + status);
            return element;
        }
        private static DPoint3d Point(VectorMm p,double scale)
        {
            return new DPoint3d(p.X*scale,p.Y*scale,p.Z*scale);
        }
    }
}

