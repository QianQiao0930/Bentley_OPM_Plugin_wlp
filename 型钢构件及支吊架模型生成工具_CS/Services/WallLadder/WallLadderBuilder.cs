using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class WallLadderBuilder
    {
        internal static Element[] Build(WallLadderPlan plan,WallLadderPoint originMm)
        {
            if(plan==null)throw new ArgumentNullException("plan");
            if(double.IsNaN(originMm.X)||double.IsNaN(originMm.Y)||double.IsNaN(originMm.Z)||double.IsInfinity(originMm.X)||double.IsInfinity(originMm.Y)||double.IsInfinity(originMm.Z))
                throw new InvalidOperationException("墙面爬梯放置坐标无效。");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("墙面爬梯需要三维活动模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000;
            if(scale<=0||double.IsNaN(scale)||double.IsInfinity(scale))throw new InvalidOperationException("模型单位无效。");
            uint color=DgnColorMap.CreateElementColor(new RgbColorDef(255,204,0),null,null,Session.Instance.GetActiveDgnFile());
            var cells=new List<Element>();
            cells.Add(Cell(plan.LadderParts,WallLadderCatalog.LadderCell));
            if(plan.CageParts.Length>0)cells.Add(Cell(plan.CageParts,WallLadderCatalog.CageCell));
            var rotate=DTransform3d.Rotation(2,Angle.FromRadians(plan.Parameters.HeadingDegrees*Math.PI/180));
            var transform=new TransformInfo(DTransform3d.Multiply(DTransform3d.FromTranslation(P(originMm,scale)),rotate));
            foreach(var cell in cells)cell.ApplyTransform(transform);
            return cells.ToArray();

            Element Cell(WallLadderPart[] parts,string name)
            {
                var children=new List<Element>();
                for(int i=0;i<parts.Length;i++)
                {
                    try { children.Add(SolidPrimitiveFactory.Element(Body(parts[i],scale),color)); }
                    catch(Exception ex){throw new InvalidOperationException(name+" 第"+(i+1)+"个构件构造失败："+ex.Message,ex);}
                }
                // Detached child elements and cells: only PreviewSession writes the two complete groups.
                return new CellHeaderElement(model,name,DPoint3d.Zero,DMatrix3d.Identity,children);
            }
        }
        private static SolidKernelEntity Body(WallLadderPart p,double scale)
        {
            if(p.Kind==WallLadderPartKind.Box)
            {
                var at=p.Center-p.W*(p.Size.Z/2);
                return SolidPrimitiveFactory.PolygonPrism(Corners(at,p.U,p.V,p.Size.X,p.Size.Y,scale),V(p.W*p.Size.Z,scale));
            }
            if(p.Kind==WallLadderPartKind.Cylinder)
                return SolidPrimitiveFactory.Cylinder(P(p.Center-p.W*(p.Size.Z/2),scale),P(p.Center+p.W*(p.Size.Z/2),scale),p.Size.X/2*scale);
            if(p.Kind==WallLadderPartKind.Angle)
            {
                var mode=ProfileLookup.Mode(RuntimeData.Families,"equal_angle",WallLadderCatalog.AngleProfile,"outer_corner");
                return SteelMemberFactory.AlongAxisBody(mode,P(p.Center,scale),scale,V(p.U,1),V(p.V,1),V(p.W,1),p.Size.Z);
            }
            return FlatSweep(p,scale);
        }
        private static SolidKernelEntity FlatSweep(WallLadderPart part,double scale)
        {
            string last="";
            // Reversing and changing a reference direction preserves exact geometry. No faceted/chord fallback.
            for(int reverse=0;reverse<2;reverse++)
            {
                var segments=reverse==0?part.Path:part.Path.Reverse().Select(s=>s.Reversed()).ToArray();
                var tangent=(segments[0].End-segments[0].Start).Unit();
                WallLadderPoint width,thickness;
                if(part.Spatial)
                {
                    thickness=Math.Abs(tangent.Z)>.999?new WallLadderPoint(0,1,0):new WallLadderPoint(tangent.Y,-tangent.X,0).Unit();
                    width=WallLadderPoint.Cross(thickness,tangent).Unit();
                }
                else {width=new WallLadderPoint(0,0,1);thickness=new WallLadderPoint(tangent.Y,-tangent.X,0).Unit();}
                var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
                var corners=Corners(segments[0].Start,width,thickness,part.Size.X,part.Size.Y,scale);
                for(int i=0;i<4;i++)profile.Add(CurvePrimitive.CreateLine(new DSegment3d(corners[i],corners[(i+1)%4])));
                var path=CurveVector.Create(CurveVector.BoundaryType.Open);
                foreach(var s in segments)
                {
                    if(s.IsArc)
                    {
                        DEllipse3d arc;
                        if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(P(s.Start,scale),P(s.Middle,scale),P(s.End,scale),out arc))
                            throw new InvalidOperationException("R355真实圆弧路径无效。");
                        path.Add(CurvePrimitive.CreateArc(arc));
                    }
                    else path.Add(CurvePrimitive.CreateLine(new DSegment3d(P(s.Start,scale),P(s.End,scale))));
                }
                var primary=part.Spatial?width:thickness;
                foreach(ValueType direction in new ValueType[]{null,V(primary,1),new DVector3d(0,0,1),new DVector3d(1,0,0),new DVector3d(0,1,0)})
                {
                    try
                    {
                        SolidKernelEntity body;
                        var status=Create.BodyFromSweep(out body,profile,path,Session.Instance.GetActiveDgnModelRef(),false,true,false,direction,null,null,null);
                        if(status==BentleyStatus.Success&&body!=null)return body;
                        last=status.ToString();
                    }
                    catch(Exception ex){last=ex.GetType().Name+"："+ex.Message;}
                }
            }
            throw new InvalidOperationException((part.Spatial?"顶部倒L与护笼组合":"护笼环")+"真实曲线扫掠失败："+last+"。请检查路径与模型单位。");
        }
        private static DPoint3d[] Corners(WallLadderPoint center,WallLadderPoint u,WallLadderPoint v,double width,double thickness,double scale)
        {return new[]{P(center-u*(width/2)-v*(thickness/2),scale),P(center+u*(width/2)-v*(thickness/2),scale),P(center+u*(width/2)+v*(thickness/2),scale),P(center-u*(width/2)+v*(thickness/2),scale)};}
        private static DPoint3d P(WallLadderPoint p,double scale){return new DPoint3d(p.X*scale,p.Y*scale,p.Z*scale);}
        private static DVector3d V(WallLadderPoint p,double scale){return new DVector3d(p.X*scale,p.Y*scale,p.Z*scale);}
    }
}
