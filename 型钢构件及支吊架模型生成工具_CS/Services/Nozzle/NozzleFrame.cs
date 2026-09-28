using System;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>Axis is the nozzle centreline; U and V span its flange face.</summary>
    internal sealed class NozzleFrame
    {
        private readonly DPoint3d origin;
        private readonly double scale;
        private readonly double ax,ay,az,ux,uy,uz,vx,vy,vz;
        internal double Scale { get { return scale; } }
        internal NozzleFrame(DPoint3d point,double uorPerMm,string axis)
        {
            origin=point;scale=uorPerMm;
            int sign=axis[0]=='-'?-1:1;
            switch(axis[1])
            {
                case 'X': ax=sign;ux=0;uy=1;uz=0;vx=0;vy=0;vz=1;break;
                case 'Y': ay=sign;ux=0;uy=0;uz=1;vx=1;vy=0;vz=0;break;
                case 'Z': az=sign;ux=1;uy=0;uz=0;vx=0;vy=1;vz=0;break;
                default: throw new InvalidOperationException("放置方向无效。");
            }
        }
        internal DPoint3d Point(double alongMm,double uMm,double vMm)
        { return new DPoint3d(origin.X+(ax*alongMm+ux*uMm+vx*vMm)*scale,
            origin.Y+(ay*alongMm+uy*uMm+vy*vMm)*scale,
            origin.Z+(az*alongMm+uz*uMm+vz*vMm)*scale); }
    }
}
