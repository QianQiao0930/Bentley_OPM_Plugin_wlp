using System;
using System.Collections.Generic;
using SteelSectionProbe.PipeAlignment;
namespace SteelSectionProbe.PipeAlignmentCheck
{
    internal static partial class Program
    {
        private static Dictionary<string,PipeInfo> OffsetFixture(double angle, bool reverse, double yaw)
        {
            double rise=800, run=rise/Math.Tan(angle*Math.PI/180.0);
            var r=new Dictionary<string,PipeInfo>();
            r["seed"]=RouteMember(101,"seed","PIPE",new PipeAxis(0,0,1000,1000,0,1000));
            r["elbow"]=RouteMember(102,"elbow","LONG_RADIUS_45_DEGREE_PIPE_ELBOW",new PipeAxis(1000,0,1000,1100,0,900));
            r["slope"]=RouteMember(103,"slope","PIPE",new PipeAxis(1100,0,900,1100+run,0,100));
            r["fixedElbow"]=RouteMember(104,"fixedElbow","LONG_RADIUS_45_DEGREE_PIPE_ELBOW",new PipeAxis(1100+run,0,100,1200+run,0,0));
            r["fixed"]=RouteMember(105,"fixed","PIPE",new PipeAxis(1200+run,0,0,2200+run,0,0));
            Connect(r["seed"],"elbow",r["elbow"].ClassName,1);
            Connect(r["elbow"],"seed","PIPE",0); Connect(r["elbow"],"slope","PIPE",1);
            Connect(r["slope"],"elbow",r["elbow"].ClassName,0);Connect(r["slope"],"fixedElbow",r["fixedElbow"].ClassName,1);
            Connect(r["fixedElbow"],"slope","PIPE",0);Connect(r["fixedElbow"],"fixed","PIPE",1);
            Connect(r["fixed"],"fixedElbow",r["fixedElbow"].ClassName,0);
            foreach(var p in r.Values)
            {
                var a=p.Axis; double c=Math.Cos(yaw),s=Math.Sin(yaw);
                a=new PipeAxis(a.StartXmm*c,a.StartXmm*s,a.StartZmm,a.EndXmm*c,a.EndXmm*s,a.EndZmm);
                if(reverse)a=new PipeAxis(a.EndXmm,a.EndYmm,a.EndZmm,a.StartXmm,a.StartYmm,a.StartZmm);
                p.Axis=a;p.EcTranslationZRaw=a.StartZmm*1000;p.EcLengthRaw=a.LengthMm;
            }
            return r;
        }
        private static AlignmentPlan OffsetPlan(Dictionary<string,PipeInfo> r,double delta)
        {return ZAxisRoutePlanner.Build(r["seed"],delta,id=>r[id],Options());}
        private static void OffsetRefused(Dictionary<string,PipeInfo> r,double delta)
        {bool refused=false;try{OffsetPlan(r,delta);}catch(PipeAlignValidationException){refused=true;}True(refused,"危险乙字弯必须拒绝");}
        private static void AddOffsetCases(List<TestCase> cases)
        {
            cases.Add(new TestCase("O01 不同倾角、方向和端点顺序，升降均保持固定侧与接点",delegate {
                foreach(double angle in new[]{30.0,45.0,60.0})foreach(double yaw in new[]{0.0,0.7,2.1})
                foreach(bool reverse in new[]{false,true})foreach(double delta in new[]{-100.0,100.0,0.0})
                {
                    var r=OffsetFixture(angle,reverse,yaw);var plan=OffsetPlan(r,delta);
                    True(plan.Items.Count==3 && plan.FixedPipes.Count==2,"仅选中管、移动弯头、斜管修改");
                    var seed=plan.Items[0];var elbow=plan.Items[1];var slope=plan.Items[2];
                    Near(seed.TargetAxis.CenterElevationMm,1000+delta,Len,"选中管标高");
                    True(seed.TargetAxis.IsHorizontal(Len),"选中管保持水平");
                    True(seed.IsStretch && slope.IsStretch && elbow.IsRigidAdjustment && !elbow.IsStretch,"修改类型");
                    int selectedEnd=reverse?0:1, movingSlopeEnd=reverse?1:0;
                    Near(Distance(seed.TargetAxis,selectedEnd,elbow.TargetAxis,reverse?1:0),0,Len,"水平管与弯头仍连接");
                    Near(Distance(slope.TargetAxis,movingSlopeEnd,elbow.TargetAxis,reverse?0:1),0,Len,"斜管与弯头仍连接");
                    Near(Distance(slope.TargetAxis,1-movingSlopeEnd,r["slope"].Axis,1-movingSlopeEnd),0,Len,"斜管固定端不动");
                    Near(seed.TargetAxis.LengthMm,1000-delta/Math.Tan(angle*Math.PI/180),1e-8,"水平伸缩量");
                    Near(slope.TargetAxis.LengthMm,r["slope"].Axis.LengthMm+delta/Math.Sin(angle*Math.PI/180),1e-8,"斜管伸缩量");
                    foreach(var f in plan.FixedPipes)True(f.InstanceId=="fixed"||f.InstanceId=="fixedElbow","固定侧");
                }
            }));
            cases.Add(new TestCase("O02 移动侧远端连接和斜管分支拒绝",delegate {
                var r=OffsetFixture(45,false,0);Connect(r["seed"],"remote","PIPE",0);OffsetRefused(r,100);
                r=OffsetFixture(45,false,0);Connect(r["slope"],"branch","PIPE",2);OffsetRefused(r,100);
            }));
            cases.Add(new TestCase("O03 非平行水平管及空间偏转拒绝",delegate {
                var r=OffsetFixture(45,false,0);var a=r["fixed"].Axis;r["fixed"].Axis=new PipeAxis(a.StartXmm,0,0,a.StartXmm,1000,0);OffsetRefused(r,100);
                r=OffsetFixture(45,false,0);r["seed"].Axis=new PipeAxis(1000,-1000,1000,1000,0,1000);OffsetRefused(r,100);
            }));
            cases.Add(new TestCase("O04 过短、翻转及不可写斜管拒绝",delegate {
                OffsetRefused(OffsetFixture(45,false,0),1100);OffsetRefused(OffsetFixture(45,false,0),-900);
                var r=OffsetFixture(45,false,0);r["slope"].IsLocked=true;OffsetRefused(r,100);
            }));
            cases.Add(new TestCase("O05 固定侧未知拓扑和端点不吻合拒绝",delegate {
                var r=OffsetFixture(45,false,0);r["fixed"].Topology.IsKnown=false;OffsetRefused(r,100);
                r=OffsetFixture(45,false,0);r["slope"].Axis=r["slope"].Axis.ShiftedByZ(20);OffsetRefused(r,100);
            }));
            cases.Add(new TestCase("O06 乙字弯配合直线基准管底中心管顶",delegate {
                foreach(var mode in new[]{AlignmentMode.Bottom,AlignmentMode.Center,AlignmentMode.Top})
                {
                    var r=OffsetFixture(45,false,0);var line=new PipeInfo{IsReferenceLine=true,ElementId=200,Axis=new PipeAxis(0,0,1100,100,0,1100)};
                    var plan=ZAxisRoutePlanner.BuildBatch(line,new[]{r["seed"]},mode,SurfaceMode.Pipe,id=>r[id],Options());
                    True(plan.ReadyCount==3,"乙字弯三成员");
                    var moved=Pipe(101,plan.Items[0].TargetAxis.CenterElevationMm,88.9);
                    Near(ElevationCalculator.GetAlignmentElevation(moved,mode,SurfaceMode.Pipe),1100,Len,"目标表面对齐");
                    True(plan.Items[1].IsRigidAdjustment,"批量保留弯头平移类型");
                }
            }));
            cases.Add(new TestCase("O07 同时选中乙字弯两侧冲突跳过",delegate {
                var r=OffsetFixture(45,false,0);var reference=Pipe(200,500,88.9);
                var plan=ZAxisRoutePlanner.BuildBatch(reference,new[]{r["seed"],r["fixed"]},AlignmentMode.Center,SurfaceMode.Pipe,id=>r[id],Options());
                True(plan.ReadyCount==0,"冲突两侧不能同时修改");
            }));
            cases.Add(new TestCase("O08 弯头复核要求XYZ均匹配",delegate {
                var r=OffsetFixture(45,false,0);var item=OffsetPlan(r,100).Items[1];
                var v=new PipeMoveVerification{GeometryAxis=item.TargetAxis,GeometryCenterElevationMm=item.TargetAxis.CenterElevationMm,
                    EcTranslationZRaw=r["elbow"].EcTranslationZRaw+100000};
                True(v.MatchesTarget(item,0.1),"完整平移通过");
                v.GeometryAxis=r["elbow"].Axis.ShiftedByZ(100);
                True(!v.MatchesTarget(item,0.1),"只改Z拒绝");
            }));
        }
        private static double Distance(PipeAxis a,int i,PipeAxis b,int j)
        {
            double x=(i==0?a.StartXmm:a.EndXmm)-(j==0?b.StartXmm:b.EndXmm);
            double y=(i==0?a.StartYmm:a.EndYmm)-(j==0?b.StartYmm:b.EndYmm);
            double z=(i==0?a.StartZmm:a.EndZmm)-(j==0?b.StartZmm:b.EndZmm);
            return Math.Sqrt(x*x+y*y+z*z);
        }
    }
}
