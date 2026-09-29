using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class PadPlateCatalog
    {
        private static readonly int[] Dns={15,20,25,32,40,50,65,80,90,100,125,150,200,250,300,350,400,450,500,600,650,700,750,800,850,900};
        private static readonly double[] Ods={21.3,26.7,33.4,42.2,48.3,60.3,73,88.9,101.6,114.3,141.3,168.3,219.1,273,323.8,355.6,406.4,457,508,609.6,660.4,711.2,762,812.8,863.6,914.4};
        private static readonly double[] Nominals={12.7,19.05,25.4,31.75,38.1,50.8,63.5,76.2,88.9,101.6,127,152.4,203.2,254,304.8,355.6,406.4,457.2,508,609.6,660.4,711.2,762,812.8,863.6,914.4};
        private static readonly Dictionary<string,string> Materials=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase)
        {{"L","Q345R"},{"C1","Q235B"},{"C2","Q345R"},{"A1","15CrMoR"},{"A2","12Cr1MoVR"},{"S","06Cr19Ni10"}};
        internal static int[] DnChoices { get { return (int[])Dns.Clone(); } }
        internal static double Outside(int dn){return Ods[Index(dn)];}
        internal static double Nominal(int dn){return Nominals[Index(dn)];}
        internal static double Thickness(int dn){Index(dn);return dn<=200?6:dn<=450?8:10;}
        internal static double DuctThickness(double od){if(!Finite(od)||od<=0)throw new InvalidOperationException("风管外径无效。");return od>2000?10:6;}
        internal static string PadMaterial(string code)
        {string value;if(!Materials.TryGetValue(code??"",out value))throw new InvalidOperationException("未知材料代码。");return value;}
        internal static int? MatchDn(double? value)
        {
            if(!value.HasValue||!Finite(value.Value)||value.Value<=0)return null;
            int best=-1;double error=double.MaxValue;
            for(int i=0;i<Dns.Length;i++)
            {double diff=Math.Min(Math.Abs(Dns[i]-value.Value),Math.Abs(Ods[i]-value.Value));
                if(diff<error){error=diff;best=i;}}
            return best>=0&&error<=Math.Max(5,0.05*Ods[best])?(int?)Dns[best]:null;
        }
        internal static double SnapMultiplier(double ratio)
        {double[] choices={1,1.5,2,2.5,3};double best=choices[0];foreach(double value in choices)
            if(Math.Abs(value-ratio)<Math.Abs(best-ratio))best=value;return best;}
        internal static PadPlatePlan Y2(PadPlateParameters p,PipeClampSelection line,
            PadPlateHvacDuct duct=null)
        {
            if(p==null||line==null)throw new InvalidOperationException("请先点选水平管道或直线。");
            var axis=new VectorMm(line.AxisX,line.AxisY,line.AxisZ).Unit();
            if(Math.Abs(axis.Z)>Math.Sin(5*Math.PI/180))throw new InvalidOperationException("Y2 只适用于水平管道（偏角不超过 5°）。");
            int dn=MatchDn(line.IsPipe?line.NominalMm:null)??p.FallbackDn;
            double od=duct==null?Outside(dn):duct.OutsideMm;
            var plan=Base(p,duct==null?(int?)dn:null,od,
                duct==null?Thickness(dn):DuctThickness(od));
            if(!Finite(p.LengthMm)||p.LengthMm<1)throw new InvalidOperationException("垫板长度 L 必须不小于 1 mm。");
            plan.Kind=PadPlateKind.Y2;plan.LengthMm=p.LengthMm;
            double[] center=line.ProjectedCenter();plan.Center=new VectorMm(center[0],center[1],center[2]);plan.Axis=axis;
            string size=duct==null?""+dn:duct.SizeLabel;
            plan.Number="Y2-"+size+"-"+Fmt(p.LengthMm)+"-"+p.Material.ToUpperInvariant()+"-"+Fmt(p.AlphaDeg);
            plan.Specification=(duct==null?"DN"+dn:size)+" OD"+Fmt(plan.OutsideMm)+"，T"+Fmt(plan.ThicknessMm)+"，L"+Fmt(p.LengthMm)+"，α"+Fmt(p.AlphaDeg)+"°，"+plan.PadMaterial;
            plan.CellName="Y2_ARC_PAD";plan.SupportType="Y2-[弧形垫板]";plan.PipeNumber=line.PipeNumber??"";
            return plan;
        }
        internal static PadPlatePlan Elbow(PadPlateParameters p,PadPlateElbow elbow)
        {
            if(p==null||elbow==null)throw new InvalidOperationException("请先点选 90° 弯头。");
            int dn=elbow.Dn??p.FallbackDn;
            double od=elbow.IsDuct?elbow.OutsideMm:Outside(dn);
            var plan=Base(p,elbow.IsDuct?(int?)null:dn,od,elbow.IsDuct?DuctThickness(od):Thickness(dn));
            if(!Finite(p.CoverageDeg)||p.CoverageDeg<1||p.CoverageDeg>90)
                throw new InvalidOperationException("覆盖角应为 1°～90°。");
            double baseDiameter=elbow.IsDuct?od:Nominal(dn);
            double multiplier=p.AutoMultiplier?SnapMultiplier(elbow.CenterToEndMm/baseDiameter):p.Multiplier;
            if(!Finite(multiplier)||multiplier<0.5||multiplier>5)throw new InvalidOperationException("弯头倍率应为 0.5～5D。");
            plan.Kind=PadPlateKind.Elbow;plan.CoverageDeg=p.CoverageDeg;plan.Multiplier=multiplier;
            plan.BendRadiusMm=multiplier*baseDiameter;plan.ArcLengthMm=plan.BendRadiusMm*p.CoverageDeg*Math.PI/180;
            plan.Origin=elbow.Origin;plan.AxisX=elbow.AxisX;plan.AxisZ=elbow.AxisZ;
            string size=elbow.IsDuct?elbow.SizeLabel:""+dn;
            plan.Number="弯头垫板-"+size+"-"+multiplier.ToString("0.0",CultureInfo.InvariantCulture);
            plan.Specification=(elbow.IsDuct?size:"DN"+dn)+" OD"+Fmt(od)+"，T"+Fmt(plan.ThicknessMm)+
                "，弯头倍率 "+multiplier.ToString("0.0",CultureInfo.InvariantCulture)+"D（R"+Fmt(plan.BendRadiusMm)+
                "），覆盖 "+Fmt(p.CoverageDeg)+"°，α"+Fmt(p.AlphaDeg)+"°，"+plan.PadMaterial;
            plan.CellName="ELBOW_PAD";plan.SupportType="弯头垫板";plan.PipeNumber=elbow.PipeNumber??"";
            return plan;
        }
        private static PadPlatePlan Base(PadPlateParameters p,int? dn,double od,double thickness)
        {
            if(!Finite(p.AlphaDeg)||p.AlphaDeg<1||p.AlphaDeg>359)
                throw new InvalidOperationException("截面张角 α 应为 1°～359°。");
            return new PadPlatePlan{Dn=dn,OutsideMm=od,ThicknessMm=thickness,
                InnerRadiusMm=od/2,OuterRadiusMm=od/2+thickness,AlphaDeg=p.AlphaDeg,
                VentHole=p.VentHole,Material=p.Material.ToUpperInvariant(),PadMaterial=PadMaterial(p.Material)};
        }
        private static int Index(int dn){int index=Array.IndexOf(Dns,dn);if(index<0)throw new InvalidOperationException("未知管径 DN"+dn+"。");return index;}
        private static bool Finite(double value){return !double.IsNaN(value)&&!double.IsInfinity(value);}
        private static string Fmt(double value){return value.ToString("0.###",CultureInfo.InvariantCulture);}
        internal static string AssemblyItemName(PadPlateKind kind){return "PipeSupportAssembly_"+(kind==PadPlateKind.Y2?"Y2_ARC_PAD":"ELBOW_PAD");}
        internal static string ComponentItemName(PadPlateKind kind){return "PipeSupportComponent_"+(kind==PadPlateKind.Y2?"Y2_ARC_PAD_PAD":"ELBOW_PAD_PAD");}
    }
}
