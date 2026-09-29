using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>A22 / A24 共用的表 1 / 表 2 选型和几何尺寸推导，不依赖 Bentley API。</summary>
    internal static class A22ClampCalculator
    {
        internal static A22ClampPlan Calculate(A22ClampParameters parameters,bool isPipe,
            double? nominalMm,double? outsideMm,double? coldThicknessMm)
        { return Calculate(parameters,isPipe,nominalMm,outsideMm,coldThicknessMm,false); }

        internal static A22ClampPlan Calculate(A22ClampParameters parameters,bool isPipe,
            double? nominalMm,double? outsideMm,double? coldThicknessMm,bool fourBolt)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            int? matched=isPipe?A22ClampCatalog.MatchDn(nominalMm):null;
            int dn=matched.HasValue?matched.Value:parameters.FallbackDn;
            double outside=isPipe && outsideMm.HasValue &&
                outsideMm.Value>0.0?outsideMm.Value:E1GuideCatalog.Outside(dn);
            double cold=isPipe && coldThicknessMm.HasValue?
                coldThicknessMm.Value:parameters.FallbackColdThicknessMm;
            return Calculate(dn,outside,cold,parameters.Name,fourBolt);
        }

        internal static A22ClampPlan Calculate(int dn,double outside,double cold,string name)
        { return Calculate(dn,outside,cold,name,false); }

        internal static A22ClampPlan Calculate(int dn,double outside,double cold,string name,bool fourBolt)
        {
            if(double.IsNaN(outside) || double.IsInfinity(outside) || outside<=0.0)
                throw new InvalidOperationException("管道外径必须大于 0 mm。");
            if(double.IsNaN(cold) || double.IsInfinity(cold) || cold<0.0)
                throw new InvalidOperationException("保冷厚度必须是大于等于 0 的有限数字。");
            double bearing=A22ClampCatalog.BearingPlateThickness(dn);
            double a=outside+2.0*(bearing+cold)+10.0;
            var row=A22ClampCatalog.ForA(a);
            double b=a/2.0+row.E;
            double innerRadius=a/2.0;
            double outerRadius=innerRadius+row.T;
            if(row.C<=row.T || row.C>=innerRadius)
                throw new InvalidOperationException((fourBolt?"A24":"A22")+" 管夹的 C/T 与当前 A 不相容。");
            double rMin=row.T<=15.0?row.T:2.5*row.T;
            double innerFace=row.C-row.T;
            double flangeRoot=Math.Sqrt(innerRadius*innerRadius-innerFace*innerFace);
            double filletCenterZ=row.C+rMin;
            double centerDistance=outerRadius+rMin;
            double transitionEndY=Math.Sqrt(centerDistance*centerDistance-
                filletCenterZ*filletCenterZ);
            double transitionTangentY=outerRadius*transitionEndY/centerDistance;
            double transitionTangentZ=outerRadius*filletCenterZ/centerDistance;
            double f=fourBolt?A24ClampCatalog.FForA(a):0.0;
            double flangeEnd=b+row.E+f;
            double holeRadius=(row.BoltDiameterMm+3.0)/2.0;
            if(flangeRoot>=b-holeRadius || flangeEnd<=b+holeRadius ||
                transitionEndY>=flangeEnd || (fourBolt && f<=2*holeRadius))
                throw new InvalidOperationException("管夹的 C/T/E/F 与当前 A 不相容。");
            string code=fourBolt?"A24":"A22";
            string number=(name??code).Trim();
            if(number.Length==0) number=code;
            number+="-DN"+dn.ToString(CultureInfo.InvariantCulture)+"-"+
                cold.ToString("0.#",CultureInfo.InvariantCulture);
            return new A22ClampPlan {
                Dn=dn,PipeOutsideMm=outside,ColdThicknessMm=cold,
                BearingPlateThicknessMm=bearing,A=a,B=b,C=row.C,E=row.E,F=f,T=row.T,W=row.W,
                G=row.BoltDiameterMm+3.0,OuterRadiusMm=outerRadius,
                FlangeEndMm=flangeEnd,FlangeRootMm=flangeRoot,
                RMinMm=rMin,TransitionEndYmm=transitionEndY,
                TransitionTangentYmm=transitionTangentY,
                TransitionTangentZmm=transitionTangentZ,
                BoltDiameterMm=row.BoltDiameterMm,
                AllowableLoadKn=fourBolt?0.0:row.AllowableLoadKn,Code=code,
                Number=number,Specification="DN"+dn+" / A="+a.ToString("0.#",CultureInfo.InvariantCulture)+
                    " / C="+row.C+" / E="+row.E+
                    (fourBolt?" / F="+f.ToString("0.#",CultureInfo.InvariantCulture):"")+
                    " / T="+row.T+" / W="+row.W+
                    " / R="+rMin.ToString("0.#",CultureInfo.InvariantCulture)+
                    " / M"+row.BoltDiameterMm
            };
        }

        internal static string Describe(A22ClampPlan plan)
        {
            return plan.Code+" 保冷管用 "+(plan.F>0?"4":"2")+" 螺栓管夹："+plan.Specification+
                "；承重板厚 "+plan.BearingPlateThicknessMm+"，保冷厚 "+
                plan.ColdThicknessMm.ToString("0.#",CultureInfo.InvariantCulture)+
                "；B="+plan.B.ToString("0.#",CultureInfo.InvariantCulture)+
                "，孔径 G="+plan.G+"，过渡圆角 R="+plan.RMinMm+
                (plan.F>0?"；两侧各两套螺栓，孔距 F="+plan.F+" mm":
                    "；允许荷载 "+plan.AllowableLoadKn+" kN")+
                "。编号 "+plan.Number+"。";
        }
    }
}
