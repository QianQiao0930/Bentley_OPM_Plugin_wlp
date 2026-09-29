using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class TriangleBracketCalculator
    {
        internal const double MinimumEndOverhangMm=150;
        internal static TriangleBracketPlan Calculate(TriangleBracketParameters p,double lineLengthMm,
            double headingDegrees)
        {
            if(p==null)throw new ArgumentNullException("p");
            var v=TriangleBracketCatalog.Variant(p.Kind,p.Variant);
            if(p.Type!=1&&p.Type!=2)throw new InvalidOperationException("类型只支持 1（斜撑在下）或 2（斜撑在上）。");
            if(!Finite(lineLengthMm)||lineLengthMm<=0)
                throw new InvalidOperationException("水平辅助线长度无效。");
            double maximum=TriangleBracketCatalog.MaxLength(p.Kind);
            if(lineLengthMm>maximum)
                throw new InvalidOperationException(p.Kind+" 横担总长 L2 不能超过 "+F(maximum)+" mm。");
            if(!Finite(p.L1Mm))throw new InvalidOperationException("L1 必须是有限数字。");
            double min=p.Kind=="D5"
                ? Math.Max(150,(v.HeightB+v.WebB)*Math.Sqrt(2)/2+50)
                : Math.Max(150,v.HeightB*Math.Sqrt(2)/4+50);
            if(p.L1Mm<min)
                throw new InvalidOperationException("L1 小于当前子项要求的 "+F(min)+" mm。");
            double toe=p.Kind=="D5"?Math.Sqrt(2)*v.HeightB:v.HeightB*Math.Sqrt(2)/4;
            double end=lineLengthMm-p.L1Mm-toe;
            if(end<MinimumEndOverhangMm)
                throw new InvalidOperationException("端部余量 E=L2−L1−斜撑上端伸出量须不小于 150 mm；当前为 "+F(end)+" mm。");
            if(p.Kind=="G12" && p.L1Mm<75+v.BoltSpacing+50)
                throw new InvalidOperationException("G12 斜撑第二根锚栓会落在斜撑之外；L1 至少为 "+
                    F(125+v.BoltSpacing)+" mm。");
            G2AnchorPlan plate=null;
            double plateOffset=0,beamStart=0;
            if(p.Kind=="D5" && p.AddPlate)
            {
                if(!Finite(p.PlateOffsetMm)||p.PlateOffsetMm<0)
                    throw new InvalidOperationException("端板外移量必须不小于零。");
                var item=G2AnchorCatalog.Require(p.PlateSubtype);
                double spacing=Math.Max(item.MinSpacingMm,
                    (Math.Floor(Math.Max(v.HeightA,v.WidthA)/25)+1)*25);
                plate=G2AnchorCalculator.Calculate(new G2AnchorParameters {
                    SubtypeKey=p.PlateSubtype,SpacingMm=spacing,
                    HeadingDegrees=headingDegrees,MountFace=G2MountFace.Wall });
                plateOffset=p.PlateOffsetMm;
                beamStart=plateOffset+plate.PlateThicknessMm;
                if(lineLengthMm-beamStart<=p.L1Mm)
                    throw new InvalidOperationException("端板外移和板厚占用横担长度过多。");
            }
            string tag=string.IsNullOrWhiteSpace(p.Name)?"":p.Name.Trim()+"-"+p.Type+"-"+
                p.Variant+"-"+Round(p.L1Mm)+"-"+Round(lineLengthMm);
            string spec=v.SectionA+(p.Kind=="D19"?"×2":"")+" + "+
                v.SectionB+(p.Kind=="D19"?"×2":"");
            if(p.Kind=="D19")spec+=" + 构件C（S="+F(v.WebGap)+"）";
            if(p.Kind=="G12")spec+=" + 构件C 膨胀锚栓×4";
            if(plate!=null)spec+=" + G2 端板×2（"+p.PlateSubtype+"）";
            var result=new TriangleBracketPlan {
                Parameters=p,Variant=v,Plate=plate,Number=tag,
                SupportType=TriangleBracketCatalog.SupportType(p.Kind),
                SupportCode=TriangleBracketCatalog.SupportCode(p.Kind),
                CellName=TriangleBracketCatalog.CellName(p.Kind),AssemblySpecification=spec,
                L1Mm=p.L1Mm,L2Mm=lineLengthMm,BeamStartMm=beamStart,
                BeamLengthMm=lineLengthMm-beamStart,BraceLengthMm=Math.Sqrt(2)*p.L1Mm,
                EndOverhangMm=end,ToeOffsetMm=toe,MinL1Mm=min,
                P1ZMm=p.Type==1?-v.HeightA:0,
                P3ZMm=p.Type==1?-v.HeightA-p.L1Mm:p.L1Mm,
                QuantityA=p.Kind=="D19"?2:1,QuantityB=p.Kind=="D19"?2:1
            };
            if(v.Loads!=null)
            {
                var columns=p.Kind=="D19"?TriangleBracketCatalog.D19LoadColumns:
                    TriangleBracketCatalog.LoadColumns;
                for(int i=0;i<columns.Length;i++)
                    if(p.L1Mm<=columns[i])
                    {
                        if(v.Loads[i].HasValue)
                        {
                            result.HasLoad=true;result.AllowableVerticalKn=v.Loads[i].Value;
                            if(p.Kind!="D19")result.AllowableHorizontalKn=v.Loads[i].Value*0.3;
                        }
                        break;
                    }
            }
            return result;
        }
        private static bool Finite(double value){return !double.IsNaN(value)&&!double.IsInfinity(value);}
        private static string F(double value){return value.ToString("0.#",CultureInfo.InvariantCulture);}
        private static int Round(double value){return (int)Math.Floor(value+0.5);}
    }
}
