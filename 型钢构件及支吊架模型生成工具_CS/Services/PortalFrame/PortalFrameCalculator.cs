using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class PortalFrameCalculator
    {
        internal static PortalFramePlan Calculate(PortalFrameParameters p,double heightMm)
        {
            if(p==null)throw new ArgumentNullException("p");
            if(p.Kind=="D16")return CalculateHorizontal(p,heightMm);
            var v=PortalFrameCatalog.Variant(p.Kind,p.Variant);
            bool ground=p.Kind=="G5"||p.Kind=="G6";
            if((ground||p.Kind=="D20") && p.Type!=1 || !ground &&
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
                armLength=p.SpanMm;span=armLength-(p.Kind=="D20"?1:2)*v.PostWidth;
                pitch=p.Kind=="D20"?armLength:armLength-v.PostWidth;
                postLength=frameH+50;
                if(2*v.ArmWidth+v.ChannelGap>Dim(post,"B")+1e-6)
                    throw new InvalidOperationException("双槽钢横担总宽超过立柱翼缘宽。");
                if(v.ChannelGap<=v.PostWeb)
                    throw new InvalidOperationException("槽钢腹板间距不足以容纳立柱腹板。");
            }
            if(span<50||postLength<=0)
                throw new InvalidOperationException("当前宽度或高度过小，无法生成有效门型架。");
            if((ground||p.Kind=="D20")&&(heightMm>PortalFrameCatalog.MaxHeight(p.Kind,p.Variant)+1||
                p.SpanMm>PortalFrameCatalog.MaxSpan(p.Kind,p.Variant)))
                throw new InvalidOperationException("H 或 L 超出当前子项标准表上限。");
            double lookupSpan=p.Kind=="D8"?span:p.SpanMm;
            string name=string.IsNullOrWhiteSpace(p.Name)?"":p.Name.Trim();
            int roundH=Round(heightMm),roundL=Round(armLength);
            string number=name.Length==0?"":name+"-"+
                (ground||p.Kind=="D20"?"":p.Type.ToString(CultureInfo.InvariantCulture)+"-")+
                p.Variant+"-"+roundH+"-"+roundL;
            return new PortalFramePlan{
                Parameters=p,Variant=v,SupportType=PortalFrameCatalog.SupportType(p.Kind),
                SupportCode=PortalFrameCatalog.SupportCode(p.Kind),Number=number,
                CellName=PortalFrameCatalog.SupportCode(p.Kind),
                AssemblySpecification=v.PostSpecification+((p.Kind=="G6"||p.Kind=="D20")?" + "+v.ArmSpecification+"×2":"")+
                    " / H="+roundH+" / L="+roundL,
                HeightMm=heightMm,FrameHeightMm=frameH,SpanMm=span,ArmLengthMm=p.Kind=="D20"?span:armLength,
                PostLengthMm=postLength,PostPitchMm=pitch,PostVOffsetMm=postV,
                GroundLiftMm=lift,ArmQuantity=(p.Kind=="G6"||p.Kind=="D20")?2:1,
                AllowableLoadKn=PortalFrameCatalog.Load(p.Kind,p.Variant,heightMm,lookupSpan)
            };
        }
        private static PortalFramePlan CalculateHorizontal(PortalFrameParameters p,double l1)
        {
            var v=PortalFrameCatalog.Variant(p.Kind,p.Variant);
            if(p.Type!=1&&p.Type!=2)throw new InvalidOperationException("D16 类型应为 1 或 2。");
            if(p.Weld<'A'||p.Weld>'D')throw new InvalidOperationException("接点焊接型式应为 A～D。");
            if(!Finite(l1)||l1<=0||l1>1000+1)throw new InvalidOperationException("水平辅助线 L1 须大于 0 且不超过 1000 mm。");
            double max=PortalFrameCatalog.MaxSpan("D16",p.Variant);
            if(!Finite(p.SpanMm)||p.SpanMm<=0||p.SpanMm>max)
                throw new InvalidOperationException("L2 须大于 0 且不超过 "+max+" mm。");
            double l3=p.Type==2?p.L3Mm:0,l4=p.Type==2?p.L4Mm:0;
            if(!Finite(l3)||!Finite(l4)||p.Type==2&&(l3<=0||l4<0||l4>=l1))
                throw new InvalidOperationException("类型 2 要求 L3 > 0，0 ≤ L4 < L1；L4=0 时不生成内侧构件 B。");
            double aWidth=Dim(PortalFrameCatalog.Profile(v.PostFamily,v.PostProfile),"B");
            double webReach=v.PostFamily=="hot_rolled_h"?
                (aWidth-Dim(PortalFrameCatalog.Profile(v.PostFamily,v.PostProfile),"t1"))/2:0;
            double bWidth=Dim(PortalFrameCatalog.Profile(v.ArmFamily,v.ArmProfile),"B");
            // 站位保存截面中心；尺寸标注定位到竖肢/腹板的外侧平面。
            double outer=p.Type==1?l1-bWidth/2:l1+l3+bWidth/2;
            double[] stations=p.Type==1||l4==0?new[]{outer}:new[]{l1-l4-bWidth/2,outer};
            G2AnchorPlan plate=null;
            double memberStart=0;
            if(p.AddPlate){
                if(!Finite(p.PlateOffsetMm)||p.PlateOffsetMm<0)
                    throw new InvalidOperationException("端板外移量必须不小于零。");
                var item=G2AnchorCatalog.Require(p.PlateSubtype);
                var profile=PortalFrameCatalog.Profile(v.PostFamily,v.PostProfile);
                double height=v.PostFamily=="equal_angle"?aWidth:Dim(profile,"H");
                double spacing=Math.Max(item.MinSpacingMm,(Math.Floor(Math.Max(height,aWidth)/25)+1)*25);
                plate=G2AnchorCalculator.Calculate(new G2AnchorParameters{SubtypeKey=p.PlateSubtype,
                    SpacingMm=spacing,MountFace=G2MountFace.Wall});
                memberStart=p.PlateOffsetMm+plate.PlateThicknessMm;
                double first=stations[0]-bWidth/2;
                if(memberStart>=first)throw new InvalidOperationException("端板外移和板厚占用构件 A 长度过多。");
                if(plate.PlateSideMm>=p.SpanMm+aWidth)
                    throw new InvalidOperationException("两块锚板会相互重叠，请增大 L2 或调整锚板子项。");
            }
            string name=string.IsNullOrWhiteSpace(p.Name)?"D16":p.Name.Trim();
            string number=name+"-"+p.Type+"-"+p.Variant+"-"+p.Weld+"-"+Round(l1)+"-"+Round(p.SpanMm)+
                (p.Type==2?"-"+Round(l3)+(Math.Abs(l4-l3)<1e-6?"":"-"+Round(l4)):"");
            return new PortalFramePlan{Parameters=p,Variant=v,SupportType=PortalFrameCatalog.SupportType("D16"),
                SupportCode=PortalFrameCatalog.SupportCode("D16"),CellName=PortalFrameCatalog.SupportCode("D16"),Number=number,
                Plate=plate,MemberAStartMm=memberStart,L1Mm=l1,L3Mm=l3,L4Mm=l4,SpanMm=p.SpanMm,PostPitchMm=p.SpanMm+aWidth,
                PostLengthMm=l1+l3+(p.Type==2?bWidth:0)+50-memberStart,ArmLengthMm=p.SpanMm+2*webReach,ArmQuantity=stations.Length,MemberBStationsMm=stations,
                AssemblySpecification="构件 A："+v.PostSpecification+" ×2 / 构件 B："+v.ArmSpecification+" ×"+stations.Length+
                    " / L1="+Round(l1)+" / L2="+Round(p.SpanMm)+(p.Type==2?" / L3="+Round(l3)+" / L4="+Round(l4):"")+
                    " / 接点焊接型式 "+p.Weld+(plate==null?"":" + G2 端板×2（"+p.PlateSubtype+"）"),
                AllowableLoadKn=PortalFrameCatalog.Load("D16",p.Variant,l1,p.SpanMm)};
        }
        private static double Dim(ProfileData profile,string key)
        {double value;if(!profile.Dimensions.TryGetValue(key,out value))
            throw new InvalidOperationException("型钢目录缺少 "+profile.Name+" / "+key);
            return value;}
        private static bool Finite(double value){return !double.IsNaN(value)&&!double.IsInfinity(value);}
        private static int Round(double value){return (int)Math.Floor(value+0.5);}
    }
}
