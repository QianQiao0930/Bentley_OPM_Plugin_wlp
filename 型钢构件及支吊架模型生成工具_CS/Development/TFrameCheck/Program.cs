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
        private static TFramePlan Plan(string kind,char key,double line,double length,int type=1)
        {return TFrameCalculator.Calculate(new TFrameParameters{Kind=kind,Variant=key,
            Type=type,SpanMm=length,HeadingDegrees=0,WeldJoint='A'},line);}
        private static void Reject(Action action,string label)
        {try{action();}catch(InvalidOperationException){return;}throw new Exception(label+" 应拒绝");}
        private static string Error(Action action)
        {try{action();}catch(InvalidOperationException ex){return ex.Message;}
            throw new Exception("应返回参数超限错误");}
        private static void Main()
        {
            var names=new HashSet<string>();
            foreach(string kind in TFrameCatalog.Kinds)
            {
                Check(names.Add(TFrameCatalog.AssemblyItemName(kind)),"固定 Assembly 名唯一");
                Check(TFrameCatalog.ComponentItemName(kind,"Post").StartsWith("PipeSupportComponent_"),
                    "固定角色名");
                foreach(char key in TFrameCatalog.Variants(kind))
                {
                    var v=TFrameCatalog.Variant(kind,key);
                    Check(ProfileLookup.Mode(RuntimeData.Families,v.FamilyA,v.ProfileA,
                        "geometric_center")!=null,"构件 A 截面 "+kind+key);
                    Check(ProfileLookup.Mode(RuntimeData.Families,v.FamilyB,v.ProfileB,
                        "geometric_center")!=null,"构件 B 截面 "+kind+key);
                    Check(TFrameCatalog.MaxLength(kind,key)>0,"荷载表列 "+kind+key);
                }
            }
            var d12=Plan("D12",'A',500,250);
            Check(d12.Number=="D12-1-A-500-250"&&d12.AllowableLoadKn==1,"D12 编号与荷载");
            Close(d12.PostLengthMm,484,"D12 角钢下料");
            var inverted=Plan("D12",'A',500,250,2);
            Close(inverted.PostLengthMm,534,"D12 倒 T 角钢搭接");
            var g4=Plan("G4",'D',1000,500);
            Check(g4.Number=="G4-D-1000-500"&&g4.AllowableLoadKn==5,"G4 编号与荷载");
            Close(g4.GroundLiftMm,37,"G4 基础抬升");
            Close(g4.PostLengthMm,863,"G4 H 型钢下料");
            Reject(()=>Plan("G4",'D',1000,500,2),"G4 倒 T 禁用");
            Reject(()=>Plan("G4",'D',1000,750),"G4 D 长度上限");
            var d15=Plan("D15",'A',256,200);
            Check(d15.Number=="D15-1-A-A-250-200"&&d15.AllowableLoadKn==.3,
                "D15 长度口径与荷载");
            Close(d15.Variant.FitU,-15,"D15 角钢贴合偏移");
            Close(d15.Variant.FitW,6,"D15 角钢竖向贴合");
            var channel=Plan("D15",'C',256,200,2);
            Close(channel.Variant.FitU,-23,"D15 槽钢贴合偏移");
            Close(channel.ArmStartVMm,-39,"D15 偏心布置");
            var bChannel=TFrameSectionAxes.Arm(channel.Variant.FamilyB);
            Close(bChannel.Xu,-1,"D15 构件 B 槽钢截面 X 朝 -u");
            Close(bChannel.Yw,1,"D15 构件 B 槽钢截面 Y 朝 +w");
            Close(-bChannel.Xu*bChannel.Yw,1,"D15 构件 B 截面右手系");
            var aChannel=TFrameSectionAxes.Post(channel.Variant.FamilyA);
            Close(aChannel.Xv,1,"D15 构件 A 槽钢截面 X 朝 +v");
            Close(aChannel.Yw,1,"D15 构件 A 槽钢截面 Y 朝 +w");
            var bAngle=TFrameSectionAxes.Arm("equal_angle");
            Close(bAngle.Xw,-1,"D15 角钢 B 保持朝下");
            Close(bAngle.Yu,-1,"D15 角钢 B 保持朝 -u");
            var stiff=new TFrameParameters{Kind="D15",Variant='A',Type=1,
                SpanMm=200,WeldJoint='B',Stiffener=" 10×100 "};
            Check(TFrameCalculator.Number(stiff,256,250)=="D15-1-A-B-250-200-10×100",
                "D15 筋板文字仅进入编号");
            Reject(()=>Plan("D15",'A',600,200),"D15 L1 超限");
            var e1=TFrameCalculator.Limits("D15",'E',1);
            var e2=TFrameCalculator.Limits("D15",'E',2);
            Close(e1.MaxHeightMm,1000,"D15 E L1 标准上限");
            Close(e1.MaxSpanMm,500,"D15 E 类型 1 L2 上限");
            Close(e2.MaxSpanMm,1000,"D15 E 类型 2 L2 上限");
            Close(e1.MaxLineMm,e1.MaxHeightMm+e1.WebThicknessMm,"D15 辅助线长上限");
            string l1Error=Error(()=>Plan("D15",'E',e1.MaxLineMm+10,200));
            Check(l1Error.Contains("L1 当前")&&l1Error.Contains("标准上限 1000 mm")&&
                l1Error.Contains("辅助线当前"),"D15 L1 超限显示当前值与上限");
            string l2Error=Error(()=>Plan("D15",'E',e1.WebThicknessMm+500,600));
            Check(l2Error.Contains("L2 当前 600 mm")&&l2Error.Contains("标准上限 500 mm"),
                "D15 L2 超限显示当前值与上限");
            var d12Limits=TFrameCalculator.Limits("D12",'A',1);
            Close(d12Limits.MaxHeightMm,1000,"D12 H 上限");
            Close(d12Limits.MaxSpanMm,250,"D12 L 上限");
            string hError=Error(()=>Plan("D12",'A',1100,250));
            Check(hError.Contains("H 当前 1100 mm")&&hError.Contains("标准上限 1000 mm"),
                "D12 H 超限显示当前值与上限");
            Console.WriteLine("TFrameCheck: D12/G4/D15 规格、尺寸、荷载、编号、截面朝向、上限提示和固定附加项名通过。");
        }
    }
}
