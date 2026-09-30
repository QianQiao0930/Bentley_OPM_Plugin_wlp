using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class HandrailPathReader
    {
        internal static List<HandrailPoint> Read(ulong id)
        {
            var model=Session.Instance.GetActiveDgnModel();if(model==null||!model.Is3d)throw new InvalidOperationException("请先激活三维 DGN 模型。");
            var element=model.FindElementById(new Bentley.DgnPlatformNET.ElementId(ref id));
            if(element==null||!element.IsValid)throw new InvalidOperationException("无法读取所选辅助线。");
            var curve=CurvePathQuery.ElementToCurveVector(element);
            if(curve==null||curve.GetBoundaryType()!=CurveVector.BoundaryType.Open)throw new InvalidOperationException("请选择非闭合直线、折线或纯直线复杂链。");
            var pieces=new List<List<HandrailPoint>>();Collect(curve,1000/model.GetModelInfo().UorPerMeter,pieces);
            var points=new List<HandrailPoint>();
            foreach(var segment in pieces){if(segment.Count<2)continue;
                if(points.Count==0){points.AddRange(segment);continue;}
                var last=points[points.Count-1];
                if((last-segment[0]).Length>0.01){if((last-segment[segment.Count-1]).Length<=0.01)segment.Reverse();
                    else throw new InvalidOperationException("复杂链中的直线段不连续。");}
                for(int i=1;i<segment.Count;i++)points.Add(segment[i]);}
            return HandrailCalculator.Clean(points);
        }
        private static HandrailPoint P(DPoint3d p,double s){return new HandrailPoint(p.X*s,p.Y*s,p.Z*s);}
        private static void Collect(CurveVector curve,double scale,List<List<HandrailPoint>> result)
        {
            for(int i=0;i<curve.Count;i++){
                var primitive=curve.GetPrimitive(i);if(primitive==null)throw new InvalidOperationException("辅助线含无效段。");
                DSegment3d line;
                if(primitive.TryGetLine(out line)){DPoint3d a,b;if(!primitive.GetStartEnd(out a,out b))throw new InvalidOperationException("无法读取直线端点。");
                    if((P(b,scale)-P(a,scale)).Length>0.01)result.Add(new List<HandrailPoint>{P(a,scale),P(b,scale)});continue;}
                var list=new List<DPoint3d>();if(primitive.TryGetLineString(list)){
                    var cleaned=new List<HandrailPoint>();foreach(var q in list){var p=P(q,scale);if(cleaned.Count==0||(p-cleaned[cleaned.Count-1]).Length>0.01)cleaned.Add(p);}
                    if(cleaned.Count>=2)result.Add(cleaned);continue;}
                var child=primitive.GetChildCurveVector();if(child!=null){Collect(child,scale,result);continue;}
                throw new InvalidOperationException("路径含圆弧或曲线，请选择纯直线辅助线。");
            }
        }
    }
}
