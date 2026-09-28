using System;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class VerticalPipeSupportCalculator
    {
        private static string N(double value) { return value.ToString("0.##",CultureInfo.InvariantCulture); }
        private static string Angle(double value)
        { return Math.Abs(value-Math.Round(value))<1e-9?
            Math.Round(value).ToString("0",CultureInfo.InvariantCulture):
            value.ToString("0.#",CultureInfo.InvariantCulture); }
        private static int Round(double value) { return (int)Math.Floor(value+0.5); }
        internal static VerticalPipeSupportPlan Calculate(VerticalPipeSupportParameters p,
            bool isPipe,double? nominal,string pipeNumber)
        {
            if(p==null) throw new ArgumentNullException("p");
            int dn=p.PipeDn;
            if(isPipe)
            {
                dn=nominal.HasValue?VerticalPipeSupportCatalog.MatchDn(nominal.Value,p.Kind):0;
                if(dn==0) throw new InvalidOperationException("所选管道的公称直径不在当前立管耳轴类型的范围内。");
            }
            double od;
            if(!VerticalPipeSupportCatalog.Od.TryGetValue(dn,out od))
                throw new InvalidOperationException("所选 DN 不在标准管径表中。");
            if(p.Kind==VerticalPipeSupportKind.F10 && !VerticalPipeSupportCatalog.F10Dns.Contains(dn))
                throw new InvalidOperationException("F10 仅支持 DN15～DN50。");
            if(p.Kind!=VerticalPipeSupportKind.F10 && !VerticalPipeSupportCatalog.TrunnionDns.Contains(dn))
                throw new InvalidOperationException("F6/F7 仅支持 DN50～DN1200。");
            if(double.IsNaN(p.AzimuthDegrees)||double.IsInfinity(p.AzimuthDegrees))
                throw new InvalidOperationException("方位角无效。");
            double angle=(p.AzimuthDegrees%360+360)%360;
            var plan=new VerticalPipeSupportPlan {Kind=p.Kind,PipeDn=dn,PipeOd=od,
                AzimuthDegrees=angle,Material=p.Material,PipeNumber=pipeNumber??""};
            if(p.Kind==VerticalPipeSupportKind.F10)
            {
                double length;
                switch(p.F10Length) {case "1":length=100;break;case "2":length=150;break;
                    case "3":length=200;break;default:throw new InvalidOperationException("F10 长度代码应为 1/2/3。");}
                double height;
                switch(p.F10Height) {case "A":height=50;break;case "B":height=100;break;
                    case "C":height=150;break;case "D":height=200;break;
                    default:throw new InvalidOperationException("F10 高度代码应为 A/B/C/D。");}
                if(!new[]{"L","C1","C2","A1","A2","S"}.Contains(p.Material))
                    throw new InvalidOperationException("F10 材料代码无效。");
                plan.EarWidthMm=length;plan.EarHeightMm=height;plan.Fixed=p.F10Fixed;
                plan.LengthMm=length;
                plan.Number="F10-"+p.F10Length+"-"+p.F10Height+"-"+p.Material+"-"+
                    Angle(angle%180)+"-"+(p.F10Fixed?"Y":"N");
                plan.Specification="DN"+dn+" "+VerticalPipeSupportCatalog.Nps(dn)+
                    " 耳板 L"+Round(length)+" H"+Round(height);
                return plan;
            }
            int trunnion=p.TrunnionDn==0?VerticalPipeSupportCatalog.TrunnionCandidates(dn).Last():p.TrunnionDn;
            if(!VerticalPipeSupportCatalog.TrunnionCandidates(dn).Contains(trunnion))
                throw new InvalidOperationException("耳轴 DN 不在主管 DN 的表 1 候选范围内。");
            if(!new[]{"L","C1","C2","A1","A2","S","S1"}.Contains(p.Material))
                throw new InvalidOperationException("F6/F7 材料代码无效。");
            double stdWall=VerticalPipeSupportCatalog.StdWall[trunnion];
            double wall=p.WallMm>0?p.WallMm:stdWall;
            double trunnionOd=VerticalPipeSupportCatalog.Od[trunnion];
            if(wall<=0||wall>=trunnionOd/2) throw new InvalidOperationException("耳轴壁厚无效。");
            if(p.LengthMm<=0||double.IsNaN(p.LengthMm)||double.IsInfinity(p.LengthMm))
                throw new InvalidOperationException("耳轴长度 L 必须为正数。");
            if(!new[]{"A","B","C"}.Contains(p.EndType)) throw new InvalidOperationException("端板类型应为 A/B/C。");
            double endThickness=0;
            if(p.EndType=="A") endThickness=6;
            if(p.EndType=="B") endThickness=trunnion<=80?10:trunnion<=200?12:
                trunnion<=300?16:trunnion<=450?20:25;
            double padWidth=dn<=150?50:dn<=400?75:dn<=600?100:dn<=1000?150:200;
            double pad=p.BuildPad?p.PadThicknessMm:0;
            if(p.Material=="S1"&&pad<=0) pad=5;
            if(pad<0||double.IsNaN(pad)||double.IsInfinity(pad)) throw new InvalidOperationException("补强板厚度无效。");
            plan.TrunnionDn=trunnion;plan.TrunnionOd=trunnionOd;plan.WallMm=wall;
            plan.LengthMm=p.LengthMm;plan.EndType=p.EndType;plan.EndPlateThicknessMm=endThickness;
            plan.PadThicknessMm=pad;plan.PadWidthMm=padWidth;
            string wallSuffix=Math.Abs(wall-stdWall)<1e-9?"":"("+N(wall)+")";
            plan.Number=p.Kind+"-"+VerticalPipeSupportCatalog.Nps(dn)+"-"+
                VerticalPipeSupportCatalog.Nps(trunnion)+wallSuffix+"-"+p.Material+"-"+
                Round(p.LengthMm)+"-"+p.EndType+"-"+Angle(p.Kind==VerticalPipeSupportKind.F7?angle%180:angle)+
                (pad>0?"-"+N(pad):"");
            plan.Specification=p.Kind+" DN"+dn+"×"+VerticalPipeSupportCatalog.Nps(trunnion)+
                " 耳轴 L"+Round(p.LengthMm);
            return plan;
        }
        internal static void ValidateVertical(PipeClampSelection selection)
        {
            double horizontal=Math.Sqrt(selection.AxisX*selection.AxisX+selection.AxisY*selection.AxisY);
            double vertical=Math.Abs(selection.AxisZ);
            if(vertical<1e-9 || Math.Atan2(horizontal,vertical)>5*Math.PI/180)
                throw new InvalidOperationException("请选择与竖直方向夹角不超过 5° 的管道或辅助线。");
        }
    }
}
