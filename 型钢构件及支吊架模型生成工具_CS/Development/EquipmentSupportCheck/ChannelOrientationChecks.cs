using System;
using System.Linq;
using Bentley.GeometryNET;
using SteelSectionProbe;

internal static class ChannelOrientationChecks
{
    private static double Dot(DVector3d a,DVector3d b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
    private static bool Near(double a,double b){return Math.Abs(a-b)<1e-8;}
    internal static void Run(Action<bool,string> check)
    {
        foreach(bool isDouble in new[]{false,true})
        foreach(char subtype in "ABCDEF")
        foreach(int type in new[]{1,2})
        foreach(bool reverse in new[]{false,true})
        foreach(bool preweld in new[]{false,true})
        foreach(double angle in new[]{0d,30,90,180})
        {
            var parameters=new BracketParameters {Double=isDouble,Subtype=subtype,Type=type,
                Reverse=reverse,EquipmentOdMm=2000,PreweldMm=100,ShowPreweld=preweld,L3Mm=150,L4Mm=150};
            var plan=BracketCalculator.Calculate(parameters,2000);
            double rad=angle*Math.PI/180,rx=Math.Cos(rad),ry=Math.Sin(rad);
            var line=new PipeClampSelection {StartX=250,StartY=-450,StartZ=1200,
                EndX=250+2000*rx,EndY=-450+2000*ry,EndZ=1200,AxisX=2000*rx,AxisY=2000*ry};
            if(reverse){rx=-rx;ry=-ry;}
            var run=new DVector3d(rx,ry,0);var transverse=new DVector3d(-ry,rx,0);
            SteelMemberFactory.Sweeps.Clear();SolidPrimitiveFactory.Cuts.Clear();
            BracketBuilder.Build(plan,line);
            var sweeps=SteelMemberFactory.Sweeps.ToArray();
            string label=(isDouble?"N4":"N3")+" "+subtype+"/"+type+"/"+reverse+"/"+preweld+"/"+angle;
            check(sweeps.Length==(isDouble?6:2),"构件扫掠数量 "+label);
            int sides=isDouble?2:1;
            for(int side=0;side<sides;side++)
            {
                var beam=sweeps[side*2];var brace=sweeps[side*2+1];
                bool channel=subtype=='A'||subtype=='B';
                int sign=isDouble&&channel?(side==0?-1:1):1;
                check(Near(Dot(beam.X,transverse),sign)&&Near(Dot(brace.X,transverse),sign),"横担和斜撑宽轴 "+label+side);
                check(Near(beam.Y.Z,1)&&Near(Dot(beam.Z,run),1)&&Near(beam.Length,plan.BeamLength),"横担高度方向和长度保留 "+label+side);
                double vr=plan.BraceRun,vz=plan.BraceContactZMm-plan.BracePlateCenterZMm;
                double length=Math.Sqrt(vr*vr+vz*vz);
                check(Near(Dot(brace.Z,run),vr/length)&&Near(brace.Z.Z,vz/length),"斜撑轴线及剪切方向保留 "+label+side);
                if(isDouble&&channel)
                {
                    // 真实目录槽钢开口沿+X，腹板外侧在-X；映射后腹板必须位于内侧。
                    foreach(var member in new[]{beam,brace})
                    {
                        var xs=member.Mode.Segments.SelectMany(s=>s.IsArc?new[]{s.X0,s.Xm,s.X1}:new[]{s.X0,s.X1}).ToArray();
                        double min=xs.Min(),max=xs.Max();
                        check(min<0&&max>0&&Near(min,-max),"真实几何中心轮廓 "+label+side);
                        double webTowardCentre=min*Dot(member.X,transverse)*sign;
                        double tipOutward=max*Dot(member.X,transverse)*sign;
                        check(webTowardCentre<0&&tipOutward>0,"腹板朝内、翼缘开口朝外 "+label+side);
                        check(member.Mode.Segments.Any(s=>s.IsArc),"槽钢真实圆角保留 "+label+side);
                    }
                }
            }
            check(SolidPrimitiveFactory.Cuts.Count(s=>s=="斜撑设备端剪切")==sides&&
                SolidPrimitiveFactory.Cuts.Count(s=>s=="斜撑横担端剪切")==sides,"两端剪切流程保留 "+label);
            if(isDouble)
            {
                check(Near(Dot(sweeps[4].X,run),-1)&&Near(Dot(sweeps[5].X,run),1),"构件C方向保留 "+label);
                double expected=plan.ConnectorSpan+2*Math.Max(2,plan.SectionAWeb/2);
                check(Near(sweeps[4].Length,expected)&&Near(sweeps[5].Length,expected),"构件C跨距与搭接长度保留 "+label);
                foreach(int member in new[]{0,1})
                {
                    var left=sweeps[member];var right=sweeps[2+member];
                    double span=((right.Origin.X-left.Origin.X)*transverse.X+
                        (right.Origin.Y-left.Origin.Y)*transverse.Y)/left.Scale;
                    check(Near(span,plan.L2),"两侧中心间距保留 "+label+member);
                }
            }
        }
    }
}
