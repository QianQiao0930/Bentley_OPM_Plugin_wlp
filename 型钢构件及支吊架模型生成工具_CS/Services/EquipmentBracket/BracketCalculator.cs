using System;

namespace SteelSectionProbe
{
    internal static class BracketCalculator
    {
        internal const double MinimumN3EndMargin=150;
        internal const double MinimumN8PlateClearanceMm=20;
        /// <summary>按实际N8外形复核相邻连接板净距，避免选型表变动后仅凭MIN.H/MIN.L2漏检。</summary>
        internal static void ValidateN8PlateSpacing(double centreDistanceMm,double plateSizeMm,string dimension)
        {
            double gap=centreDistanceMm-plateSizeMm;
            if(double.IsNaN(gap)||double.IsInfinity(gap)||gap<MinimumN8PlateClearanceMm)
                throw new InvalidOperationException(dimension+" 对应的N8板边净距为 "+gap.ToString("0.#")+
                    " mm，应至少为 "+MinimumN8PlateClearanceMm+" mm；请增大 "+dimension+"。");
        }
        /// <summary>
        /// 沿斜撑轴线延长，使完整截面越过设备端竖直面和横担端水平面。
        /// 截面关于高度方向居中；按两剪切面的投影取较大值，再留10mm轴向余量。
        /// </summary>
        internal static double BraceCutOverrunMm(double sectionHeightMm,double radialRunMm,double verticalRunMm)
        {
            double radial=Math.Abs(radialRunMm),vertical=Math.Abs(verticalRunMm);
            if(double.IsNaN(sectionHeightMm)||double.IsInfinity(sectionHeightMm)||sectionHeightMm<=0||
                double.IsNaN(radial)||double.IsInfinity(radial)||radial<=0||
                double.IsNaN(vertical)||double.IsInfinity(vertical)||vertical<=0)
                throw new InvalidOperationException("斜撑截面高度或剪切方向无效。");
            return sectionHeightMm/2*Math.Max(vertical/radial,radial/vertical)+10;
        }
        internal static double N3EndMargin(double lineLength,double plateThickness,double h)
        {return lineLength-plateThickness-h;}
        /// <summary>N3 的 L 包含支架连接板，勾选占位时扣除设备侧预焊件总长 D。</summary>
        internal static double N3SupportLength(BracketParameters p,double lineLength,double plateThickness)
        {
            if(!p.ShowPreweld)return lineLength;
            double d=p.PreweldMm;
            if(double.IsNaN(d)||double.IsInfinity(d)||d<=plateThickness)
                throw new InvalidOperationException("N3 预焊件长度 D 必须大于占位端板厚度 "+plateThickness+" mm。");
            if(d>=lineLength)
                throw new InvalidOperationException("N3 预焊件长度 D 必须小于辅助线长度。");
            return lineLength-d;
        }
        internal static BracketPlan Calculate(BracketParameters p,double lineLength)
        {
            if(p==null)throw new ArgumentNullException("p");
            int i=p.Subtype-'A';
            if(i<0||i>=6)throw new InvalidOperationException("子项应为 A～F。");
            if(p.Type!=1&&p.Type!=2)throw new InvalidOperationException("类型应为 1 或 2。");
            if(lineLength<=0||double.IsNaN(lineLength)||double.IsInfinity(lineLength))
                throw new InvalidOperationException("水平辅助线长度无效。");
            double h=p.HeightMm>0?p.HeightMm:BracketCatalog.MinH[i];
            if(h<BracketCatalog.MinH[i])throw new InvalidOperationException("H 小于该子项 MIN.H。");
            var plate=N8Catalog.Resolve(BracketCatalog.PlateType[i],"H",0,G2MountFace.Wall);
            double beamCenter=-BracketCatalog.AHeight[i]/2;
            // N3/N4: H is the vertical distance between the two N8 plate centres.
            ValidateN8PlateSpacing(h,plate.E,"H");
            double braceCenter=beamCenter+(p.Type==1?-h:h);
            double braceContact=p.Type==1?-BracketCatalog.AHeight[i]:0;
            double run=Math.Abs(braceContact-braceCenter);
            if(run<=0)throw new InvalidOperationException("斜撑水平投影必须大于零。");
            var plan=new BracketPlan {Double=p.Double,Reverse=p.Reverse,
                KeepAuxiliaryLine=p.KeepAuxiliaryLine,ShowPreweld=p.ShowPreweld,
                Subtype=p.Subtype,Type=p.Type,PlateType=BracketCatalog.PlateType[i],
                SectionA=BracketCatalog.A[i],SectionB=BracketCatalog.B[i],
                SectionC=BracketCatalog.C[i],H=h,L=lineLength,
                PlateThickness=plate.T,BraceRun=run,SectionAHeight=BracketCatalog.AHeight[i],
                BeamCenterZMm=beamCenter,BracePlateCenterZMm=braceCenter,BraceContactZMm=braceContact,
                SectionAWidth=BracketCatalog.AWidth[i],SectionAWeb=BracketCatalog.AWeb[i],
                SectionCWidth=BracketCatalog.CWidth[i]};
            if(p.Double)
            {
                double l2=p.L2Mm>0?p.L2Mm:BracketCatalog.MinL2[i];
                if(l2<BracketCatalog.MinL2[i])throw new InvalidOperationException("L2 小于该子项 MIN.L2。");
                ValidateN8PlateSpacing(l2,plate.E,"L2");
                if(p.EquipmentOdMm<=0)throw new InvalidOperationException("N4 必须填写设备外径 2R。");
                if(p.PreweldMm<0)throw new InvalidOperationException("设备预焊件长度 D 不能为负。");
                double r=p.EquipmentOdMm/2;
                if(l2/2>=r)throw new InvalidOperationException("L2/2 必须小于设备半径 R。");
                double l1=lineLength-Math.Sqrt(r*r-l2*l2/4)-p.PreweldMm;
                if(l1<=0)throw new InvalidOperationException("按设备外径计算的 L1 必须大于零。");
                if(l1>BracketCatalog.MaxL1[i])throw new InvalidOperationException("L1 超出该子项表 1 最大跨度。");
                double l3=p.L3Mm>0?p.L3Mm:Math.Max(1,l1*0.5);
                double l4=p.L4Mm>0?p.L4Mm:Math.Max(1,l1*0.25);
                if(l1-l4-plan.SectionCWidth<0)
                    throw new InvalidOperationException("内侧构件 C 越过端板外表面。");
                plan.L1=l1;plan.L2=l2;plan.L3=l3;plan.L4=l4;
                plan.RootOffsetMm=lineLength-l1;
                plan.EquipmentOd=p.EquipmentOdMm;plan.Preweld=p.PreweldMm;
                plan.BeamLength=l1+l3+50+plan.SectionCWidth;
                plan.EndOverhang=plan.BeamLength-run;
                plan.ConnectorSpan=l2-(plan.SectionA[0]=='['?plan.SectionAWidth:plan.SectionAWeb);
                if(plan.ConnectorSpan<=0)throw new InvalidOperationException("两横担间距不足以布置构件 C。");
                plan.VerticalLoad=BracketCatalog.VerticalLoad(i,l1,true);
                plan.HorizontalLoad=BracketCatalog.HorizontalLoad(i,l2);
                plan.Number="N4-"+p.Type+"-"+p.Subtype+"-"+Round(h)+"-"+Round(l1)+
                    "-"+Round(l2)+"-"+Round(l3)+"-"+Round(l4);
            }
            else
            {
                plan.L=N3SupportLength(p,lineLength,plate.T);
                plan.Preweld=p.ShowPreweld?p.PreweldMm:0;
                plan.RootOffsetMm=plan.Preweld;
                plan.L1=plan.L-plate.T;plan.BeamLength=plan.L1;
                plan.EndOverhang=plan.L-plate.T-run;
                double e=N3EndMargin(plan.L,plate.T,h);
                if(e<MinimumN3EndMargin)
                    throw new InvalidOperationException("E="+e.ToString("0.#")+
                        " mm，小于 150 mm；末端太小，不合图集要求，请调整 H 或辅助线长度。");
                plan.VerticalLoad=BracketCatalog.VerticalLoad(i,run,false);
                plan.Number="N3-"+p.Type+"-"+p.Subtype+"-"+Round(h)+"-"+Round(plan.L);
            }
            if(plan.EndOverhang<150)throw new InvalidOperationException("横担斜撑交点外端余量不足 150 mm。");
            plan.Specification="子项 "+p.Subtype+"；类型 "+p.Type+"；H="+Round(h)+
                "；横担 "+plan.SectionA+"；斜撑 "+plan.SectionB+
                (p.Double?"；连接横担 "+plan.SectionC+"；L1="+Round(plan.L1)+
                    " L2="+Round(plan.L2)+" L3="+Round(plan.L3)+" L4="+Round(plan.L4):
                    "；L="+Round(plan.L)+(p.ShowPreweld?"；设备预焊件占位 D="+Round(plan.Preweld)+"（不计材料）":""));
            return plan;
        }
        internal static void ValidateHorizontal(PipeClampSelection selection)
        {
            double horizontal=Math.Sqrt(selection.AxisX*selection.AxisX+selection.AxisY*selection.AxisY);
            if(horizontal<1e-9||Math.Atan2(Math.Abs(selection.AxisZ),horizontal)>5*Math.PI/180)
                throw new InvalidOperationException("请选择与水平面夹角不超过 5° 的辅助线。");
            if(selection.IsPipe)throw new InvalidOperationException("N3/N4 请点取绘制好的水平辅助线。");
        }
        private static int Round(double value){return (int)Math.Floor(value+0.5);}
    }
}
