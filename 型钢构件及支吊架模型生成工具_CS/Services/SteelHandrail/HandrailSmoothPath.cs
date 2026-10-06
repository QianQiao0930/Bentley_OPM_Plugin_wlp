using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class HandrailSmoothPath
    {
        // 保留真实圆弧、变坡及急转边界，仅将同坡度的密集采样段合成光滑曲线。
        internal static List<List<HandrailPiece>> Runs(IList<HandrailPiece> pieces)
        {
            var runs=new List<List<HandrailPiece>>();
            foreach(var piece in pieces){
                bool split=runs.Count==0;
                if(!split){var last=runs.Last().Last();split=last.IsArc||piece.IsArc||
                    Math.Abs(last.Tangent.Z/last.Tangent.HorizontalLength-piece.Tangent.Z/piece.Tangent.HorizontalLength)>.01||
                    HandrailPoint.Dot(last.Tangent.Horizontal(),piece.Tangent.Horizontal())<Math.Cos(Math.PI/12);}
                if(split)runs.Add(new List<HandrailPiece>());runs.Last().Add(piece);
            }
            return runs;
        }
        internal static void Spline(IList<HandrailPiece> run,out List<HandrailPoint> poles,out List<double> knots)
        {
            var points=new List<HandrailPoint>{run[0].Start};points.AddRange(run.Select(p=>p.End));
            var tangents=new List<HandrailPoint>();
            for(int i=0;i<points.Count;i++){
                HandrailPoint t;
                if(i==0)t=run.Count>1?run[0].Tangent*2-run[1].Tangent:run[0].Tangent;
                else if(i==run.Count)t=run.Count>1?run.Last().Tangent*2-run[run.Count-2].Tangent:run.Last().Tangent;
                else t=run[i-1].Tangent+run[i].Tangent;tangents.Add(t.Unit());
            }
            double total=run.Sum(p=>p.Length),station=0;poles=new List<HandrailPoint>{points[0]};knots=new List<double>{0,0,0,0};
            for(int i=0;i<run.Count;i++){
                double length=run[i].Length;poles.Add(points[i]+tangents[i]*(length/3));poles.Add(points[i+1]-tangents[i+1]*(length/3));poles.Add(points[i+1]);
                station+=length;if(i<run.Count-1){double k=station/total;knots.Add(k);knots.Add(k);knots.Add(k);}
            }
            knots.AddRange(new[]{1.0,1,1,1});
        }
    }
}
