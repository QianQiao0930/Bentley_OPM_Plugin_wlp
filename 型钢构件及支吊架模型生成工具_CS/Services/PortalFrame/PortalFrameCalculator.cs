using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class PortalFrameCalculator
    {
        internal static PortalFramePlan Calculate(PortalFrameParameters p,double heightMm)
        {
            if(p==null)throw new ArgumentNullException("p");
            var v=PortalFrameCatalog.Variant(p.Kind,p.Variant);
            bool ground=p.Kind=="G5"||p.Kind=="G6";
            if(ground && p.Type!=1 || !ground &&
                (p.Type<1||p.Type>(p.Kind=="D8"?4:2)))
                throw new InvalidOperationException("当前门型架类型无效。");
            if(!Finite(heightMm)||heightMm<150)
                throw new InvalidOperationException("竖直辅助线长度 H 须不小于 150 mm。");
            if(!Finite(p.SpanMm)||p.SpanMm<=0)
                throw new InvalidOperationException("宽度参数须为正数。");
            if(!Finite(p.HeadingDegrees))
                throw new InvalidOperationException("方向角无效。");
            var post=PortalFrameCatalog.Profile(v.PostFamily,v.PostProfile);
            var arm=PortalFrameCatalog.Profile(v.ArmFamily,v.ArmProfile);
            bool angle=v.PostFamily=="equal_angle";
            v.PostWidth=angle?Dim(post,"B"):Dim(post,"H");
            v.ArmDepth=v.ArmFamily=="equal_angle"?Dim(arm,"B"):Dim(arm,"H");
            v.ArmWidth=Dim(arm,"B");
            v.ArmFlange=v.ArmFamily=="equal_angle"?Dim(arm,"t"):
                v.ArmFamily=="parallel_channel"?Dim(arm,"tf"):Dim(arm,"t2");
            v.PostWeb=v.PostFamily=="hot_rolled_h"?Dim(post,"t1"):
                v.PostFamily=="parallel_channel"?Dim(post,"tw"):Dim(post,"t");
            double lift=ground?25+v.Ground.PlateThickness:0;
            double frameH=heightMm-lift;
            if(ground&&frameH<150)
                throw new InvalidOperationException("扣除灌浆与锚板后，构架高度须不小于 150 mm。");
            double armLength,span,pitch,postV=0,postLength;
            if(p.Kind=="D8")
            {
                span=p.SpanMm;
                if(span<50)throw new InvalidOperationException("立柱净距 B 须不小于 50 mm。");
                armLength=span+2*v.PostWidth+30;
                pitch=span+v.PostWidth;
                postV=angle?v.PostWidth:-v.ArmWidth;
                bool inverted=p.Type>=3;
                double contact=v.ArmDepth-v.ArmFlange-10;
                if(contact<=0)throw new InvalidOperationException("立柱与横担没有有效焊接搭接长度。");
                postLength=inverted?heightMm+contact:heightMm-v.ArmFlange-10;
            }
            else if(p.Kind=="D13")
            {
                armLength=p.SpanMm;span=armLength-100-2*v.PostWidth;
                pitch=armLength-100-v.PostWidth;
                postLength=p.Type==2?heightMm:heightMm-v.ArmDepth;
            }
            else if(p.Kind=="G5")
            {
                armLength=p.SpanMm;span=armLength-50-2*v.PostWidth;
                pitch=armLength-50-v.PostWidth;
                postV=angle?v.PostWidth:0;
                postLength=angle?frameH-v.ArmFlange-10:frameH-v.ArmDepth;
            }
            else
            {
                armLength=p.SpanMm;span=armLength-2*v.PostWidth;
                pitch=armLength-v.PostWidth;
                postLength=frameH+50;
                if(2*v.ArmWidth+v.ChannelGap>Dim(post,"B")+1e-6)
                    throw new InvalidOperationException("双槽钢横担总宽超过立柱翼缘宽。");
                if(v.ChannelGap<=v.PostWeb)
                    throw new InvalidOperationException("槽钢腹板间距不足以容纳立柱腹板。");
            }
            if(span<50||postLength<=0)
                throw new InvalidOperationException("当前宽度或高度过小，无法生成有效门型架。");
            if(ground&&(heightMm>PortalFrameCatalog.MaxHeight(p.Kind,p.Variant)+1||
                p.SpanMm>PortalFrameCatalog.MaxSpan(p.Kind,p.Variant)))
                throw new InvalidOperationException("H 或 L 超出当前子项标准表上限。");
            double lookupSpan=p.Kind=="D8"?span:p.SpanMm;
            string name=string.IsNullOrWhiteSpace(p.Name)?"":p.Name.Trim();
            int roundH=Round(heightMm),roundL=Round(armLength);
            string number=name.Length==0?"":name+"-"+
                (ground?"":p.Type.ToString(CultureInfo.InvariantCulture)+"-")+
                p.Variant+"-"+roundH+"-"+roundL;
            return new PortalFramePlan{
                Parameters=p,Variant=v,SupportType=PortalFrameCatalog.SupportType(p.Kind),
                SupportCode=PortalFrameCatalog.SupportCode(p.Kind),Number=number,
                CellName=PortalFrameCatalog.SupportCode(p.Kind),
                AssemblySpecification=v.PostSpecification+(p.Kind=="G6"?" + "+v.ArmSpecification+"×2":"")+
                    " / H="+roundH+" / L="+roundL,
                HeightMm=heightMm,FrameHeightMm=frameH,SpanMm=span,ArmLengthMm=armLength,
                PostLengthMm=postLength,PostPitchMm=pitch,PostVOffsetMm=postV,
                GroundLiftMm=lift,ArmQuantity=p.Kind=="G6"?2:1,
                AllowableLoadKn=PortalFrameCatalog.Load(p.Kind,p.Variant,heightMm,lookupSpan)
            };
        }
        private static double Dim(ProfileData profile,string key)
        {double value;if(!profile.Dimensions.TryGetValue(key,out value))
            throw new InvalidOperationException("型钢目录缺少 "+profile.Name+" / "+key);
            return value;}
        private static bool Finite(double value){return !double.IsNaN(value)&&!double.IsInfinity(value);}
        private static int Round(double value){return (int)Math.Floor(value+0.5);}
    }
}
