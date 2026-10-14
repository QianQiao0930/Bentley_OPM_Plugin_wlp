using System.Collections.Generic;

// 记录真实 BracketBuilder 的扫掠参数，原生相并/剪切使用隔离替身。
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
namespace Bentley.DgnPlatformNET
{
    internal sealed class SolidKernelEntity { }
    internal sealed class ModelInfo { internal double UorPerMeter=1000000; }
    internal sealed class DgnModel
    {
        internal bool Is3d=true;
        internal ModelInfo GetModelInfo(){return new ModelInfo();}
    }
    internal sealed class ElementPropertiesSetter
    {
        internal void SetTransparency(double value){}
        internal bool Apply(Elements.Element element){return true;}
    }
}
namespace Bentley.DgnPlatformNET.Elements { internal sealed class Element { } }
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session
    {
        internal static readonly Session Instance=new Session();
        internal Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel(){return new Bentley.DgnPlatformNET.DgnModel();}
    }
}
namespace SteelSectionProbe
{
    using Bentley.GeometryNET;
    using Bentley.DgnPlatformNET;
    using Bentley.DgnPlatformNET.Elements;
    internal sealed class SweepRecord
    {
        internal ModeData Mode;
        internal DPoint3d Origin;
        internal double Scale,Length;
        internal DVector3d X,Y,Z;
    }
    internal static class SteelMemberFactory
    {
        internal static readonly List<SweepRecord> Sweeps=new List<SweepRecord>();
        internal static SolidKernelEntity AlongAxisBody(ModeData mode,DPoint3d origin,double scale,
            DVector3d x,DVector3d y,DVector3d z,double length)
        {
            Sweeps.Add(new SweepRecord {Mode=mode,Origin=origin,Scale=scale,X=x,Y=y,Z=z,Length=length});
            return new SolidKernelEntity();
        }
        internal static Element AlongAxis(ModeData mode,DPoint3d origin,double scale,
            DVector3d x,DVector3d y,DVector3d z,double length,uint color)
        {AlongAxisBody(mode,origin,scale,x,y,z,length);return new Element();}
    }
    internal static class SolidPrimitiveFactory
    {
        internal static readonly List<string> Cuts=new List<string>();
        internal static Element Element(SolidKernelEntity body,uint color){return new Element();}
        internal static SolidKernelEntity PolygonPrism(DPoint3d[] points,DVector3d direction){return new SolidKernelEntity();}
        internal static SolidKernelEntity Cylinder(DPoint3d start,DPoint3d end,double radius){return new SolidKernelEntity();}
        internal static void Subtract(ref SolidKernelEntity body,IEnumerable<SolidKernelEntity> cuts,string label){Cuts.Add(label);}
        internal static void Union(ref SolidKernelEntity body,IEnumerable<SolidKernelEntity> others,string label){}
    }
    internal static class SupportSteelAppearance {internal const uint Color=7;}
    internal static class N8Builder
    {
        internal static IList<Element> Build(N8Plan plan,DPoint3d point){return new List<Element>();}
        internal static Element BuildPlate(N8Plan plan,G2AnchorFrame frame){return new Element();}
    }
    internal sealed class G2AnchorFrame
    {
        private readonly DPoint3d origin;private readonly double scale;
        internal G2AnchorFrame(DPoint3d origin,double scale,double angle,G2MountFace face){this.origin=origin;this.scale=scale;}
        internal DPoint3d Point(double x,double y,double z){return new DPoint3d(origin.X+x*scale,origin.Y+y*scale,origin.Z+z*scale);}
    }
}
