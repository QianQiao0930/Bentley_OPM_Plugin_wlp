using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Check(bool condition,string label)
        {if(!condition)throw new Exception(label);}
        private static void Close(double actual,double expected,string label)
        {if(Math.Abs(actual-expected)>0.001)throw new Exception(label+": "+actual+" != "+expected);}
        private static PortalFramePlan Plan(string kind,char variant,double span,double height,int type=1)
        {return PortalFrameCalculator.Calculate(new PortalFrameParameters{
            Kind=kind,Variant=variant,SpanMm=span,Type=type,Name=kind,HeadingDegrees=0},height);}
        private static void Reject(Action action,string label)
        {try{action();}catch(InvalidOperationException){return;}throw new Exception(label+" 应拒绝");}
        private static void Main()
        {
            var names=new HashSet<string>(StringComparer.Ordinal);
            foreach(string kind in PortalFrameCatalog.Kinds)
            {
                Check(names.Add(PortalFrameCatalog.AssemblyItemName(kind)),"固定 ItemType 名唯一");
                foreach(char key in PortalFrameCatalog.Variants(kind))
                {
                    var v=PortalFrameCatalog.Variant(kind,key);
                    Check(ProfileLookup.Mode(RuntimeData.Families,v.PostFamily,v.PostProfile,
                        "geometric_center")!=null,"立柱截面存在 "+kind+key);
                    Check(ProfileLookup.Mode(RuntimeData.Families,v.ArmFamily,v.ArmProfile,
                        "geometric_center")!=null,"横担截面存在 "+kind+key);
                    Check(PortalFrameCatalog.MaxHeight(kind,key)>0&&
                        PortalFrameCatalog.MaxSpan(kind,key)>0,"标准表档位存在 "+kind+key);
                }
            }
            var d8=Plan("D8",'A',500,500);
            Close(d8.ArmLengthMm,630,"D8 横担长度 B+2W+30");
            Close(d8.PostPitchMm,550,"D8 两柱轴距");
            Check(d8.AllowableLoadKn==3,"D8 荷载");
            var d8Inverted=Plan("D8",'A',500,500,3);
            Check(d8Inverted.PostLengthMm>500,"D8 倒门搭接长度");
            var d13=Plan("D13",'B',1000,1000);
            Close(d13.SpanMm,600,"D13 净距");
            Check(d13.AllowableLoadKn==80,"D13 荷载");
            var g5=Plan("G5",'G',1500,1500);
            Close(g5.GroundLiftMm,45,"G5 灌浆与锚板抬升");
            Check(g5.AllowableLoadKn==60&&g5.Variant.Ground.BoltDiameter==20,"G5 荷载与锚栓");
            var g6=Plan("G6",'B',1500,1500);
            Close(g6.SpanMm,1200,"G6 横担夹在两柱内");
            Close(g6.PostLengthMm,1500-41+50,"G6 柱顶高出横担 50");
            Check(g6.ArmQuantity==2&&g6.AllowableLoadKn==20,"G6 双槽钢与荷载");
            Reject(()=>Plan("G6",'A',1500,1000),"G6 L 超表上限");
            Reject(()=>Plan("D8",'A',49,500),"D8 最小净距");
            foreach(char variant in "ABCDE")foreach(char weld in "ABCD")
            {
                var input=new PortalFrameParameters{Kind="D16",Variant=variant,Weld=weld,
                    Type=1,Name="D16",SpanMm=600,L3Mm=double.NaN,L4Mm=double.NaN};
                var one=PortalFrameCalculator.Calculate(input,500);
                Close(one.PostLengthMm,550,"D16 类型1 A端伸50");
                double reach=one.Variant.PostFamily=="hot_rolled_h"?
                    PortalFrameCatalog.Dimension(one.Variant.PostFamily,one.Variant.PostProfile,"B")-
                    PortalFrameCatalog.Dimension(one.Variant.PostFamily,one.Variant.PostProfile,"t1"):0;
                Close(one.ArmLengthMm,600+reach,"D16 B实长延伸至H型钢腹板内侧");
                Close(one.PostPitchMm,600+PortalFrameCatalog.Dimension(one.Variant.PostFamily,
                    one.Variant.PostProfile,"B"),"D16 A轴距含截面宽");
                Check(one.ArmQuantity==1&&one.MemberBStationsMm.Length==1,"D16 类型1 B数量");
                double bWidth=PortalFrameCatalog.Dimension(one.Variant.ArmFamily,one.Variant.ArmProfile,"B");
                Close(one.MemberBStationsMm[0]+bWidth/2,500,"D16 类型1 B背面定位L1");
                Close(one.PostLengthMm-one.MemberBStationsMm[0]-bWidth/2,50,"D16 类型1外缘伸出50");
                Check(one.Number=="D16-1-"+variant+"-"+weld+"-500-600","D16 类型1编号");
                input.Type=2;input.L3Mm=200;input.L4Mm=150;
                var two=PortalFrameCalculator.Calculate(input,500);
                Close(two.PostLengthMm,750+bWidth,"D16 类型2 A总长含B宽");
                Close(two.MemberBStationsMm[0]+bWidth/2,350,"D16 内侧B背面位置");
                Close(two.MemberBStationsMm[1]-bWidth/2,700,"D16 外侧B背面位置");
                Close(two.PostLengthMm-two.MemberBStationsMm[1]-bWidth/2,50,"D16 类型2外缘伸出50");
                Check(two.ArmQuantity==2&&two.Number.EndsWith("-200-150"),"D16 类型2数量与编号");
                input.L4Mm=200;
                Check(PortalFrameCalculator.Calculate(input,500).Number.EndsWith("-600-200"),"D16 相等L4省略");
                input.L4Mm=0;
                var noInner=PortalFrameCalculator.Calculate(input,500);
                Check(noInner.ArmQuantity==1&&noInner.Number.EndsWith("-200-0"),"D16 无内侧B");
                Close(noInner.MemberBStationsMm[0]-bWidth/2,700,"D16 无内侧B的外侧背面位置");
                input.L4Mm=500;Reject(()=>PortalFrameCalculator.Calculate(input,500),"D16 L4不得到根部");
                input.L4Mm=150;input.L3Mm=double.PositiveInfinity;
                Reject(()=>PortalFrameCalculator.Calculate(input,500),"D16 非有限L3");
            }
            double[][] loads={new[]{4d,2,1.2,.8},new[]{6d,4,2.4,1.6},new[]{10d,6,4,2},
                new[]{-1d,25,16,12},new[]{-1d,40,30,20}};
            for(int row=0;row<5;row++)for(int col=0;col<4;col++)
            {
                var load=PortalFrameCatalog.Load("D16",(char)('A'+row),(col+1)*250,600);
                Check(loads[row][col]<0?!load.HasValue:load==loads[row][col],"D16 完整荷载表");
            }
            Reject(()=>Plan("D16",'A',1001,500),"D16 AB L2上限");
            Reject(()=>Plan("D16",'E',1201,500),"D16 CDE L2上限");
            Reject(()=>Plan("D16",'C',600,1002),"D16 L1上限");
            Reject(()=>Plan("D16",'C',600,500,3),"D16 非法类型");
            double[][] d20Loads={new[]{17d,15,10,-1},new[]{-1d,60,30,-1},new[]{-1d,90,60,40},new[]{-1d,150,120,80}};
            foreach(char variant in "ABCD")
            {
                var d20=Plan("D20",variant,1000,800);
                double width=PortalFrameCatalog.Dimension(d20.Variant.PostFamily,d20.Variant.PostProfile,"H");
                Close(d20.PostLengthMm,850,"D20 立杆高出横担50");
                Close(d20.PostPitchMm,1000,"D20 L为立杆中心间距");
                Close(d20.ArmLengthMm,1000-width,"D20 横担在立杆内侧");
                Check(d20.ArmQuantity==2&&d20.Variant.Ground==null&&d20.GroundLiftMm==0,"D20 背靠背双槽钢且无地脚");
                Check(d20.Number=="D20-"+variant+"-800-1000","D20 编号不含类型");
                for(int col=0;col<4;col++){
                    var load=PortalFrameCatalog.Load("D20",variant,800,(col+1)*500);
                    double expected=d20Loads[variant-'A'][col];
                    Check(expected<0?!load.HasValue:load==expected,"D20 完整荷载表");
                }
                Reject(()=>Plan("D20",variant,1000,PortalFrameCatalog.MaxHeight("D20",variant)+2),"D20 H上限");
            }
            Reject(()=>Plan("D20",'B',2001,800),"D20 L上限");
            Reject(()=>Plan("D20",'B',1000,800,2),"D20 非法类型");
            foreach(char variant in "ABCDE")foreach(string subtype in new[]{"A","B","C","D"})
            foreach(int type in new[]{1,2}){
                var p=new PortalFrameParameters{Kind="D16",Variant=variant,Type=type,SpanMm=1000,
                    AddPlate=true,PlateSubtype=subtype,PlateOffsetMm=20,L3Mm=200,L4Mm=200};
                var withPlate=PortalFrameCalculator.Calculate(p,800);
                double start=20+withPlate.Plate.PlateThicknessMm;
                Close(withPlate.MemberAStartMm,start,"D16 沿用三角架外移+板厚扣除");
                p.AddPlate=false;
                var bare=PortalFrameCalculator.Calculate(p,800);
                Close(withPlate.PostLengthMm+start,bare.PostLengthMm,"D16 端部总位置不因锚板变化");
                Close(withPlate.MemberBStationsMm[0],bare.MemberBStationsMm[0],"D16 B位置不因锚板变化");
                Check(withPlate.Plate.SpacingMm%25==0,"D16 G2孔距25模数");
                Check(bare.Plate==null&&bare.MemberAStartMm==0,"D16 取消锚板恢复长度");
                p.AddPlate=true;p.PlateOffsetMm=800;
                Reject(()=>PortalFrameCalculator.Calculate(p,800),"D16 锚板占长过多");
                p.PlateOffsetMm=-1;
                Reject(()=>PortalFrameCalculator.Calculate(p,800),"D16 锚板负外移");
            }
            Console.WriteLine("PortalFrameCheck: D8/D13/G5/G6/D16/D20 规格、尺寸、荷载、编号、固定附加项名通过。");
        }
    }
}
