using System;

namespace SteelSectionProbe
{
    internal static class VerticalPipeSupportPositionCalculator
    {
        /// <summary>毫米坐标沿轴偏移，正值朝 +Z；结果截断在线段内，与端点顺序无关。</summary>
        internal static double[] ShiftAlongAxis(double[] point,double[] start,double[] end,double offsetMm)
        {
            double dx=end[0]-start[0],dy=end[1]-start[1],dz=end[2]-start[2];
            double lengthSquared=dx*dx+dy*dy+dz*dz;
            double length=Math.Sqrt(lengthSquared);
            if(length<=1.0e-9||offsetMm==0)return new[]{point[0],point[1],point[2]};
            // 偏移正方向朝上；投影和重构始终使用原始 start -> end 方向。
            double k=offsetMm/length*(dz<0?-1:1);
            double x=point[0]+dx*k,y=point[1]+dy*k,z=point[2]+dz*k;
            double t=((x-start[0])*dx+(y-start[1])*dy+(z-start[2])*dz)/lengthSquared;
            t=Math.Max(0,Math.Min(1,t));
            return new[]{start[0]+t*dx,start[1]+t*dy,start[2]+t*dz};
        }
    }
}
