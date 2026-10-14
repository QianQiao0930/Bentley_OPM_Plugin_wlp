using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    internal sealed class WallLadderSelection
    {
        internal WallLadderPoint BasePointMm;
        internal double HeightMm;
        internal static WallLadderSelection FromPoints(IList<WallLadderPoint> points)
        {
            if(points==null||points.Count<2)throw new InvalidOperationException("请选择一条竖直线。");
            var a=points[0];var b=points[points.Count-1];
            foreach(var p in points)
            {
                if(double.IsNaN(p.X)||double.IsNaN(p.Y)||double.IsNaN(p.Z)||double.IsInfinity(p.X)||double.IsInfinity(p.Y)||double.IsInfinity(p.Z))throw new InvalidOperationException("辅助线坐标无效。");
                if(Math.Sqrt((p.X-a.X)*(p.X-a.X)+(p.Y-a.Y)*(p.Y-a.Y))>WallLadderCatalog.VerticalToleranceMm)
                    throw new InvalidOperationException("请选择竖直线，水平偏差不得超过5 mm。");
            }
            double h=Math.Abs(b.Z-a.Z);
            if(h<=1e-6||h>WallLadderCatalog.MaxHeightMm)throw new InvalidOperationException("竖直线高度须大于0且不超过6000 mm。");
            return new WallLadderSelection { BasePointMm=a.Z<b.Z?a:b,HeightMm=h };
        }
    }
}
