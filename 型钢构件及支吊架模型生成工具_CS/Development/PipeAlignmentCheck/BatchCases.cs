using System;
using System.Collections.Generic;
using SteelSectionProbe.PipeAlignment;
namespace SteelSectionProbe.PipeAlignmentCheck
{
    internal static partial class Program
    {
        private static void AddBatchCases(List<TestCase> cases)
        {
            cases.Add(new TestCase("B01 参考只读锁定管可作基准，但不可作目标", delegate {
                var reference = Pipe(99,1200,88.9); reference.IsFromReference=true; reference.IsReadOnly=true; reference.IsLocked=true;
                True(PipeValidationService.ValidateReferencePipe(reference,SurfaceMode.Pipe,Options()).IsValid,"参考可读");
                True(!PipeValidationService.ValidateTargetPipe(reference,AlignmentMode.Center,SurfaceMode.Pipe,Options()).IsValid,"参考不可改");
            }));
            cases.Add(new TestCase("B02 多起点分别计算位移且保留参考跨文件同号", delegate {
                var reference=Pipe(1,1200,88.9); reference.IsFromReference=true; reference.InstanceId="seed";
                var a=RouteFixture(false); var b=Pipe(80,800,88.9); b.InstanceId="isolated";
                var plan=ZAxisRoutePlanner.BuildBatch(reference,new[]{a["seed"],b},AlignmentMode.Center,SurfaceMode.Pipe,id=>a[id],Options());
                True(plan.ReadyCount==4,"一组3构件加独立管");
                Near(plan.Items[0].DeltaZmm,200,Len,"首起点位移");
                Near(plan.Items[3].DeltaZmm,400,Len,"第二起点位移");
            }));
            cases.Add(new TestCase("B03 重复起点去重且伸缩立管只处理一次", delegate {
                var a=RouteFixture(false); var reference=Pipe(99,1200,88.9);
                var plan=ZAxisRoutePlanner.BuildBatch(reference,new[]{a["seed"],a["seed"]},AlignmentMode.Center,SurfaceMode.Pipe,id=>a[id],Options());
                True(plan.Items.Count==3 && plan.FixedPipes.Count==1,"去重");
            }));
            cases.Add(new TestCase("B04 共享构件不同位移冲突跳过整组", delegate {
                var a=RouteFixture(false); var reference=Pipe(99,1200,88.9);
                var b=Pipe(80,800,88.9); b.InstanceId="other"; Connect(b,"seed","PIPE",0);
                var plan=ZAxisRoutePlanner.BuildBatch(reference,new[]{a["seed"],b},AlignmentMode.Center,SurfaceMode.Pipe,id=>a[id],Options());
                True(plan.ReadyCount==0 && plan.SkippedCount>0,"冲突不执行");
            }));
            cases.Add(new TestCase("B05 修改十五根允许，十六根实际直管拒绝", delegate {
                var a=RouteFixture(false); var reference=Pipe(99,1200,88.9);
                var seeds=new List<PipeInfo>{a["seed"]};
                for(ulong i=80;i<93;i++){var p=Pipe(i,800,88.9);p.InstanceId="p"+i;seeds.Add(p);}
                var plan=ZAxisRoutePlanner.BuildBatch(reference,seeds,AlignmentMode.Center,SurfaceMode.Pipe,id=>a[id],Options());
                True(plan.ReadyCount==16,"15直管加弯头");
                var extra=Pipe(93,800,88.9);extra.InstanceId="extra";seeds.Add(extra);
                bool refused=false;try{ZAxisRoutePlanner.BuildBatch(reference,seeds,AlignmentMode.Center,SurfaceMode.Pipe,id=>a[id],Options());}catch(PipeAlignValidationException){refused=true;}
                True(refused,"含伸缩立管累计十六根拒绝");
            }));
            cases.Add(new TestCase("B06 起点超过十五根拒绝", delegate {
                var p=Pipe(1,800,88.9);bool refused=false;
                var seeds=new List<PipeInfo>();for(int i=0;i<16;i++)seeds.Add(p);
                try{ZAxisRoutePlanner.BuildBatch(Pipe(99,1200,88.9),seeds,AlignmentMode.Center,SurfaceMode.Pipe,id=>p,Options());}catch(PipeAlignValidationException){refused=true;}
                True(refused,"起点上限");
            }));
        }
    }
}
