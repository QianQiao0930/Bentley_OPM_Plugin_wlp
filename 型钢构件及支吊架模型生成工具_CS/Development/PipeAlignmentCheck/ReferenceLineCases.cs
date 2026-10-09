using System.Collections.Generic;
using SteelSectionProbe.PipeAlignment;
namespace SteelSectionProbe.PipeAlignmentCheck
{
    internal static partial class Program
    {
        private static void AddReferenceLineCases(List<TestCase> cases)
        {
            cases.Add(new TestCase("L01 直线基准三种模式和保温表面均使用直线标高", delegate {
                var line = new PipeInfo { IsReferenceLine=true, IsReadOnly=true, ElementId=99,
                    ClassName="REFERENCE_LINE", Axis=new PipeAxis(0,0,1200,1000,0,1200) };
                foreach(var surface in new[]{SurfaceMode.Pipe, SurfaceMode.Insulation})
                foreach(var mode in new[]{AlignmentMode.Bottom,AlignmentMode.Center,AlignmentMode.Top})
                {
                    True(PipeValidationService.ValidateReferencePipe(line,surface,Options()).IsValid,"不需要外径或保温属性");
                    Near(ElevationCalculator.GetAlignmentElevation(line,mode,surface),1200,Len,"直线标高不偏移");
                    var target=Pipe(1,1000,100);target.InsulationThicknessMm=20;
                    var plan=PipeAlignPlanner.BuildPlan(new AlignmentRequest(line,new[]{target},mode,surface,Options()));
                    True(plan.ReadyCount==1,"只包含目标管");
                    var moved=Pipe(1,target.Axis.CenterElevationMm+plan.Items[0].DeltaZmm,100);moved.InsulationThicknessMm=20;
                    Near(ElevationCalculator.GetAlignmentElevation(moved,mode,surface),1200,Len,"目标表面对齐直线");
                    Near(line.Axis.CenterElevationMm,1200,Len,"基准不变");
                }
                True(!PipeValidationService.ValidateTargetPipe(line,AlignmentMode.Center,SurfaceMode.Pipe,Options()).IsValid,"直线禁止作为目标");
            }));
            cases.Add(new TestCase("L02 非水平和零长度直线拒绝", delegate {
                var line=new PipeInfo{IsReferenceLine=true,Axis=new PipeAxis(0,0,0,100,0,20)};
                True(!PipeValidationService.ValidateReferencePipe(line,SurfaceMode.Pipe,Options()).IsValid,"斜线拒绝");
                line.Axis=new PipeAxis(0,0,0,0,0,0);
                True(!PipeValidationService.ValidateReferencePipe(line,SurfaceMode.Pipe,Options()).IsValid,"零长度拒绝");
            }));
            cases.Add(new TestCase("L03 锁Z路由以直线标高对齐且不展开基准", delegate {
                var route=RouteFixture(false);
                var line=new PipeInfo{IsReferenceLine=true,IsReadOnly=true,ElementId=99,ClassName="REFERENCE_LINE",Axis=new PipeAxis(0,0,1200,100,0,1200)};
                var plan=ZAxisRoutePlanner.BuildBatch(line,new[]{route["seed"]},AlignmentMode.Center,SurfaceMode.Pipe,id=>route[id],Options());
                True(plan.ReadyCount==3,"水平管、弯头和伸缩立管");
                foreach(var item in plan.Items)True(!item.Pipe.IsReferenceLine,"基准不进入修改计划");
                Near(plan.ReferenceElevationMm,1200,Len,"直线基准标高");
            }));
        }
    }
}
