// API recording only: the real Builder is linked, but no native Bentley geometry runs.
using System;
using System.Collections.Generic;
using System.Linq;
namespace Bentley.GeometryNET
{
    internal struct DPoint3d
    {
        internal double X,Y,Z;internal DPoint3d(double x,double y,double z){X=x;Y=y;Z=z;}
        internal static DPoint3d Zero {get{return new DPoint3d();}}
    }
    internal struct DVector3d{internal double X,Y,Z;internal DVector3d(double x,double y,double z){X=x;Y=y;Z=z;}}
    internal struct DMatrix3d{internal static DMatrix3d Identity {get{return new DMatrix3d();}}}
    internal struct Angle{internal double Radians;internal static Angle FromRadians(double v){return new Angle{Radians=v};}}
    internal struct DTransform3d
    {
        internal DPoint3d Offset;internal double Angle;
        internal static DTransform3d Rotation(int axis,Angle a){return new DTransform3d{Angle=a.Radians};}
        internal static DTransform3d FromTranslation(DPoint3d p){return new DTransform3d{Offset=p};}
        internal static DTransform3d Multiply(DTransform3d t,DTransform3d r){return new DTransform3d{Offset=t.Offset,Angle=r.Angle};}
    }
    internal sealed class DgnTorusPipeDetail
    {
        internal DPoint3d Center;internal DVector3d U,V;internal double Major,Minor,Sweep;internal bool Capped;
        internal DgnTorusPipeDetail(DPoint3d center,DVector3d u,DVector3d v,double major,double minor,double sweep,bool capped)
        {Center=center;U=u;V=v;Major=major;Minor=minor;Sweep=sweep;Capped=capped;}
    }
    internal sealed class SolidPrimitive
    {internal DgnTorusPipeDetail Torus;internal static SolidPrimitive CreateDgnTorusPipe(DgnTorusPipeDetail d){return new SolidPrimitive{Torus=d};}}
}
namespace Bentley.DgnPlatformNET
{
    using Bentley.GeometryNET;
    internal sealed class SolidKernelEntity
    {
        internal string Kind;internal DPoint3d Start,End;internal DPoint3d[] Corners;internal DVector3d Extrusion;
        internal double Radius;internal DgnTorusPipeDetail Torus;
    }
    internal sealed class DgnModel{internal bool Is3d=true;internal ModelInfo GetModelInfo(){return new ModelInfo();}}
    internal sealed class ModelInfo{internal double UorPerMeter {get{return Bentley.MstnPlatformNET.Session.Scale*1000;}}}
    internal sealed class TransformInfo{internal DTransform3d Value;internal TransformInfo(DTransform3d v){Value=v;}}
    internal struct RgbColorDef{internal uint Value;internal RgbColorDef(byte r,byte g,byte b){Value=(uint)(r*65536+g*256+b);}}
    internal static class DgnColorMap{internal static uint CreateElementColor(RgbColorDef c,object a,object b,object file){return c.Value;}}
    internal sealed class ElementPropertiesSetter
    {
        private uint color;internal static bool Fail;
        internal void SetColor(uint v){color=v;}internal bool Apply(Elements.Element e){e.Color=color;return !Fail;}
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    using Bentley.GeometryNET;
    internal sealed class CellHeaderElement:Element
    {
        internal string Name;internal List<Element> Children;
        internal CellHeaderElement(Bentley.DgnPlatformNET.DgnModel model,string name,DPoint3d origin,DMatrix3d matrix,List<Element> children){Name=name;Children=children;}
    }
    internal static class DraftingElementSchema
    {
        internal static Element ToElement(Bentley.DgnPlatformNET.DgnModel model,SolidPrimitive primitive,object template)
        {return new Element{Body=new Bentley.DgnPlatformNET.SolidKernelEntity{Kind="Torus",Torus=primitive.Torus}};}
    }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session
    {
        internal static double Scale=1;internal static readonly Session Instance=new Session();internal static readonly Bentley.DgnPlatformNET.DgnModel Model=new Bentley.DgnPlatformNET.DgnModel();
        internal Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel(){return Model;}internal object GetActiveDgnFile(){return Model;}
    }
}
namespace SteelSectionProbe
{
    using Bentley.GeometryNET;
    using Bentley.DgnPlatformNET;
    using Bentley.DgnPlatformNET.Elements;
    internal static class SolidPrimitiveFactory
    {
        internal static bool Fail;
        internal static SolidKernelEntity Cylinder(DPoint3d a,DPoint3d b,double radius)
        {if(Fail)throw new InvalidOperationException("模拟圆柱失败");return new SolidKernelEntity{Kind="Cylinder",Start=a,End=b,Radius=radius};}
        internal static SolidKernelEntity PolygonPrism(IList<DPoint3d> p,DVector3d v){return new SolidKernelEntity{Kind="Box",Corners=p.ToArray(),Extrusion=v};}
        internal static Element Element(SolidKernelEntity body,uint color){return new Element{Body=body,Color=color};}
    }
    internal static class BuilderChecks
    {
        internal static void Run(Action<bool,string> check)
        {
            foreach(double scale in new[]{1d,1000d})foreach(double spacing in new[]{350d,1400d,6000d})
            {
                Bentley.MstnPlatformNET.Session.Scale=scale;var plan=MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters{ConnectionSpacingMm=spacing,HeadingDegrees=90});
                var cell=(CellHeaderElement)MagneticGaugeBuilder.Build(plan,new DPoint3d(100*scale,200*scale,300*scale));
                check(!cell.Written&&cell.Children.All(c=>!c.Written)&&cell.Children.Count==plan.Parts.Length,"real Builder detached one cell/all parts");
                check(cell.Name==plan.CellName&&Near(cell.Transform.Value.Offset.Z,300*scale)&&Near(cell.Transform.Value.Angle,Math.PI/2),"cell identity/origin/rotation");
                for(int i=0;i<plan.Parts.Length;i++)
                {
                    var p=plan.Parts[i];var e=cell.Children[i];var rgb=MagneticGaugeCatalog.Rgb(p.Color);
                    check(e.Color==(uint)(rgb[0]*65536+rgb[1]*256+rgb[2]),"Builder exact RGB");check(e.Body.Kind==p.Kind.ToString(),"Builder part type");
                    if(p.Kind==MagneticGaugeKind.Cylinder)
                    {check(Point(e.Body.Start,p.Start,scale)&&Point(e.Body.End,p.End,scale)&&Near(e.Body.Radius,p.RadiusMm*scale),"cylinder dimensions and units");}
                    else if(p.Kind==MagneticGaugeKind.Box)
                    {check(Point(e.Body.Corners[0],p.Start,scale)&&Near(e.Body.Corners[2].X,(p.Start.X+p.Size.X)*scale)&&Near(e.Body.Corners[2].Y,(p.Start.Y+p.Size.Y)*scale)&&Near(e.Body.Extrusion.Z,p.Size.Z*scale),"box dimensions and units");}
                    else
                    {var t=e.Body.Torus;check(Point(t.Center,p.Start,scale)&&Near(t.Major,30*scale)&&Near(t.Minor,3.5*scale)&&Near(t.Sweep,2*Math.PI)&&t.U.X==1&&t.V.Y==1,"true full-circle torus, horizontal wheel plane");}
                }
            }
            var valid=MagneticGaugeCalculator.Calculate(new MagneticGaugeParameters());
            SolidPrimitiveFactory.Fail=true;bool failed=false;try{MagneticGaugeBuilder.Build(valid,new DPoint3d());}catch(InvalidOperationException ex){failed=ex.Message.Contains("第1个Cylinder");}check(failed,"Builder contextual part failure");SolidPrimitiveFactory.Fail=false;
            ElementPropertiesSetter.Fail=true;failed=false;try{MagneticGaugeBuilder.Build(valid,new DPoint3d());}catch(InvalidOperationException ex){failed=ex.Message.Contains("Torus")&&ex.Message.Contains("颜色");}check(failed,"torus color error checked");ElementPropertiesSetter.Fail=false;
            Bentley.MstnPlatformNET.Session.Model.Is3d=false;Reject(()=>MagneticGaugeBuilder.Build(valid,new DPoint3d()),check,"2D rejected");Bentley.MstnPlatformNET.Session.Model.Is3d=true;
            Reject(()=>MagneticGaugeBuilder.Build(valid,new DPoint3d(double.NaN,0,0)),check,"origin rejected");
            Bentley.MstnPlatformNET.Session.Scale=0;Reject(()=>MagneticGaugeBuilder.Build(valid,new DPoint3d()),check,"units rejected");Bentley.MstnPlatformNET.Session.Scale=1;
        }
        private static bool Near(double a,double b){return Math.Abs(a-b)<1e-6;}
        private static bool Point(DPoint3d a,MagneticGaugePoint b,double s){return Near(a.X,b.X*s)&&Near(a.Y,b.Y*s)&&Near(a.Z,b.Z*s);}
        private static void Reject(Action action,Action<bool,string> check,string label){bool rejected=false;try{action();}catch(InvalidOperationException){rejected=true;}check(rejected,label);}
    }
}
