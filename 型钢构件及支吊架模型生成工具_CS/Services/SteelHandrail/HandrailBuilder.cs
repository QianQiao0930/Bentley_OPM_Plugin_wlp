using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal sealed class HandrailBuilder
    {
        private readonly DgnModel model;
        private readonly double scale;
        private readonly HandrailPoint origin;
        private readonly uint color;
        private readonly List<Element> parts=new List<Element>();
        private HandrailBuilder(HandrailPlan plan)
        {
            model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("围栏需要三维活动 DGN 模型。");
            scale=model.GetModelInfo().UorPerMeter/1000.0;origin=plan.Origin;
            color=DgnColorMap.CreateElementColor(new RgbColorDef(255,204,0),null,null,Session.Instance.GetActiveDgnFile());
        }
        private DPoint3d P(HandrailPoint p){return new DPoint3d((origin.X+p.X)*scale,(origin.Y+p.Y)*scale,(origin.Z+p.Z)*scale);}
        private DVector3d V(HandrailPoint v){return new DVector3d(v.X*scale,v.Y*scale,v.Z*scale);}
        private void Add(SolidKernelEntity body){parts.Add(SolidPrimitiveFactory.Element(body,color));}
        private static HandrailPoint Z(double z){return HandrailPoint.Up*z;}
        private void Tube(HandrailPoint a,HandrailPoint b,double od)
        {
            var axis=(b-a).Unit();
            var body=SolidPrimitiveFactory.Cylinder(P(a),P(b),od/2*scale);
            var inner=SolidPrimitiveFactory.Cylinder(P(a-axis*2),P(b+axis*2),(od/2-3.2)*scale);
            SolidPrimitiveFactory.Subtract(ref body,new[]{inner},"围栏空心钢管");Add(body);
        }
        private void ArcTube(HandrailPoint center,HandrailPoint radial,HandrailPoint tangent,double radius,double angle,double od)
        {
            Func<double,HandrailPoint> at=a=>center+(radial*Math.Cos(a)+tangent*Math.Sin(a))*radius;
            var path=new[]{SolidPathSegment.Arc(P(at(0)),P(at(angle/2)),P(at(angle)))};
            var body=SolidPrimitiveFactory.RoundPath(P(at(0)),V(tangent),od/2*scale,path);
            var inner=SolidPrimitiveFactory.RoundPath(P(at(0)),V(tangent),(od/2-3.2)*scale,path);
            SolidPrimitiveFactory.Subtract(ref body,new[]{inner},"围栏空心弯管");Add(body);
        }
        private void Plate(HandrailPoint center,HandrailPoint x,HandrailPoint y,HandrailPoint normal,double width,double height,double thickness)
        {
            var a=center-normal*(thickness/2);
            Add(SolidPrimitiveFactory.PolygonPrism(new[]{P(a-x*(width/2)-y*(height/2)),P(a+x*(width/2)-y*(height/2)),
                P(a+x*(width/2)+y*(height/2)),P(a-x*(width/2)+y*(height/2))},V(normal*thickness)));
        }
        private void Ball(HandrailPoint point)
        {
            var primitive=SolidPrimitive.CreateDgnSphere(new DgnSphereDetail(P(point),38*scale));
            var element=DraftingElementSchema.ToElement(model,primitive,null);
            if(element==null)throw new InvalidOperationException("围栏连接球创建失败。");
            var style=new ElementPropertiesSetter();style.SetColor(color);
            if(!style.Apply(element))throw new InvalidOperationException("围栏连接球颜色设置失败。");parts.Add(element);
        }
        private SolidKernelEntity Loft(IList<HandrailSection> sections,HandrailPoint along,HandrailPoint normal)
        {
            var profiles=new CurveVector[sections.Count];
            for(int i=0;i<sections.Count;i++){
                var s=sections[i];profiles[i]=CurveVector.Create(CurveVector.BoundaryType.Outer);
                profiles[i].Add(CurvePrimitive.CreateArc(new DEllipse3d(P(s.Center),V(along*s.Major),V(normal*s.Minor),Angle.FromRadians(0),Angle.FromRadians(2*Math.PI))));
            }
            SolidKernelEntity body;
            var status=Create.BodyFromLoft(out body,profiles,profiles.Length,new CurveVector[0],0,
                Session.Instance.GetActiveDgnModelRef(),false,true);
            if(status!=BentleyStatus.Success||body==null)throw new InvalidOperationException("类型 1 圆管至椭圆压扁端放样失败："+status);
            return body;
        }
        private void Flatten(HandrailNode node)
        {
            var along=node.Tangent.Horizontal();var outer=Loft(node.Sections,along,node.Normal);
            var inner=node.Sections.Select(s=>new HandrailSection(s.Center,s.Major-3.2,s.Minor-3.2)).ToList();
            var first=inner[0];var last=inner[inner.Count-1];
            inner.Insert(0,new HandrailSection(first.Center+Z(2),first.Major,first.Minor));
            inner.Add(new HandrailSection(last.Center-Z(2),last.Major,last.Minor));
            var cavity=Loft(inner,along,node.Normal);SolidPrimitiveFactory.Subtract(ref outer,new[]{cavity},"类型 1 压扁端内腔");Add(outer);
        }
        private CurveVector Path(IList<HandrailPiece> pieces,double height)
        {
            var path=CurveVector.Create(CurveVector.BoundaryType.Open);
            foreach(var p in pieces){if(!p.IsArc)path.Add(CurvePrimitive.CreateLine(new DSegment3d(P(p.Start+Z(height)),P(p.End+Z(height)))));
                else path.Add(CurvePrimitive.CreateArc(new DEllipse3d(P(p.Center+Z(height)),V(p.Radial*p.Radius),V(p.Tangent*p.Radius),Angle.FromRadians(0),Angle.FromRadians(p.Angle))));}
            return path;
        }
        private void Kickplate(IList<HandrailPiece> pieces)
        {
            var first=pieces[0];var normal=first.Tangent.Normal(1);var start=first.Start;
            var corners=new[]{start-normal*3+Z(10),start+normal*3+Z(10),start+normal*3+Z(140),start-normal*3+Z(140)};
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            for(int i=0;i<4;i++)profile.Add(CurvePrimitive.CreateLine(new DSegment3d(P(corners[i]),P(corners[(i+1)%4]))));
            SolidKernelEntity body;
            var status=Create.BodyFromSweep(out body,profile,Path(pieces,75),Session.Instance.GetActiveDgnModelRef(),
                false,true,false,new DVector3d(0,0,1),null,null,null);
            if(status!=BentleyStatus.Success||body==null)throw new InvalidOperationException("连续踢脚板扫掠失败："+status);Add(body);
        }
        private void Post(HandrailPoint point,HandrailPoint tangent,HandrailParameters parameters)
        {
            var node=HandrailCalculator.Node(point,tangent,parameters);
            Tube(parameters.Connection==HandrailConnection.Type3?node.Bottom:point,point+Z(1017),48.3);
            Ball(point+Z(560));Ball(point+Z(1017));
            // 立柱外壁伸入 2 mm，另一端延伸至踢脚板外表面。
            var t=tangent.Horizontal();var n=node.Normal;
            Plate(point+n*((22.15+40.15)/2)+Z(75),n,HandrailPoint.Up,t,18,50,6);
            if(parameters.Connection==HandrailConnection.Type1){Flatten(node);Plate(node.PlateCenter,node.PlateLong,node.PlateShort,n,146,75,10);}
            else if(parameters.Connection==HandrailConnection.Type2){ArcTube(node.ElbowCenter,n*(-1),HandrailPoint.Up*(-1),76,Math.PI/2,48.3);
                Tube(node.ElbowEnd,node.TubeEnd,48.3);Plate(node.PlateCenter,node.PlateLong,node.PlateShort,n,146,75,10);}
            else if(parameters.Connection==HandrailConnection.Type3)Plate(point+Z(5),t,t.Normal(1),HandrailPoint.Up,145,75,10);
        }
        private void Closure(HandrailPoint endpoint,HandrailPoint tangent,int direction)
        {
            var t=tangent.Horizontal()*direction;var straight=endpoint+t*160;
            Tube(endpoint+Z(1017),straight+Z(1017),42.4);Tube(endpoint+Z(560),straight+Z(560),42.4);
            ArcTube(straight+Z(877),HandrailPoint.Up,t,140,Math.PI/2,42.4);
            var outside=endpoint+t*300;Tube(outside+Z(877),outside+Z(700),42.4);
            ArcTube(straight+Z(700),t,HandrailPoint.Up*(-1),140,Math.PI/2,42.4);
        }
        internal static List<Element> Build(HandrailPlan plan)
        {
            if(plan==null)throw new ArgumentNullException("plan");var b=new HandrailBuilder(plan);
            foreach(var p in plan.Pieces)foreach(double height in new[]{1017.0,560.0}){
                double od=height==1017?42.4:33.7;
                if(p.IsArc)b.ArcTube(p.Center+Z(height),p.Radial,p.Tangent,p.Radius,p.Angle,od);
                else b.Tube(p.Start+Z(height),p.End+Z(height),od);
            }
            foreach(double station in plan.Stations){HandrailPoint point,tangent;HandrailCalculator.At(plan.Pieces,station,out point,out tangent);b.Post(point,tangent,plan.Parameters);}
            b.Kickplate(plan.Kickplate);
            foreach(int end in new[]{-1,1})if(plan.Parameters.Closure==HandrailClosure.Both||
                end==-1&&plan.Parameters.Closure==HandrailClosure.Start||end==1&&plan.Parameters.Closure==HandrailClosure.End){
                HandrailPoint point,tangent;HandrailCalculator.At(plan.Pieces,end==-1?0:plan.LengthMm,out point,out tangent);b.Closure(point,tangent,end);}
            return b.parts;
        }
    }
}
