namespace SteelSectionProbe
{
    /// <summary>D15 型钢截面的局部 (u,v,w) 三轴，与 Python 水平T形架_几何.member_axes 一致。</summary>
    internal struct TFrameSectionAxes
    {
        internal double Xu,Xv,Xw,Yu,Yv,Yw;
        internal TFrameSectionAxes(double xu,double xv,double xw,double yu,double yv,double yw)
        {Xu=xu;Xv=xv;Xw=xw;Yu=yu;Yv=yv;Yw=yw;}
        internal static TFrameSectionAxes Post(string family)
        {
            // 等边角钢绕自身轴 180°；槽钢与 H 型钢按 Python 的负 90° 旋转。
            return family=="equal_angle"
                ?new TFrameSectionAxes(0,0,-1,0,1,0)
                :new TFrameSectionAxes(0,1,0,0,0,1);
        }
        internal static TFrameSectionAxes Arm(string family)
        {
            return family=="equal_angle"
                ?new TFrameSectionAxes(0,0,-1,-1,0,0)
                :new TFrameSectionAxes(-1,0,0,0,0,1);
        }
    }
}
