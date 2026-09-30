using System;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// G2 局部坐标（毫米）到活动模型 UOR 的映射。与 Python <c>_PlateFrame</c> 完全一致：
    /// 局部 +X 恒为混凝土外法向（锚栓露出的那一侧），混凝土在 -X 侧；
    /// 局部 +Y 是板面内水平方向，+Z 是「板面内」的第二个方向。
    /// <list type="bullet">
    /// <item>竖直墙面：+X 水平，朝向角绕 Z 旋转；</item>
    /// <item>水平楼板顶面：+X = 世界 +Z，锚板水平、螺栓向下插入楼板；</item>
    /// <item>水平楼板底面：+X = 世界 -Z，锚板水平、螺栓向上。</item>
    /// </list>
    /// 朝向角在各自平面内绕外法向旋转锚板。
    /// </summary>
    internal sealed class G2AnchorFrame
    {
        internal readonly DPoint3d Origin;
        /// <summary>UOR / mm。</summary>
        internal readonly double Scale;

        private readonly double xx,xy,xz,yx,yy,yz,zx,zy,zz;

        internal G2AnchorFrame(DPoint3d origin,double uorPerMm,double headingDegrees,G2MountFace mount)
        {
            Origin=origin; Scale=uorPerMm;
            double[] axisX,axisY,axisZ;
            G2AnchorCalculator.Axes(mount,headingDegrees,out axisX,out axisY,out axisZ);
            xx=axisX[0];xy=axisX[1];xz=axisX[2];
            yx=axisY[0];yy=axisY[1];yz=axisY[2];
            zx=axisZ[0];zy=axisZ[1];zz=axisZ[2];
        }

        internal G2AnchorFrame(DPoint3d origin,double scale,DVector3d x,DVector3d y,DVector3d z)
        {
            Origin=origin;Scale=scale;
            xx=x.X;xy=x.Y;xz=x.Z;yx=y.X;yy=y.Y;yz=y.Z;zx=z.X;zy=z.Y;zz=z.Z;
        }
        /// <summary>局部毫米坐标 -> 世界 UOR 点。</summary>
        internal DPoint3d Point(double x,double y,double z)
        {
            return new DPoint3d(Origin.X+Scale*(x*xx+y*yx+z*zx),
                Origin.Y+Scale*(x*xy+y*yy+z*zy),Origin.Z+Scale*(x*xz+y*yz+z*zz));
        }

        /// <summary>局部毫米向量 -> 世界 UOR 向量（用于拉伸，不含原点平移）。</summary>
        internal DVector3d Direction(double x,double y,double z)
        {
            return new DVector3d(Scale*(x*xx+y*yx+z*zx),Scale*(x*xy+y*yy+z*zy),
                Scale*(x*xz+y*yz+z*zz));
        }
    }
}
