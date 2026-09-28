using System;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>Local X points outward from the tank; Y is horizontal tangential; Z is vertical.</summary>
    internal sealed class TankManholeFrame
    {
        internal readonly DPoint3d Origin;
        internal readonly double Scale;
        internal double Ux,Uy,Vx,Vy;
        internal TankManholeFrame(DPoint3d origin,double scale,double headingRadians)
        {
            Origin=origin; Scale=scale;
            Ux=Math.Cos(headingRadians); Uy=Math.Sin(headingRadians);
            Vx=-Uy; Vy=Ux;
        }
        internal DPoint3d Point(double x,double y,double z)
        {
            return new DPoint3d(Origin.X+(Ux*x+Vx*y)*Scale,
                Origin.Y+(Uy*x+Vy*y)*Scale,Origin.Z+z*Scale);
        }
        internal TankManholeFrame Offset(double x,double y,double z)
        {
            var result=new TankManholeFrame(Point(x,y,z),Scale,0);
            result.Ux=Ux; result.Uy=Uy; result.Vx=Vx; result.Vy=Vy;
            return result;
        }
    }
}
