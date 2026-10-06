using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class HandrailPathReader
    {
        internal static List<HandrailPoint> Read(ulong id,out HandrailArcInput arcInput)
        {
            arcInput=null;
            var model=Session.Instance.GetActiveDgnModel();if(model==null||!model.Is3d)throw new InvalidOperationException("请先激活三维 DGN 模型。");
            var element=model.FindElementById(new Bentley.DgnPlatformNET.ElementId(ref id));
            if(element==null||!element.IsValid)throw new InvalidOperationException("无法读取所选辅助线。");
            var curve=CurvePathQuery.ElementToCurveVector(element);
            if(curve!=null&&curve.Count==1&&curve.GetPrimitive(0).GetBsplineCurve()!=null)
            {
                var samples=new List<HandrailPoint>();double scale=1000/model.GetModelInfo().UorPerMeter;
                for(int i=0;i<=4096;i++){DPoint3d point;
                    if(!curve.GetPrimitive(0).FractionToPoint(i/4096.0,out point))throw new InvalidOperationException("螺旋样条求值失败。");
                    samples.Add(P(point,scale));}
                arcInput=HandrailHelixCalculator.Fit(samples);return new List<HandrailPoint>();
            }
            DEllipse3d arc;
            if(curve!=null&&curve.Count==1&&curve.GetPrimitive(0).TryGetArc(out arc))
            {
                double s=1000/model.GetModelInfo().UorPerMeter;
                arcInput=new HandrailArcInput{Center=P(arc.Center,s),
                    Vector0=new HandrailPoint(arc.Vector0.X*s,arc.Vector0.Y*s,arc.Vector0.Z*s),
                    Vector90=new HandrailPoint(arc.Vector90.X*s,arc.Vector90.Y*s,arc.Vector90.Z*s),
                    StartAngle=arc.StartAngle.Radians,SweepAngle=arc.SweepAngle.Radians};
                return new List<HandrailPoint>();
            }
            if(curve==null||curve.GetBoundaryType()!=CurveVector.BoundaryType.Open)throw new InvalidOperationException("请选择非闭合直线、折线或纯直线复杂链。");
            var pieces=new List<List<HandrailPoint>>();bool sampled=false;Collect(curve,1000/model.GetModelInfo().UorPerMeter,pieces,ref sampled);
            var points=new List<HandrailPoint>();
            foreach(var segment in pieces){if(segment.Count<2)continue;
                if(points.Count==0){points.AddRange(segment);continue;}
                var last=points[points.Count-1];
                if((last-segment[0]).Length>0.01){if((last-segment[segment.Count-1]).Length<=0.01)segment.Reverse();
                    else throw new InvalidOperationException("复杂链中的直线段不连续。");}
                for(int i=1;i<segment.Count;i++)points.Add(segment[i]);}
            bool mixed=sampled||HasSpatialTurn(points);
            points=HandrailCalculator.Clean(points,mixed);
            if(mixed){
                arcInput=new HandrailArcInput{MixedPoints=points};return new List<HandrailPoint>();}
            return points;
        }
        private static bool HasSpatialTurn(IList<HandrailPoint> points)
        {
            for(int i=1;i<points.Count-1;i++){var a=points[i]-points[i-1];var b=points[i+1]-points[i];
                var u=a.Horizontal();var v=b.Horizontal();
                if(Math.Abs(u.X*v.Y-u.Y*v.X)>1e-7&&(Math.Abs(a.Z)>1e-7||Math.Abs(b.Z)>1e-7))return true;}
            return false;
        }
        private static HandrailPoint P(DPoint3d p,double s){return new HandrailPoint(p.X*s,p.Y*s,p.Z*s);}
        private static void Collect(CurveVector curve,double scale,List<List<HandrailPoint>> result,ref bool sampled)
        {
            for(int i=0;i<curve.Count;i++){
                var primitive=curve.GetPrimitive(i);if(primitive==null)throw new InvalidOperationException("辅助线含无效段。");
                DSegment3d line;
                if(primitive.TryGetLine(out line)){DPoint3d a,b;if(!primitive.GetStartEnd(out a,out b))throw new InvalidOperationException("无法读取直线端点。");
                    if((P(b,scale)-P(a,scale)).Length>0.01)result.Add(new List<HandrailPoint>{P(a,scale),P(b,scale)});continue;}
                var list=new List<DPoint3d>();if(primitive.TryGetLineString(list)){
                    var cleaned=new List<HandrailPoint>();foreach(var q in list){var p=P(q,scale);if(cleaned.Count==0||(p-cleaned[cleaned.Count-1]).Length>0.01)cleaned.Add(p);}
                    if(cleaned.Count>=2)result.Add(cleaned);continue;}
                var child=primitive.GetChildCurveVector();if(child!=null){Collect(child,scale,result,ref sampled);continue;}
                DEllipse3d arc;double angle,radius;
                if(primitive.TryGetArc(out arc)){
                    if(Math.Abs(arc.Vector0.Z*scale)>.01||Math.Abs(arc.Vector90.Z*scale)>.01)
                        throw new InvalidOperationException("混合路径中的圆弧必须水平。");
                    var u=new HandrailPoint(arc.Vector0.X*scale,arc.Vector0.Y*scale,arc.Vector0.Z*scale);
                    var v=new HandrailPoint(arc.Vector90.X*scale,arc.Vector90.Y*scale,arc.Vector90.Z*scale);
                    radius=u.Length;angle=Math.Abs(arc.SweepAngle.Radians);
                    if(radius<=.01||Math.Abs(v.Length-radius)>.01||Math.Abs(HandrailPoint.Dot(u,v))>.01*radius)
                        throw new InvalidOperationException("混合路径不支持椭圆段。");
                }else if(primitive.GetBsplineCurve()!=null){
                    var values=new List<HandrailPoint>();
                    for(int j=0;j<=4096;j++){DPoint3d value;if(!primitive.FractionToPoint(j/4096.0,out value))throw new InvalidOperationException("混合路径螺旋样条求值失败。");values.Add(P(value,scale));}
                    var helix=HandrailHelixCalculator.Fit(values);radius=helix.Vector0.Length;angle=Math.Abs(helix.SweepAngle);
                }else throw new InvalidOperationException("混合路径只支持直线、线串、水平圆弧和固定半径螺距螺旋样条。");
                int count=Math.Max(32,(int)Math.Ceiling(angle/Math.Min(.025,Math.Sqrt(2/radius))));
                if(count>8192)throw new InvalidOperationException("混合曲线段过长，请拆分路径。");
                var samples=new List<HandrailPoint>();
                for(int j=0;j<=count;j++){DPoint3d value;if(!primitive.FractionToPoint(j/(double)count,out value))throw new InvalidOperationException("混合曲线求值失败。");samples.Add(P(value,scale));}
                result.Add(samples);sampled=true;
            }
        }
    }
}
