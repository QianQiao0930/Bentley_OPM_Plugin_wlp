using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal sealed class L2ShoeParameters
    {
        internal int Dn=L2ShoeCatalog.DefaultDn;
        internal double ColdMm=L2ShoeCatalog.DefaultColdMm;
        internal string FCode=L2ShoeCatalog.DefaultFCode;
        internal bool BuildPipe,BuildInsulation;
    }

    /// <summary>L2 专有表驱动；实体布尔布局与建模直接复用 T4。</summary>
    internal static class L2ShoeCalculator
    {
        private static string F1(double value)
        { return value.ToString("0.#",CultureInfo.InvariantCulture); }

        internal static T4ShoeLayout BuildLayout(L2ShoeParameters parameters,bool isPipe,
            double? nominalMm,double? coldMm)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            int dn=parameters.Dn;
            if(isPipe) dn=T4ShoeCatalog.MatchDn(nominalMm)??dn;
            var row=L2ShoeCatalog.Require(dn);
            var t4=T4ShoeCatalog.Require(dn);
            double cold=isPipe&&coldMm.HasValue?coldMm.Value:parameters.ColdMm;
            double height=L2ShoeCatalog.HeightForCold(cold);
            double pipeRadius=t4.OutsideMm/2.0;
            double insulationRadius=pipeRadius+cold;
            double insulationOd=2.0*insulationRadius;
            double outerRadius=insulationRadius+row.T3Mm;
            double baseWidth=T4ShoeCatalog.BaseWidthForInsulationOd(insulationOd);
            double bottomZ=-(pipeRadius+height);
            double boltDiameter=T4ShoeCatalog.BoltDiametersMm[row.Bolt];
            var layout=new T4ShoeLayout {
                Code="L2",Dn=dn,Nps=t4.Nps,OutsideMm=t4.OutsideMm,
                PipeRadiusMm=pipeRadius,InsulationMm=cold,
                InsulationRadiusMm=insulationRadius,InsulationOdMm=insulationOd,
                T1Mm=row.T1Mm,T2Mm=row.T2Mm,T3Mm=row.T3Mm,
                ClampOuterRadiusMm=outerRadius,
                ClampWidthMm=T4ShoeCatalog.DefaultClampWidthMm,
                HeightMm=height,Height1Mm=height-row.T1Mm,
                ShoeLengthMm=row.LengthMm,ShoeBottomZMm=bottomZ,
                BaseWidthMm=baseWidth,BaseTopZMm=bottomZ+row.T1Mm,
                BoltCount=4,Bolt=row.Bolt,BoltDiameterMm=boltDiameter,
                BoltLengthMm=2.0*t4.EarThicknessMm+T4ShoeCatalog.BoltExtraMm,
                EarWidthMm=t4.EarWidthMm,EarHeightMm=t4.EarHeightMm,
                EarThicknessMm=t4.EarThicknessMm,
                BoltCenterCMm=t4.BoltCenterCMm,WeldLegKMm=t4.WeldLegKMm,
                PlateGapJMm=t4.PlateGapJMm,
                SplitAngleDeg=T4ShoeCatalog.DefaultSplitAngleDeg,
                MinLengthMm=row.LengthMm,EarEndOffsetMm=row.EndEMm,
                SupportEndOffsetMm=row.EndEMm,BoltGroupSpacingMm=row.SpacingFMm,
                HasMiddleRib=false,TopPlateTopZMm=-outerRadius,
                Number=L2ShoeCatalog.BuildNumber(dn,cold,parameters.FCode)
            };
            if(Math.Abs(row.LengthMm-2*row.EndEMm-row.SpacingFMm)>0.001)
                throw new InvalidOperationException("L2 表 1 的 L、E、F 不一致。");
            return layout;
        }

        internal static string Describe(T4ShoeLayout layout,T4ShoeBooleanLayout bl)
        {
            if(layout==null) throw new ArgumentNullException("layout");
            var row=L2ShoeCatalog.Require(layout.Dn);
            string text="L2 最小长度保冷管托：DN"+layout.Dn+"（"+layout.Nps+
                "，OD "+F1(layout.OutsideMm)+"）；保冷厚度="+F1(layout.InsulationMm)+
                "，H="+F1(layout.HeightMm)+"，L="+F1(layout.ShoeLengthMm)+
                "，F="+F1(row.SpacingFMm)+"，E="+F1(row.EndEMm)+
                "；"+layout.Bolt+"×4；T1/T2/T3="+F1(row.T1Mm)+"/"+
                F1(row.T2Mm)+"/"+F1(row.T3Mm)+
                "；弧形块密度 上/下="+F1(row.UpperDensityKgM3)+"/"+
                F1(row.LowerDensityKgM3)+" kg/m³；允许荷载 垂直 "+
                F1(row.VerticalLoadKn)+"、横向 "+F1(row.LateralLoadKn)+
                " kN；允许轴向位移 "+F1(row.AxialMovementMm)+" mm。编号 "+
                layout.Number+"。";
            if(bl!=null) text+=" 耳板中心距 "+F1(bl.EarCenterXmm[1]-bl.EarCenterXmm[0])+
                " mm；"+(T4ShoeCatalog.UsesSimpleBase(layout.Dn)?
                    "底板加中央纵向腹板。":
                    "底板、纵向腹板及 "+bl.SupportCenterXmm.Length+" 道横向支撑。");
            return text;
        }
    }
}
