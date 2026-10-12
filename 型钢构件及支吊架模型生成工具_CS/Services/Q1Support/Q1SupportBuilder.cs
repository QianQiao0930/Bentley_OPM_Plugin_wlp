using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class Q1SupportBuilder
    {
        internal static List<Element> Build(Q1SupportPlan p,DPoint3d center,DVector3d axis)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("Q1 支撑需要三维模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000;
            double[] up,side,along;
            Q1SupportCalculator.Axes(new[]{axis.X,axis.Y,axis.Z},p.Mirrored,out along,out up,out side);
            var x=new DVector3d(along[0],along[1],along[2]);
            var y=new DVector3d(up[0],up[1],up[2]);
            var z=new DVector3d(side[0],side[1],side[2]);
            Func<double,double,double,DPoint3d> point=(xx,yy,zz)=>new DPoint3d(center.X+scale*(xx*x.X+yy*y.X+zz*z.X),
                center.Y+scale*(xx*x.Y+yy*y.Y+zz*z.Y),center.Z+scale*(xx*x.Z+yy*y.Z+zz*z.Z));
            var body=SteelMemberFactory.AlongAxisBody(Q1SupportCatalog.Mode(p),point(p.CornerXmm,p.LowMm,p.CornerZmm),
                scale,x,z,y,p.LengthMm);
            var holes=new List<SolidKernelEntity>();
            foreach(double sign in new[]{-1.0,1.0})
            {
                holes.Add(SolidPrimitiveFactory.Cylinder(point(0,sign*p.BigClamp.Row.C/2,p.CornerZmm-2),
                    point(0,sign*p.BigClamp.Row.C/2,p.CornerZmm+p.ThicknessMm+2),(p.BigClamp.Row.Bolt+2)/2.0*scale));
                if(p.Parallel)
                    holes.Add(SolidPrimitiveFactory.Cylinder(point(0,p.SmallYmm+sign*p.SmallClamp.Row.C/2,p.CornerZmm-2),
                        point(0,p.SmallYmm+sign*p.SmallClamp.Row.C/2,p.CornerZmm+p.ThicknessMm+2),(p.SmallClamp.Row.Bolt+2)/2.0*scale));
                else
                    holes.Add(SolidPrimitiveFactory.Cylinder(point(p.CornerXmm-2,p.SmallYmm+sign*p.SmallClamp.Row.C/2,p.SmallZmm),
                        point(p.CornerXmm+p.ThicknessMm+2,p.SmallYmm+sign*p.SmallClamp.Row.C/2,p.SmallZmm),(p.SmallClamp.Row.Bolt+2)/2.0*scale));
            }
            SolidPrimitiveFactory.Subtract(ref body,holes,"Q1 角钢管卡通孔");
            var result=new List<Element>{SolidPrimitiveFactory.Element(body,SupportSteelAppearance.Color)};
            Orient(p.BigClamp,x,z);result.AddRange(A1ClampBuilder.Build(p.BigClamp,center,x));
            var smallAxis=p.Parallel?x:z;
            var smallOpen=p.Parallel?z:x;
            Orient(p.SmallClamp,smallAxis,smallOpen);
            result.AddRange(A1ClampBuilder.Build(p.SmallClamp,point(p.SmallXmm,p.SmallYmm,p.SmallZmm),smallAxis));
            if(p.Parallel&&p.PadThicknessMm>0)
            {
                double h=p.PadSizeMm/2,start=p.SmallZmm+p.SmallClamp.Row.OutsideMm/2;
                var pad=new[]{point(-h,p.SmallYmm-h,start),point(h,p.SmallYmm-h,start),
                    point(h,p.SmallYmm+h,start),point(-h,p.SmallYmm+h,start)};
                result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(pad,
                    new DVector3d(z.X*p.PadThicknessMm*scale,z.Y*p.PadThicknessMm*scale,z.Z*p.PadThicknessMm*scale)),SupportSteelAppearance.Color));
            }
            return result;
        }
        private static void Orient(A1ClampPlan p,DVector3d axis,DVector3d open)
        {p.AngleDeg=A1ClampCalculator.AngleFromCursor(new[]{axis.X,axis.Y,axis.Z},new[]{open.X,open.Y,open.Z});}
    }
}
