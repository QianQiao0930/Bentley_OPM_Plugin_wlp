using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class SquareManholeBuilder
    {
        // Local X/Y are opening axes; Z=0 is the barrel-bottom centre.
        internal static Element Build(SquareManholePlan plan,DPoint3d origin)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("请在三维 DGN 模型中放置方形人孔。");
            double s=model.GetModelInfo().UorPerMeter/1000.0;
            if(s<=0||double.IsInfinity(s)||double.IsNaN(s))throw new InvalidOperationException("活动模型的长度单位无效。");
            var p=plan.Parameters;var parts=new List<Element>();
            var barrel=Box(-plan.BarrelOutsideWidthMm/2,-plan.BarrelOutsideDepthMm/2,0,plan.BarrelOutsideWidthMm,plan.BarrelOutsideDepthMm,p.BarrelHeightMm,s);
            SolidPrimitiveFactory.Subtract(ref barrel,new[]{Box(-p.BarrelWidthMm/2,-p.BarrelDepthMm/2,-1,p.BarrelWidthMm,p.BarrelDepthMm,p.BarrelHeightMm+2,s)},"筒体开口");
            parts.Add(SolidPrimitiveFactory.Element(barrel,uint.MaxValue));
            var cover=Box(-p.CoverWidthMm/2,-p.CoverDepthMm/2,plan.CoverBottomMm,p.CoverWidthMm,p.CoverDepthMm,p.CoverHeightMm,s);
            double skirt=p.CoverHeightMm-p.WallMm;
            if(skirt>0)SolidPrimitiveFactory.Subtract(ref cover,new[]{Box(-p.CoverWidthMm/2+p.WallMm,-p.CoverDepthMm/2+p.WallMm,plan.CoverBottomMm-1,p.CoverWidthMm-2*p.WallMm,p.CoverDepthMm-2*p.WallMm,skirt+1,s)},"盖板底部开口");
            parts.Add(SolidPrimitiveFactory.Element(cover,uint.MaxValue));
            parts.Add(Handle(150,plan.TotalHeightMm,false,1,s));parts.Add(Handle(-150,plan.TotalHeightMm,false,1,s));
            parts.Add(Handle(plan.BarrelOutsideDepthMm/2,50,true,1,s));parts.Add(Handle(-plan.BarrelOutsideDepthMm/2,50,true,-1,s));
            // Only the cell is added to the model; all six children are detached.
            var cell=new CellHeaderElement(model,"SQUARE_MANHOLE",DPoint3d.Zero,DMatrix3d.Identity,parts);
            var rotation=DTransform3d.Rotation(2,Angle.FromRadians(p.RotationDegrees*Math.PI/180));
            cell.ApplyTransform(new TransformInfo(DTransform3d.Multiply(DTransform3d.FromTranslation(origin),rotation)));
            return cell;
        }
        private static SolidKernelEntity Box(double x,double y,double z,double dx,double dy,double dz,double s)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{new DPoint3d(x*s,y*s,z*s),new DPoint3d((x+dx)*s,y*s,z*s),
                new DPoint3d((x+dx)*s,(y+dy)*s,z*s),new DPoint3d(x*s,(y+dy)*s,z*s)},new DVector3d(0,0,dz*s));
        }
        private static Element Handle(double y,double z,bool horizontal,double sign,double s)
        {
            Func<double,double,DPoint3d> point=(x,h)=>horizontal?new DPoint3d(x*s,(y+sign*h)*s,z*s):new DPoint3d(x*s,y*s,(z+h)*s);
            var a=point(-70,0);var b=point(-70,28);var c=point(-38,60);var d=point(38,60);var e=point(70,28);var f=point(70,0);
            double q=Math.Sqrt(0.5);
            var body=SolidPrimitiveFactory.RoundPath(a,horizontal?new DVector3d(0,sign,0):new DVector3d(0,0,1),8*s,
                new[]{SolidPathSegment.Line(a,b),SolidPathSegment.Arc(b,point(-70+32*(1-q),28+32*q),c),SolidPathSegment.Line(c,d),
                    SolidPathSegment.Arc(d,point(70-32*(1-q),28+32*q),e),SolidPathSegment.Line(e,f)});
            return SolidPrimitiveFactory.Element(body,uint.MaxValue);
        }
    }
}
