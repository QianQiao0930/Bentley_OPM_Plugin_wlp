using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

// 仅记录真实 TFrameBuilder 传往型钢/地脚工厂的坐标，不模拟原生实体内核。
namespace Bentley.GeometryNET
{
    internal struct DPoint3d
    {
        internal double X,Y,Z;
        internal DPoint3d(double x,double y,double z){X=x;Y=y;Z=z;}
    }
    internal struct DVector3d
    {
        internal double X,Y,Z;
        internal DVector3d(double x,double y,double z){X=x;Y=y;Z=z;}
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    internal class Element
    {
        internal DPoint3d Origin;
        internal Element(DPoint3d origin){Origin=origin;}
    }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session
    {
        internal static readonly Session Instance=new Session();
        internal readonly Model Model=new Model();
        internal Model GetActiveDgnModel(){return Model;}
    }
    internal sealed class Model
    {
        internal bool Is3d=true;
        internal double UorPerMeter=1000;
        internal Model GetModelInfo(){return this;}
    }
}
namespace SteelSectionProbe
{
    internal sealed class PipeClampSelection
    {
        internal double StartX,StartY,StartZ,EndX,EndY,EndZ,AxisX,AxisY,AxisZ;
    }
    internal static class SupportSteelAppearance
    {
        internal const uint Color=0;
    }
    internal sealed class RecordedMember : Element
    {
        internal readonly ModeData Mode;
        internal readonly DVector3d XAxis,YAxis;
        internal readonly double Scale;
        internal RecordedMember(ModeData mode,DPoint3d origin,double scale,DVector3d x,DVector3d y)
            :base(origin){Mode=mode;Scale=scale;XAxis=x;YAxis=y;}
    }
    internal static class SteelMemberFactory
    {
        internal static Element AlongAxis(ModeData mode,DPoint3d origin,double scale,
            DVector3d x,DVector3d y,DVector3d axis,double length,uint color)
        {return new RecordedMember(mode,origin,scale,x,y);}
    }
    internal static class PortalFrameBuilder
    {
        internal static IList<Element> BuildGround(PortalGroundSpec spec,
            double xMm,double yMm,double zMm,double uorPerMm)
        {return new[]{new Element(new DPoint3d(xMm*uorPerMm,yMm*uorPerMm,zMm*uorPerMm))};}
    }
}
