using System;
namespace SteelSectionProbe
{
    internal static class NozzleCalculator
    {
        internal static NozzlePlan Calculate(NozzleParameters p)
        {
            if(p==null) throw new InvalidOperationException("缺少管口参数。");
            if(p.Axis!="+X" && p.Axis!="-X" && p.Axis!="+Y" && p.Axis!="-Y" &&
                p.Axis!="+Z" && p.Axis!="-Z") throw new InvalidOperationException("放置方向无效。");
            var size=NozzleCatalog.Get(p.Rating,p.PipeSchedule,p.NominalDn);
            double wall=p.WallOverrideMm.HasValue?p.WallOverrideMm.Value:size.PipeWallMm;
            if(double.IsNaN(wall) || double.IsInfinity(wall) || wall<=0 || wall*2>=size.PipeOutsideMm)
                throw new InvalidOperationException("壁厚必须大于 0 且小于钢管外径的一半。");
            if(double.IsNaN(p.TotalLengthMm) || double.IsInfinity(p.TotalLengthMm) ||
                p.TotalLengthMm<=size.FlangeThicknessMm || p.TotalLengthMm>100000)
                throw new InvalidOperationException("管口总长度必须大于法兰厚度，且不超过 100000 mm。");
            if(size.BoltCount<0 || size.BoltHoleMm<0 || size.BoltCircleMm<0 ||
                size.BoltCircleMm/2+size.BoltHoleMm/2>=size.FlangeOutsideMm/2)
                throw new InvalidOperationException("法兰螺栓孔尺寸超出法兰边缘。");
            return new NozzlePlan { Parameters=p,Size=size,WallMm=wall,
                PipeLengthMm=p.TotalLengthMm-size.FlangeThicknessMm,
                BoreRadiusMm=size.PipeOutsideMm/2-wall };
        }
        internal static double[] BoltOffset(int index,int count,double circleRadius)
        {
            if(count<=0 || index<0 || index>=count) throw new InvalidOperationException("螺栓序号无效。");
            double angle=2*Math.PI*index/count;
            return new[]{circleRadius*Math.Cos(angle),circleRadius*Math.Sin(angle)};
        }
    }
}
