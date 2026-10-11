using System;
namespace SteelSectionProbe
{
    internal enum G2MountFace {Wall,FloorTop,CeilingBottom}
    internal static class Program
    {
        private static int checks;
        private static void Equal(double actual,double expected,string label)
        {checks++;if(double.IsNaN(actual)||Math.Abs(actual-expected)>1e-8)throw new Exception(label+": "+actual+" != "+expected);}
        private static void True(bool value,string label){checks++;if(!value)throw new Exception(label);}
        private static void Reject(Action action,string label)
        {checks++;try{action();}catch(InvalidOperationException){return;}throw new Exception(label+" should fail");}
        private static void Main()
        {
            var p=new N1CantileverParameters{EquipmentOdMm=2000,PreweldMm=100};
            var one=N1CantileverCalculator.Calculate(p,1400);
            Equal(one.L1Mm,1400,"类型1直接取辅助线L1");True(!one.HasLoad,"类型1不凭空计算载荷位置");
            Equal(one.RootMm,0,"类型1起点为生根端");Equal(one.ACutMm,1400,"类型1构件A长度");
            True(one.Number=="N1-1-A-1400","类型1省略L2");
            p.Type=2;p.L2Mm=300;var two=N1CantileverCalculator.Calculate(p,1400);
            Equal(two.L1Mm,300,"类型2L1");Equal(two.ACutMm,290,"B-B的10mm缩进");
            True(two.Number=="N1-2-A-300-300","类型2带L2");
            double[,] loads={{1.4,0.5,0},{3.6,1.8,0.9},{5,2.4,2},{12,6,2.4},{20,10,5}};
            int[] plate={0,1,1,1,2};
            double[] bOffsets={6,7,10,17,20};
            for(int i=0;i<5;i++)
            {
                var v=N1CantileverCatalog.Require((char)('A'+i));Equal(v.PlateType,plate[i],"N8板型");
                foreach(bool b in new[]{false,true})
                {
                    var mode=N1CantileverCatalog.Mode(v,b);True(mode.Segments.Length>=6,"真型钢轮廓存在");
                    bool hasArc=false;foreach(var segment in mode.Segments)hasArc|=segment.IsArc;
                    True(hasArc,"真圆弧轮廓保留");
                }
                Equal(N1CantileverCatalog.AllowableLoad(v,250),loads[i,0],"a=250边界");
                Equal(N1CantileverCatalog.AllowableLoad(v,250.001),loads[i,1],"跨250档");
                Equal(N1CantileverCatalog.AllowableLoad(v,500),loads[i,1],"a=500边界");
                if(i==0)Reject(()=>N1CantileverCatalog.AllowableLoad(v,500.001),"A空白档不得外推");
                else Equal(N1CantileverCatalog.AllowableLoad(v,750),loads[i,2],"a=750边界");
                Reject(()=>N1CantileverCatalog.AllowableLoad(v,750.001),"超表拒绝");
                for(int type=1;type<=2;type++)
                {
                    p.Type=type;p.Subtype=v.Key;var plan=N1CantileverCalculator.Calculate(p,1400);
                    True(plan.Number.StartsWith("N1-"+type+"-"+v.Key),"十种组合");
                    Equal(plan.BTopOffsetMm,type==2?bOffsets[i]:0,"B分截面定位");
                    if(type==2)
                    {
                        if(v.Family=="equal_angle")
                            Equal(plan.BTopOffsetMm-N1CantileverCatalog.BFlangeThickness(v),0,"角钢B翼缘内侧贴合A顶面");
                        else
                        {
                            var a=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileA);
                            var b=ProfileLookup.Profile(RuntimeData.Families,v.Family,v.ProfileB);
                            Equal(plan.BTopOffsetMm-b.Dimensions["H"]/2,-a.Dimensions["H"]/2,"槽钢AB截面中心对齐");
                            Equal(plan.ACutMm,plan.L1Mm-b.Dimensions["tw"],"槽钢A端面贴合B内腹板");
                        }
                    }
                }
            }
            p.Type=2;p.L2Mm=600;N1CantileverCalculator.Calculate(p,1400);p.L2Mm=600.01;
            Reject(()=>N1CantileverCalculator.Calculate(p,1400),"L2超600");p.L2Mm=10;
            Reject(()=>N1CantileverCalculator.Calculate(p,1400),"B长度不足连接");
            p.Type=2;

            p.PreweldMm=400;Reject(()=>N1CantileverCalculator.Calculate(p,1400),"预焊件越过管中心");p.PreweldMm=100;
            p.EquipmentOdMm=double.NaN;Reject(()=>N1CantileverCalculator.Calculate(p,1400),"非有限外径");p.EquipmentOdMm=2000;
            Reject(()=>N1CantileverCalculator.Calculate(p,double.PositiveInfinity),"非有限线长");
            p.Type=1;p.EquipmentOdMm=double.NaN;p.PreweldMm=double.NaN;
            Equal(N1CantileverCalculator.Calculate(p,800).L1Mm,800,"类型1不读无效的隐藏外径或D");
            p.ShowPreweld=true;Reject(()=>N1CantileverCalculator.Calculate(p,800),"勾选占位要求有效D");
            p.PreweldMm=32;Reject(()=>N1CantileverCalculator.Calculate(p,800),"占位必须容纳两块N8板");
            p.PreweldMm=200;var shown=N1CantileverCalculator.Calculate(p,800);
            Equal(shown.RootMm,0,"类型1勾选占位不改变根点");Equal(shown.L1Mm,800,"占位不改变类型1跨度");
            True(shown.Specification.Contains("透明预焊件占位"),"显示选项写入实例规格");
            p.Type=2;p.EquipmentOdMm=2000;p.L2Mm=300;
            Equal(N1CantileverCalculator.Calculate(p,1400).RootMm,1200,"类型2占位端到设备外壁");
            p.ShowPreweld=false;
            p.Type=3;Reject(()=>N1CantileverCalculator.Calculate(p,1400),"类型3缺资料");
            foreach(double angle in new[]{0.0,Math.PI/2,Math.PI,Math.PI*1.37})
            {
                double dx=Math.Cos(angle)*1400,dy=Math.Sin(angle)*1400;
                var f=N1CantileverCalculator.Frame(100,200,300,100+dx,200+dy,300,false);
                var end=f.Point(1400,0,0);Equal(end[0],100+dx,"旋转终点X");Equal(end[1],200+dy,"旋转终点Y");
                var reverse=N1CantileverCalculator.Frame(100+dx,200+dy,300,100,200,300,true);
                Equal(reverse.X,f.X,"反向辅助线设备端X");Equal(reverse.RunY,f.RunY,"反向辅助线方向Y");
                var transverse=f.Point(0,300,0);Equal((transverse[0]-f.X)*f.RunX+(transverse[1]-f.Y)*f.RunY,0,"局部横向正交");
            }
            Reject(()=>N1CantileverCalculator.Frame(0,0,0,0,0,0,false),"零长");
            Reject(()=>N1CantileverCalculator.Frame(0,0,0,500,0,2,false),"非水平线");
            Console.WriteLine("N1CantileverCheck: "+checks+" checks passed (catalog, loads, numbering, lengths, frames, invalid inputs).");
        }
    }
}
