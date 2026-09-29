using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class LBracketReader
    {
        internal static LBracketSelection Read(DgnModelRef modelRef,ulong id)
        {
            var model=ComponentPropertyReader.ResolveModel(modelRef);
            if(model==null||!model.Is3d)throw new InvalidOperationException("请选择三维活动模型。");
            var element=model.FindElementById(new ElementId(ref id));
            if(element==null||!element.IsValid)throw new InvalidOperationException("无法读取所选折线。");
            var curve=CurvePathQuery.ElementToCurveVector(element);
            if(curve==null||curve.GetBoundaryType()!=CurveVector.BoundaryType.Open)
                throw new InvalidOperationException("请选择一条开放的 L 形辅助折线。");
            double mmPerUor=1000.0/model.GetModelInfo().UorPerMeter;
            var segments=new List<LBracketPoint[]>();
            Collect(curve,mmPerUor,segments);
            var selected=LBracketShapeParser.Parse(segments);
            selected.ElementId=id;
            selected.IsFromReference=modelRef!=null&&
                !ReferenceEquals(model,Session.Instance.GetActiveDgnModel());
            return selected;
        }
        private static void Collect(CurveVector curve,double scale,IList<LBracketPoint[]> result)
        {
            for(int i=0;i<curve.Count;i++)
            {
                var primitive=curve.GetPrimitive(i);
                if(primitive==null)throw new InvalidOperationException("折线含无效段。");
                DSegment3d line;
                if(primitive.TryGetLine(out line))
                {
                    DPoint3d a,b;
                    if(!primitive.GetStartEnd(out a,out b))throw new InvalidOperationException("直线端点无法读取。");
                    result.Add(new[]{P(a,scale),P(b,scale)});continue;
                }
                var points=new List<DPoint3d>();
                if(primitive.TryGetLineString(points))
                {
                    for(int j=1;j<points.Count;j++)
                        result.Add(new[]{P(points[j-1],scale),P(points[j],scale)});
                    continue;
                }
                var child=primitive.GetChildCurveVector();
                if(child!=null){Collect(child,scale,result);continue;}
                throw new InvalidOperationException("L 形辅助折线只能包含直线段。");
            }
        }
        private static LBracketPoint P(DPoint3d p,double scale)
        {return new LBracketPoint(p.X*scale,p.Y*scale,p.Z*scale);}
    }
}
