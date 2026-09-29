using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class TFrameCalculator
    {
        /// <summary>页面显示与放置校验共用同一组表格上限。D15 的 MaxHeightMm 表示 L1 上限。</summary>
        internal static TFrameLimits Limits(string kind,char variant,int type)
        {
            if(type<1||type>2||kind=="G4"&&type==2)
                throw new InvalidOperationException("当前 T 型架类别不支持此类型。");
            if(kind=="D15")
            {
                var selected=TFrameCatalog.Variant(kind,variant);
                var profile=ProfileLookup.Profile(RuntimeData.Families,
                    selected.FamilyB,selected.ProfileB);
                if(profile==null)throw new InvalidOperationException("型钢目录缺少构件 B 规格。");
                return new TFrameLimits{Horizontal=true,
                    MaxHeightMm=TFrameCatalog.MaxLength(kind,variant),
                    MaxSpanMm=TFrameCatalog.MaxL2(variant,type),
                    WebThicknessMm=WebThickness(profile,selected.FamilyB)};
            }
            return new TFrameLimits{MaxHeightMm=TFrameCatalog.MaxHeight(kind,variant),
                MaxSpanMm=TFrameCatalog.MaxLength(kind,variant)};
        }
        internal static TFramePlan Calculate(TFrameParameters p,double lineLengthMm)
        {
            if(p==null)throw new ArgumentNullException("p");
            var v=TFrameCatalog.Variant(p.Kind,p.Variant);
            bool horizontal=p.Kind=="D15",ground=p.Kind=="G4";
            if(p.Type<1||p.Type>2||ground&&p.Type==2)
                throw new InvalidOperationException("当前 T 型架类别不支持此类型。");
            if(!Finite(lineLengthMm)||lineLengthMm<150)
                throw new InvalidOperationException("辅助线长度须不小于 150 mm。");
            if(!Finite(p.SpanMm)||p.SpanMm<50)
                throw new InvalidOperationException(horizontal?"L2 须不小于 50 mm。":"横担长 L 须不小于 50 mm。");
            if(!Finite(p.HeadingDegrees))throw new InvalidOperationException("方向角无效。");
            var a=ProfileLookup.Profile(RuntimeData.Families,v.FamilyA,v.ProfileA);
            var b=ProfileLookup.Profile(RuntimeData.Families,v.FamilyB,v.ProfileB);
            if(a==null||b==null)throw new InvalidOperationException("型钢目录缺少 T 型架规格。");
            v.WidthA=Dim(a,"B");v.WidthB=Dim(b,"B");
            v.DepthA=v.FamilyA=="equal_angle"?v.WidthA:Dim(a,"H");
            v.FlangeA=v.FamilyA=="equal_angle"?Dim(a,"t"):
                v.FamilyA=="parallel_channel"?Dim(a,"tf"):Dim(a,"t2");
            v.WebB=WebThickness(b,v.FamilyB);
            double lift=ground?25+v.Ground.PlateThickness:0;
            double h=horizontal?0:lineLengthMm-lift;
            if(ground&&h<150)throw new InvalidOperationException("扣除地脚抬升量后构架高度须不小于 150 mm。");
            double l1=horizontal?lineLengthMm-v.WebB:p.SpanMm;
            if(horizontal&&l1<=0)throw new InvalidOperationException("辅助线扣除构件 B 腹板厚后长度无效。");
            double l2=p.SpanMm,postLength=horizontal?l1:
                p.Type==1?(v.FamilyA=="equal_angle"?h-v.FlangeA-10:h-v.DepthA):
                (v.FamilyA=="equal_angle"?h+v.DepthA-v.FlangeA-10:h);
            if(postLength<=0)throw new InvalidOperationException("立柱下料长无效；请增大辅助线高度。");
            var limits=Limits(p.Kind,p.Variant,p.Type);
            if(horizontal)
            {
                if(l1>limits.MaxHeightMm+1)
                    throw new InvalidOperationException("L1 当前 "+Fmt(l1)+" mm，子项 "+p.Variant+
                        " 标准上限 "+Fmt(limits.MaxHeightMm)+" mm（校验容差 1 mm）；"+
                        "辅助线当前 "+Fmt(lineLengthMm)+" mm，标准上限 "+Fmt(limits.MaxLineMm)+" mm。");
                if(l2>limits.MaxSpanMm+1)
                    throw new InvalidOperationException("L2 当前 "+Fmt(l2)+" mm，子项 "+p.Variant+
                        " 类型 "+p.Type+" 标准上限 "+Fmt(limits.MaxSpanMm)+" mm（校验容差 1 mm）。");
                if("ABCDEF".IndexOf(p.WeldJoint)<0)
                    throw new InvalidOperationException("接点焊接形式只支持 A～F。");
                v.FitU=v.FamilyB=="equal_angle"?-(v.WidthB/2-10):
                    v.FamilyB=="parallel_channel"?-v.WidthB/2+v.WebB:0;
                v.FitW=v.FamilyB=="equal_angle"?v.WebB:0;
            }
            else
            {
                if(lineLengthMm>limits.MaxHeightMm+1)
                    throw new InvalidOperationException("H 当前 "+Fmt(lineLengthMm)+" mm，"+
                        p.Kind+" 子项 "+p.Variant+" 标准上限 "+Fmt(limits.MaxHeightMm)+
                        " mm（校验容差 1 mm）。");
                if(p.SpanMm>limits.MaxSpanMm+1)
                    throw new InvalidOperationException("L 当前 "+Fmt(p.SpanMm)+" mm，"+
                        p.Kind+" 子项 "+p.Variant+" 标准上限 "+Fmt(limits.MaxSpanMm)+
                        " mm（校验容差 1 mm）。");
                if(v.FamilyA=="equal_angle"&&v.DepthA-v.FlangeA-10<=0)
                    throw new InvalidOperationException("角钢无有效焊接搭接长度。");
            }
            string number=Number(p,lineLengthMm,l1);
            return new TFramePlan{Parameters=p,Variant=v,Number=number,
                SupportType=TFrameCatalog.SupportType(p.Kind),SupportCode=TFrameCatalog.SupportCode(p.Kind),
                CellName=TFrameCatalog.SupportCode(p.Kind),
                AssemblySpecification=v.SpecA+" + "+v.SpecB,
                HeightMm=lineLengthMm,L1Mm=l1,L2Mm=l2,PostLengthMm=postLength,
                GroundLiftMm=lift,PostVOffsetMm=!horizontal&&v.FamilyA=="equal_angle"?v.DepthA:0,
                ArmStartVMm=horizontal?(p.Type==1?-l2/2:-(v.WidthA/2+15)):0,
                ArmStartWMm=horizontal?v.FitW:0,
                AllowableLoadKn=TFrameCatalog.Load(p.Kind,p.Variant,lineLengthMm,horizontal?l1:p.SpanMm)};
        }
        internal static string Number(TFrameParameters p,double lineLengthMm,double l1)
        {
            if(p.Kind=="D15")
            {
                string result="D15-"+p.Type+"-"+p.Variant+"-"+p.WeldJoint+"-"+
                    Round(l1)+"-"+Round(p.SpanMm);
                string tail=(p.Stiffener??"").Trim();return tail.Length==0?result:result+"-"+tail;
            }
            return p.Kind=="G4"
                ?"G4-"+p.Variant+"-"+Round(lineLengthMm)+"-"+Round(p.SpanMm)
                :"D12-"+p.Type+"-"+p.Variant+"-"+Round(lineLengthMm)+"-"+Round(p.SpanMm);
        }
        private static int Round(double v){return (int)Math.Floor(v+0.5);}
        private static string Fmt(double v){return v.ToString("0.##",CultureInfo.InvariantCulture);}
        private static bool Finite(double v){return !double.IsNaN(v)&&!double.IsInfinity(v);}
        private static double WebThickness(ProfileData p,string family)
        {return family=="equal_angle"?Dim(p,"t"):
            family=="parallel_channel"?Dim(p,"tw"):Dim(p,"t1");}
        private static double Dim(ProfileData p,string key)
        {double value;if(!p.Dimensions.TryGetValue(key,out value))
            throw new InvalidOperationException("型钢规格 "+p.Name+" 缺少 "+key+" 尺寸。");return value;}
    }
}
