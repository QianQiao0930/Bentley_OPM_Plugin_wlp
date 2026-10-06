using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class SpiralStairBuilder
    {
        internal static List<HandrailBuildStep> Steps(SpiralStairPlan plan,DPoint3d origin,SpiralStairBuildResult result)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("请在三维活动模型中生成盘梯。");
            double scale=model.GetModelInfo().UorPerMeter/1000;
            if(scale<=0||double.IsNaN(scale)||double.IsInfinity(scale))throw new InvalidOperationException("模型长度单位无效。");
            Func<HandrailPoint,DPoint3d> point=q=>new DPoint3d(origin.X+q.X*scale,origin.Y+q.Y*scale,origin.Z+q.Z*scale);
            Func<List<HandrailPoint>,CurveVector> profile=q=>{
                var curve=CurveVector.Create(CurveVector.BoundaryType.Outer);
                for(int i=0;i<q.Count;i++)curve.Add(CurvePrimitive.CreateLine(new DSegment3d(point(q[i]),point(q[(i+1)%q.Count]))));return curve;};
            var jobs=new List<HandrailBuildStep>();var structural=new List<Element>();
            uint steelColor=DgnColorMap.CreateElementColor(new RgbColorDef(127,163,124),null,null,Session.Instance.GetActiveDgnFile());
            foreach(var beam in plan.Beams)
            {
                var parts=new List<Element>();
                var segments=new List<HandrailPiece>();
                for(int i=1;i<beam.Points.Count;i++){var delta=beam.Points[i]-beam.Points[i-1];segments.Add(new HandrailPiece{Start=beam.Points[i-1],End=beam.Points[i],Tangent=delta.Unit(),Length=delta.Length});}
                int cursor=0,runNumber=0;
                foreach(var run in HandrailSmoothPath.Runs(segments)){
                    int begin=cursor;cursor+=run.Count;int end=cursor;int number=++runNumber;
                    bool straight=run.All(p=>HandrailPoint.Dot(p.Tangent,run[0].Tangent)>1-1e-10);
                    jobs.Add(new HandrailBuildStep(beam.Name+(straight?"平台直纹放样 ":"螺旋光滑放样 ")+number,delegate{
                        var curves=beam.Profiles.Skip(begin).Take(end-begin+1).Select(profile).ToArray();
                        if(!straight){
                            SolidKernelEntity body;var status=Create.BodyFromLoft(out body,curves,curves.Length,new CurveVector[0],0,Session.Instance.GetActiveDgnModelRef(),false,false);
                            if(status!=BentleyStatus.Success||body==null)throw new InvalidOperationException("竖直U形梯梁光滑放样失败（段"+number+"）："+status);
                            parts.Add(SolidPrimitiveFactory.Element(body,steelColor));return;
                        }
                        var primitive=SolidPrimitive.CreateDgnRuledSweep(new DgnRuledSweepDetail(curves,true));
                        if(primitive==null)throw new InvalidOperationException("竖直U形梯梁直纹扫掠创建失败。");
                        var element=DraftingElementSchema.ToElement(model,primitive,null);
                        if(element==null)throw new InvalidOperationException("竖直U形梯梁直纹扫掠转元素失败。");
                        var appearance=new ElementPropertiesSetter();appearance.SetColor(steelColor);
                        if(!appearance.Apply(element))throw new InvalidOperationException("梯梁颜色设置失败。");
                        parts.Add(element);}));
                }
                jobs.Add(new HandrailBuildStep(beam.Name+"组装",delegate{structural.Add(new CellHeaderElement(model,"SPIRAL_STAIR_BEAM",DPoint3d.Zero,DMatrix3d.Identity,parts));}));
            }
            foreach(var plate in plan.Plates)jobs.Add(new HandrailBuildStep(plate.Name,delegate{
                var body=SolidPrimitiveFactory.PolygonPrism(plate.Corners.Select(point).ToList(),new DVector3d(0,0,plate.ThicknessMm*scale));
                structural.Add(SolidPrimitiveFactory.Element(body,steelColor));}));
            jobs.Add(new HandrailBuildStep("盘梯结构组装",delegate{result.Elements.Add(new CellHeaderElement(model,"TANK_SPIRAL_STAIR",DPoint3d.Zero,DMatrix3d.Identity,structural));}));
            foreach(bool inner in plan.Parameters.RequiresInnerRailing?new[]{false,true}:new[]{false})
            {
                var rail=SpiralStairCalculator.Railing(plan,inner);
                rail.Origin+=new HandrailPoint(origin.X/scale,origin.Y/scale,origin.Z/scale);
                var parts=new List<Element>();string side=inner?"内侧栏杆":"外侧栏杆";
                foreach(var step in HandrailBuilder.BuildSteps(rail,parts))jobs.Add(new HandrailBuildStep(side+"："+step.Name,step.Run));
                jobs.Add(new HandrailBuildStep(side+"组装",delegate{
                    var cell=new CellHeaderElement(model,HandrailCatalog.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
                    result.Elements.Add(cell);result.Railings.Add(new KeyValuePair<Element,HandrailPlan>(cell,rail));}));
            }
            return jobs;
        }
    }
}
