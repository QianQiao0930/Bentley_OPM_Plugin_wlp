using System;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 管夹的局部坐标（毫米）到活动模型 UOR 的映射：局部 X = 管轴，局部 Z ≈ 竖直向上。
    /// 与 Python 的 <c>_frame()</c>（A2 与 T4 完全一致）逐项对齐。纯几何，供
    /// <see cref="A2ClampBuilder"/> 与 <see cref="T4ShoeBuilder"/> 共用。
    /// </summary>
    internal sealed class PipeClampFrame
    {
        internal readonly DPoint3d Origin;
        /// <summary>UOR / mm。</summary>
        internal readonly double Scale;

        private readonly double xx,xy,xz,yx,yy,yz,zx,zy,zz;

        internal PipeClampFrame(DPoint3d origin,double uorPerMm,
            double axisX,double axisY,double axisZ)
        {
            Origin=origin; Scale=uorPerMm;
            double[] ex,ey,ez;
            Axes(axisX,axisY,axisZ,out ex,out ey,out ez);
            xx=ex[0];xy=ex[1];xz=ex[2];
            yx=ey[0];yy=ey[1];yz=ey[2];
            zx=ez[0];zy=ez[1];zz=ez[2];
        }

        /// <summary>
        /// 由管轴方向求本地方位系：X = 归一化管轴，Z ≈ 竖直向上（Z 的分量为负时翻转 Y/Z）。
        /// 轴接近竖直时改用世界 +X 作为参考「上」方向。纯数学，供纯计算检查工程断言。
        /// </summary>
        internal static void Axes(double axisX,double axisY,double axisZ,
            out double[] ex,out double[] ey,out double[] ez)
        {
            ex=Normalize(axisX,axisY,axisZ);
            double upX=0.0,upY=0.0,upZ=1.0;
            if(Math.Abs(Dot(ex[0],ex[1],ex[2],upX,upY,upZ))>0.99)
            { upX=1.0;upY=0.0;upZ=0.0; }
            ey=NormalizeArray(Cross(upX,upY,upZ,ex[0],ex[1],ex[2]));
            ez=NormalizeArray(Cross(ex[0],ex[1],ex[2],ey[0],ey[1],ey[2]));
            if(ez[2]<0.0)
            {
                ey=new[]{-ey[0],-ey[1],-ey[2]};
                ez=new[]{-ez[0],-ez[1],-ez[2]};
            }
        }

        private static double[] NormalizeArray(double[] v)
        {
            double length=Math.Sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
            if(length<=1.0e-12) throw new InvalidOperationException("管轴方向长度为零，无法定位。");
            return new[]{v[0]/length,v[1]/length,v[2]/length};
        }

        private static double[] Normalize(double x,double y,double z)
        {
            double length=Math.Sqrt(x*x+y*y+z*z);
            if(length<=1.0e-12) throw new InvalidOperationException("管轴方向长度为零，无法定位。");
            return new[]{x/length,y/length,z/length};
        }
        private static double[] Cross(double ax,double ay,double az,double bx,double by,double bz)
        { return new[]{ay*bz-az*by,az*bx-ax*bz,ax*by-ay*bx}; }
        private static double Dot(double ax,double ay,double az,double bx,double by,double bz)
        { return ax*bx+ay*by+az*bz; }

        /// <summary>局部毫米坐标 -> 世界 UOR 点。</summary>
        internal DPoint3d Point(double x,double y,double z)
        {
            return new DPoint3d(Origin.X+Scale*(x*xx+y*yx+z*zx),
                Origin.Y+Scale*(x*xy+y*yy+z*zy),Origin.Z+Scale*(x*xz+y*yz+z*zz));
        }

        /// <summary>局部毫米向量 -> 世界 UOR 向量（不含原点平移）。</summary>
        internal DVector3d Direction(double x,double y,double z)
        {
            return new DVector3d(Scale*(x*xx+y*yx+z*zx),Scale*(x*xy+y*yy+z*zy),
                Scale*(x*xz+y*yz+z*zz));
        }
    }
}
