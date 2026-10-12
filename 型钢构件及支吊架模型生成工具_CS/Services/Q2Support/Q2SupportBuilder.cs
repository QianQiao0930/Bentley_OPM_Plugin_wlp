using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class Q2SupportBuilder
    {
        internal static List<Element> Build(Q2SupportPlan p,DPoint3d center,DVector3d axis)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("Q2需要三维模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000;
            double[] xx,yy,zz;Q2SupportCalculator.Axes(new[]{axis.X,axis.Y,axis.Z},p.BigVertical,p.Mirrored,out xx,out yy,out zz,p.AngleDeg);
            var x=new DVector3d(xx[0],xx[1],xx[2]);var y=new DVector3d(yy[0],yy[1],yy[2]);var z=new DVector3d(zz[0],zz[1],zz[2]);
            Func<double,double,double,DPoint3d> point=(a,b,c)=>new DPoint3d(center.X+scale*(a*x.X+b*y.X+c*z.X),
                center.Y+scale*(a*x.Y+b*y.Y+c*z.Y),center.Z+scale*(a*x.Z+b*y.Z+c*z.Z));
            var down=new DVector3d(-z.X,-z.Y,-z.Z);var back=new DVector3d(-y.X,-y.Y,-y.Z);
            var mode=ProfileLookup.Mode(RuntimeData.Families,"equal_angle",p.ProfileName,"outer_corner");
            var body=SteelMemberFactory.AlongAxisBody(mode,point(p.StartMm,p.CornerYmm,p.TopZmm),scale,back,down,x,p.LengthMm);
            var holes=new List<SolidKernelEntity>();
            foreach(double sign in new[]{-1.0,1.0})
            {
                double a=sign*(p.BigClamp.LegSpacingMm??p.BigClamp.Row.C)/2;
                holes.Add(p.BigVertical?SolidPrimitiveFactory.Cylinder(point(a,p.CornerYmm+2,0),point(a,p.CornerYmm-p.ThicknessMm-2,0),(p.BigClamp.Row.Bolt+2)/2.0*scale):
                    SolidPrimitiveFactory.Cylinder(point(a,0,p.TopZmm+2),point(a,0,p.TopZmm-p.ThicknessMm-2),(p.BigClamp.Row.Bolt+2)/2.0*scale));
                if(p.SmallClamp!=null)foreach(double station in p.SmallStationsMm)
                    holes.Add(SolidPrimitiveFactory.Cylinder(point(station+sign*(p.SmallClamp.LegSpacingMm??p.SmallClamp.Row.C)/2,p.CornerYmm+2,p.SmallZmm),
                        point(station+sign*(p.SmallClamp.LegSpacingMm??p.SmallClamp.Row.C)/2,p.CornerYmm-p.ThicknessMm-2,p.SmallZmm),(p.SmallClamp.Row.Bolt+2)/2.0*scale));
            }
            SolidPrimitiveFactory.Subtract(ref body,holes,"Q2角钢管卡通孔");
            var parts=new List<Element>{SolidPrimitiveFactory.Element(body,SupportSteelAppearance.Color)};
            Orient(p.BigClamp,p.BigVertical?z:y,p.BigVertical?back:down);
            parts.AddRange(A1ClampBuilder.Build(p.BigClamp,center,p.BigVertical?z:y));
            if(p.SmallClamp!=null)
            {
                Orient(p.SmallClamp,z,back);
                foreach(double station in p.SmallStationsMm)
                {
                    parts.AddRange(A1ClampBuilder.Build(p.SmallClamp,point(station,p.SmallYmm,p.SmallZmm),z));
                    parts.Add(Block(point,x,z,scale,station,p.SmallYmm,p.SmallClamp.Row.OutsideMm/2,p.TopZmm,p.SmallBlockHeightMm,p.SmallBlockProjectionMm,p.SmallBlockMm[2]));
                }
            }
            return parts;
        }
        private static Element Block(Func<double,double,double,DPoint3d> point,DVector3d x,DVector3d z,double scale,
            double station,double pipeY,double radius,double top,double height,double projection,double thickness)
        {
            // 长边沿立管焊在管壁上，短边径向伸出，厚度沿切向；块底落在角钢顶面。
            double half=thickness/2,inner=pipeY-Math.Sqrt(radius*radius-half*half),outer=inner-projection;
            var outline=new[]{point(station-half,outer,top),point(station+half,outer,top),point(station+half,inner,top),point(station-half,inner,top)};
            var block=SolidPrimitiveFactory.PolygonPrism(outline,new DVector3d(z.X*height*scale,z.Y*height*scale,z.Z*height*scale));
            SolidPrimitiveFactory.Subtract(ref block,new[]{SolidPrimitiveFactory.Cylinder(point(station,pipeY,top-2),point(station,pipeY,top+height+2),radius*scale)},"Q2承重块贴管弧面");
            return SolidPrimitiveFactory.Element(block,SupportSteelAppearance.Color);
        }
        private static void Orient(A1ClampPlan p,DVector3d axis,DVector3d open)
        {p.AngleDeg=A1ClampCalculator.AngleFromCursor(new[]{axis.X,axis.Y,axis.Z},new[]{open.X,open.Y,open.Z});}
    }
}
