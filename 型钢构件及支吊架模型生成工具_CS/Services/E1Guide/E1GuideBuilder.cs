using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class E1GuideBuilder
    {
        internal static IList<Element> Build(E1GuidePlan plan)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)throw new InvalidOperationException("E1 导向架需要活动三维模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var result=new List<Element>();
            double baseZ=plan.CenterZmm-plan.OutsideMm/2;
            foreach(int side in new[]{1,-1})
            {
                double ax=side*plan.AwayX,ay=side*plan.AwayY;
                double ox,oy,xx,xy,yx,yy;
                if(plan.Item.Key=="C")
                {
                    xx=ax;xy=ay;yx=plan.PipeX;yy=plan.PipeY;
                    ox=plan.CenterXmm-plan.Item.FaceWidthMm/2*plan.PipeX+plan.FaceMm*ax;
                    oy=plan.CenterYmm-plan.Item.FaceWidthMm/2*plan.PipeY+plan.FaceMm*ay;
                }
                else if(plan.Item.Key=="D" || plan.Item.Key=="E")
                {
                    xx=plan.PipeX;xy=plan.PipeY;yx=ax;yy=ay;
                    ox=plan.CenterXmm+(plan.FaceMm+plan.Item.DepthMm/2)*ax;
                    oy=plan.CenterYmm+(plan.FaceMm+plan.Item.DepthMm/2)*ay;
                }
                else
                {
                    xx=plan.PipeX;xy=plan.PipeY;yx=ax;yy=ay;
                    ox=plan.CenterXmm-plan.Item.FaceWidthMm/2*plan.PipeX+plan.FaceMm*ax;
                    oy=plan.CenterYmm-plan.Item.FaceWidthMm/2*plan.PipeY+plan.FaceMm*ay;
                }
                int direction=xx*yy-xy*yx>=0?1:-1;
                double oz=direction>0?baseZ:baseZ+plan.HeightMm;
                if(plan.Item.Key=="A")
                    result.Add(Box(ox,oy,baseZ,plan.PipeX,plan.PipeY,ax,ay,
                        plan.Item.FaceWidthMm,plan.Item.DepthMm,plan.HeightMm,scale));
                else
                    result.Add(SteelMemberFactory.Vertical(E1GuideCatalog.ProfileMode(plan.Item),
                        ox,oy,oz,xx,xy,yx,yy,plan.HeightMm,direction,scale));
                if(plan.Stainless)
                {
                    double h=plan.Item.LinerHeightMm;
                    double z0=plan.CenterZmm-h/2,z1=z0+h;
                    if(z0<baseZ){z1+=baseZ-z0;z0=baseZ;}
                    if(z1>baseZ+plan.HeightMm){z0-=z1-baseZ-plan.HeightMm;z1=baseZ+plan.HeightMm;}
                    if(z0<baseZ-0.01)throw new InvalidOperationException("薄板长度超过构件高度。");
                    double inner=plan.OutsideMm/2+3;
                    result.Add(Box(plan.CenterXmm-plan.Item.LinerWidthMm/2*plan.PipeX+inner*ax,
                        plan.CenterYmm-plan.Item.LinerWidthMm/2*plan.PipeY+inner*ay,z0,
                        plan.PipeX,plan.PipeY,ax,ay,plan.Item.LinerWidthMm,
                        plan.Item.LinerThicknessMm,z1-z0,scale));
                }
            }
            return result;
        }
        private static Element Box(double x,double y,double z,double ux,double uy,
            double vx,double vy,double width,double depth,double height,double scale)
        {
            var points=new List<DPoint3d>();
            points.Add(new DPoint3d(x*scale,y*scale,z*scale));
            points.Add(new DPoint3d((x+width*ux)*scale,(y+width*uy)*scale,z*scale));
            points.Add(new DPoint3d((x+width*ux+depth*vx)*scale,(y+width*uy+depth*vy)*scale,z*scale));
            points.Add(new DPoint3d((x+depth*vx)*scale,(y+depth*vy)*scale,z*scale));
            return SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(points,
                new DVector3d(0,0,height*scale)),7);
        }
    }
}
