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
            Console.WriteLine("PortalFrameCheck: D8/D13/G5/G6 规格、几何、荷载、固定附加项名通过。");
        }
    }
}
