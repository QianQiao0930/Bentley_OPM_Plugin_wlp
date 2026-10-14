using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class WallLadderReader
    {
        internal static WallLadderSelection Read(LocatedElement located)
        {
            if(located==null)throw new ArgumentNullException("located");
            var active=Session.Instance.GetActiveDgnModel();
            if(active==null||!active.Is3d)throw new InvalidOperationException("请激活三维模型。");
            var model=located.ModelRef==null?active:located.ModelRef.GetDgnModel();
            ulong id=located.ElementId;
            var element=model==null?null:model.FindElementById(new ElementId(ref id));
            if(element==null||!element.IsValid)throw new InvalidOperationException("辅助线已失效。");
            var curve=CurvePathQuery.ElementToCurveVector(element);
            if(curve==null||curve.GetBoundaryType()!=CurveVector.BoundaryType.Open)throw new InvalidOperationException("请选择开放的单条竖直线。");
            var pieces=new List<List<DPoint3d>>();Collect(curve,pieces);
            if(pieces.Count!=1)throw new InvalidOperationException("请选择单条竖直线，不要选折线或复杂链。");
            var points=pieces[0];
            if(located.IsFromReference())
            {
                var attachment=located.ModelRef.AsDgnAttachment();
                if(attachment==null)throw new InvalidOperationException("参考线缺少附件坐标关系。");
                int depth=0;
                while(attachment!=null)
                {
                    if(++depth>32)throw new InvalidOperationException("参考附件嵌套过深。");
                    DTransform3d transform;attachment.GetTransformToParent(out transform,true);
                    for(int i=0;i<points.Count;i++){var p=points[i];points[i]=transform.MultiplyPoint(p.X,p.Y,p.Z);}
                    attachment=attachment.GetParentDgnAttachment();
                }
            }
            double scale=1000/active.GetModelInfo().UorPerMeter;
            if(scale<=0||double.IsNaN(scale)||double.IsInfinity(scale))throw new InvalidOperationException("模型单位无效。");
            var mm=new List<WallLadderPoint>();foreach(var p in points)mm.Add(new WallLadderPoint(p.X*scale,p.Y*scale,p.Z*scale));
            return WallLadderSelection.FromPoints(mm);
        }
        private static void Collect(CurveVector cv,List<List<DPoint3d>> pieces)
        {
            for(int i=0;i<cv.Count;i++)
            {
                var p=cv.GetPrimitive(i);DSegment3d line;DPoint3d a,b;
                if(p.TryGetLine(out line)&&p.GetStartEnd(out a,out b)){pieces.Add(new List<DPoint3d>{a,b});continue;}
                var list=new List<DPoint3d>();if(p.TryGetLineString(list)){pieces.Add(list);continue;}
                var child=p.GetChildCurveVector();if(child!=null){Collect(child,pieces);continue;}
                throw new InvalidOperationException("所选辅助线含圆弧或曲线，请选择竖直线。");
            }
        }
    }
}
