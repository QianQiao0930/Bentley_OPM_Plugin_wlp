// Recording substitutes exercise the real Builder's API calls, not Bentley's native kernel.
using System;
using System.Collections.Generic;
using System.Linq;
namespace Bentley.GeometryNET
{
    internal struct DPoint3d
    {
        internal double X,Y,Z;
        internal DPoint3d(double x,double y,double z){X=x;Y=y;Z=z;}
        internal static DPoint3d Zero {get{return new DPoint3d();}}
    }
    internal struct DVector3d
    {
        internal double X,Y,Z;
        internal DVector3d(double x,double y,double z){X=x;Y=y;Z=z;}
    }
    internal struct DMatrix3d {internal static DMatrix3d Identity {get{return new DMatrix3d();}}}
    internal struct Angle {internal double Radians;internal static Angle FromRadians(double v){return new Angle{Radians=v};}}
    internal struct DTransform3d
    {
        internal DPoint3d Offset;internal double Angle;
        internal static DTransform3d Rotation(int axis,Angle a){return new DTransform3d{Angle=a.Radians};}
        internal static DTransform3d FromTranslation(DPoint3d p){return new DTransform3d{Offset=p};}
        internal static DTransform3d Multiply(DTransform3d translation,DTransform3d rotation){return new DTransform3d{Offset=translation.Offset,Angle=rotation.Angle};}
    }
    internal struct DSegment3d {internal DPoint3d Start,End;internal DSegment3d(DPoint3d a,DPoint3d b){Start=a;End=b;}}
    internal struct DEllipse3d
    {
        internal DPoint3d Start,Middle,End;
        internal static bool TryCircularArcFromStartMiddleEnd(DPoint3d a,DPoint3d m,DPoint3d b,out DEllipse3d arc)
        {arc=new DEllipse3d{Start=a,Middle=m,End=b};return true;}
    }
    internal sealed class CurvePrimitive
    {
        internal bool IsArc;internal DPoint3d Start,Middle,End;
        internal static CurvePrimitive CreateLine(DSegment3d s){return new CurvePrimitive{Start=s.Start,End=s.End};}
        internal static CurvePrimitive CreateArc(DEllipse3d a){return new CurvePrimitive{IsArc=true,Start=a.Start,Middle=a.Middle,End=a.End};}
    }
    internal sealed class CurveVector : List<CurvePrimitive>
    {
        internal enum BoundaryType {Outer,Open}
        internal BoundaryType Boundary;
        internal static CurveVector Create(BoundaryType b){return new CurveVector{Boundary=b};}
    }
}
namespace Bentley.DgnPlatformNET
{
    using Bentley.GeometryNET;
    internal enum BentleyStatus {Success,Error}
    internal sealed class SolidKernelEntity {internal string Kind;}
    internal sealed class DgnModel {internal bool Is3d=true;internal ModelInfo GetModelInfo(){return new ModelInfo();}}
    internal sealed class ModelInfo {internal double UorPerMeter {get{return Bentley.MstnPlatformNET.Session.Scale*1000;}}}
    internal sealed class TransformInfo {internal DTransform3d Value;internal TransformInfo(DTransform3d v){Value=v;}}
    internal struct RgbColorDef {internal RgbColorDef(byte r,byte g,byte b){}}
    internal static class DgnColorMap {internal static uint CreateElementColor(RgbColorDef rgb,object a,object b,object file){return 0xFFCC00;}}
    internal static class Create
    {
        internal sealed class Call {internal CurveVector Profile,Path;internal ValueType Direction;}
        internal static readonly List<Call> Calls=new List<Call>();
        internal static bool FailAll;
        internal static int FailNext;
        internal static BentleyStatus BodyFromSweep(out SolidKernelEntity body,CurveVector profile,CurveVector path,object model,bool parallel,bool repair,bool sheet,ValueType dir,ValueType twist,ValueType scale,ValueType at)
        {Calls.Add(new Call{Profile=profile,Path=path,Direction=dir});body=null;if(FailAll||FailNext-->0)return BentleyStatus.Error;body=new SolidKernelEntity{Kind="Sweep"};return BentleyStatus.Success;}
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    using Bentley.GeometryNET;
    internal sealed class CellHeaderElement : Element
    {
        internal string Name;internal List<Element> Children;
        internal CellHeaderElement(Bentley.DgnPlatformNET.DgnModel model,string name,DPoint3d origin,DMatrix3d matrix,List<Element> children){Name=name;Children=children;}
    }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session
    {
        internal static double Scale=1;
        internal static readonly Session Instance=new Session();
        internal static readonly Bentley.DgnPlatformNET.DgnModel Model=new Bentley.DgnPlatformNET.DgnModel();
        internal Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel(){return Model;}
        internal object GetActiveDgnModelRef(){return Model;}
        internal object GetActiveDgnFile(){return Model;}
    }
}
namespace SteelSectionProbe
{
    using Bentley.DgnPlatformNET;
    using Bentley.DgnPlatformNET.Elements;
    using Bentley.GeometryNET;
    internal static class SolidPrimitiveFactory
    {
        internal static int BoxCount,CylinderCount;
        internal static SolidKernelEntity PolygonPrism(IList<DPoint3d> p,DVector3d v){BoxCount++;return new SolidKernelEntity{Kind="Box"};}
        internal static SolidKernelEntity Cylinder(DPoint3d a,DPoint3d b,double r){CylinderCount++;return new SolidKernelEntity{Kind="Cylinder"};}
        internal static Element Element(SolidKernelEntity body,uint color){return new Element();}
    }
    internal static class SteelMemberFactory
    {
        internal sealed class Call {internal ModeData Mode;internal DPoint3d Origin;internal DVector3d U,V,W;internal double Scale,Length;}
        internal static readonly List<Call> Calls=new List<Call>();
        internal static SolidKernelEntity AlongAxisBody(ModeData mode,DPoint3d origin,double scale,DVector3d u,DVector3d v,DVector3d w,double length)
        {Calls.Add(new Call{Mode=mode,Origin=origin,Scale=scale,U=u,V=v,W=w,Length=length});return new SolidKernelEntity{Kind="Angle"};}
    }
    internal static class BuilderChecks
    {
        internal static void Run(Action<bool,string> check)
        {
            var plan=WallLadderCalculator.Calculate(3000,new WallLadderParameters{HeadingDegrees=90});
            foreach(double scale in new[]{1d,1000d})
            {
                Bentley.MstnPlatformNET.Session.Scale=scale;Reset();
                var cells=WallLadderBuilder.Build(plan,new WallLadderPoint(100,200,300));
                check(cells.Length==2&&((CellHeaderElement)cells[0]).Name=="WALL_LADDER"&&((CellHeaderElement)cells[1]).Name=="WALL_LADDER_CAGE","real Builder groups two detached cells");
                check(cells.All(c=>!c.Written)&&cells.Cast<CellHeaderElement>().SelectMany(c=>c.Children).All(e=>!e.Written),"Builder does not write children or cells");
                check(Create.Calls.Count==plan.HoopLevels.Length,"one sweep per entire hoop path");
                check(Create.Calls.All(c=>c.Path.Count(x=>x.IsArc)==2&&c.Profile.Count==4&&c.Profile.Boundary==CurveVector.BoundaryType.Outer&&c.Path.Boundary==CurveVector.BoundaryType.Open),"real Builder sends two arcs and closed rectangle");
                for(int i=0;i<Create.Calls.Count;i++)
                {
                    var call=Create.Calls[i];var part=plan.CageParts[i];check(call.Path.Count==part.Path.Length,"exact segment topology");
                    for(int j=0;j<call.Path.Count;j++)
                    {
                        check(Near(call.Path[j].Start.X,part.Path[j].Start.X*scale)&&Near(call.Path[j].Start.Y,part.Path[j].Start.Y*scale)&&Near(call.Path[j].Start.Z,part.Path[j].Start.Z*scale),"path unit conversion");
                        check(call.Path[j].IsArc==part.Path[j].IsArc,"Builder preserves curve types");
                        if(part.Path[j].IsArc)check(Near(call.Path[j].Middle.X,part.Path[j].Middle.X*scale)&&Near(call.Path[j].Middle.Y,part.Path[j].Middle.Y*scale),"true arc middle, never a chord");
                    }
                }
                check(Near(cells[0].Transform.Value.Offset.X,100*scale)&&Near(cells[0].Transform.Value.Offset.Y,200*scale)&&Near(cells[0].Transform.Value.Offset.Z,300*scale)&&Near(cells[0].Transform.Value.Angle,Math.PI/2),"origin and heading transform in model units");
                check(SteelMemberFactory.Calls.Count==plan.BracketLevels.Length*2&&SteelMemberFactory.Calls.All(c=>c.Mode.Segments.Any(s=>s.IsArc)&&Near(c.Length,257.5)),"both-side catalogue angle fillets and wall-to-stile length");
                var top=Create.Calls.Last();check(Math.Abs(top.Profile[0].Start.Z-top.Path[0].Start.Z)<1e-8,"vertical start uses nondegenerate horizontal profile");
            }
            Reset();Create.FailNext=1;WallLadderBuilder.Build(plan,new WallLadderPoint());check(Create.Calls.Count==plan.HoopLevels.Length+1&&Create.Calls[1].Direction!=null,"native failure retries true path reference direction");
            Reset();Create.FailAll=true;bool rejected=false;try{WallLadderBuilder.Build(plan,new WallLadderPoint());}catch(InvalidOperationException ex){rejected=ex.Message.Contains("真实曲线扫掠失败")&&ex.Message.Contains("WALL_LADDER_CAGE");}
            check(rejected&&Create.Calls.Count==10,"all sweep failures report stage without faceted fallback");
            check(Create.Calls.All(c=>c.Path.Count(p=>p.IsArc)==2),"failure and reversal still contain actual arcs");
            Reset();var noCage=WallLadderCalculator.Calculate(3000,new WallLadderParameters{CageEnabled=false});check(WallLadderBuilder.Build(noCage,new WallLadderPoint()).Length==1&&Create.Calls.Count==0,"no cage single cell");
            Bentley.MstnPlatformNET.Session.Model.Is3d=false;rejected=false;try{WallLadderBuilder.Build(plan,new WallLadderPoint());}catch(InvalidOperationException){rejected=true;}check(rejected,"Builder rejects 2D model");Bentley.MstnPlatformNET.Session.Model.Is3d=true;
            rejected=false;try{WallLadderBuilder.Build(plan,new WallLadderPoint(double.NaN,0,0));}catch(InvalidOperationException){rejected=true;}check(rejected,"Builder rejects invalid origin");
        }
        private static bool Near(double a,double b){return Math.Abs(a-b)<1e-6;}
        private static void Reset(){Create.Calls.Clear();Create.FailAll=false;Create.FailNext=0;SteelMemberFactory.Calls.Clear();SolidPrimitiveFactory.BoxCount=SolidPrimitiveFactory.CylinderCount=0;}
    }
}
