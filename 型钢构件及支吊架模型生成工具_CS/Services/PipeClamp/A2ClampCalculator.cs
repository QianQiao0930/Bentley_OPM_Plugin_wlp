using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// A2 标准型 2 螺栓管夹的尺寸解析。与 Python <c>A2-[标准型2螺栓管夹].py</c> 的
    /// <c>build_clamp</c> / <c>build_on_pick</c> 尺寸口径逐项对齐。纯计算，不引用 Bentley API。
    /// </summary>
    internal static class A2ClampCalculator
    {
        private static string F0(double value)
        { return value.ToString("0",CultureInfo.InvariantCulture); }

        /// <summary>
        /// 按管径与保温厚度解析尺寸。
        /// <paramref name="isPipe"/> 为真表示点选的是 OpenPlant 管道（按 <paramref name="nominalMm"/>
        /// 匹配表 1）；匹配不上或点选直线时改用面板兜底管径。保温厚度为 null 时同样用面板兜底值。
        /// </summary>
        internal static A2ClampPlan Calculate(A2ClampParameters parameters,bool isPipe,
            double? nominalMm,double? insulationMm)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            int? matched=isPipe?A2ClampCatalog.MatchDn(nominalMm):null;
            int dn=matched.HasValue?matched.Value:parameters.FallbackDn;
            double insulation=insulationMm.HasValue?insulationMm.Value:parameters.FallbackInsulationMm;
            return Calculate(dn,insulation);
        }

        /// <summary>按表 1 管径与保温厚度解析尺寸（保温层存在时按外径放大内孔）。</summary>
        internal static A2ClampPlan Calculate(int dn,double insulationMm)
        {
            if(double.IsNaN(insulationMm) || double.IsInfinity(insulationMm) || insulationMm<0.0)
                throw new InvalidOperationException("保温厚度必须是大于等于 0 的数字（mm）。");
            var row=A2ClampCatalog.Require(dn);
            double a=row.A,b=row.B,c=row.C,d=row.D;
            if(A2ClampCatalog.AccommodateInsulation && insulationMm>0.0)
            {
                // 按保温层外径放大内孔：孔径 A′ = A + 2×保温厚度。螺栓孔心距中心 B 是
                // 「半径向」尺寸，必须同步外移同样的保温厚度，否则孔会落进放大后的孔洞区域
                // 被剪掉，螺栓随之错位。
                a+=2.0*insulationMm;
                b+=insulationMm;
            }
            double thickness=row.PlateThickness,width=row.Width;
            double cylinderDiameter=a+2.0*thickness;
            double boxLength=a+2.0*d+2.0*thickness;
            double boxWidth=c+2.0*thickness;
            foreach(double value in new[]{a,c,d,thickness,width,cylinderDiameter,boxLength,boxWidth})
                if(double.IsNaN(value) || double.IsInfinity(value) || value<=0.0)
                    throw new InvalidOperationException("尺寸参数必须是有限的正数。");

            double boltDiameter=row.BoltDiameterMm;
            double holeRadius=(boltDiameter+2.0)/2.0;
            string bodySpecification="DN"+dn.ToString(CultureInfo.InvariantCulture)+"（"+row.Nps+
                "，A="+F0(a)+"，C="+F0(c)+"，t="+F0(thickness)+"，w="+F0(width)+"）";

            return new A2ClampPlan {
                Dn=dn,InsulationMm=insulationMm,
                InnerDiameterMm=a,BoltCenterMm=b,PlateWidthCm=c,EndOffsetDm=d,
                PlateThicknessMm=thickness,WidthMm=width,Nps=row.Nps,Bolt=row.Bolt,
                BoltDiameterMm=boltDiameter,
                CylinderDiameterMm=cylinderDiameter,CylinderRadiusMm=cylinderDiameter/2.0,
                BoxLengthMm=boxLength,BoxWidthMm=boxWidth,HoleRadiusMm=holeRadius,
                BoltCount=2,
                AssemblyTag="DN"+dn.ToString(CultureInfo.InvariantCulture),
                AssemblySpecification=bodySpecification,
                BodySpecification=bodySpecification,
                BoltSpecification=row.Bolt,
                CellName=A2ClampCatalog.CellName
            };
        }

        /// <summary>面板规格信息行。</summary>
        internal static string Describe(A2ClampPlan plan)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            string text="标准型 2 螺栓管夹：DN"+plan.Dn+"（"+plan.Nps+"，"+plan.Bolt+"）；"+
                "圆柱 φ"+F0(plan.CylinderDiameterMm)+"（A+2t="+F0(plan.InnerDiameterMm)+"+2×"+
                F0(plan.PlateThicknessMm)+"）、轴向长 "+F0(plan.WidthMm)+"；长方体 长"+
                F0(plan.BoxLengthMm)+"（A+2D+2t）×宽"+F0(plan.BoxWidthMm)+"（C+2t）×厚"+
                F0(plan.WidthMm)+"；螺栓孔 φ"+F0(plan.HoleRadiusMm*2.0)+"，孔心距中心 "+
                F0(plan.BoltCenterMm)+"（B）。";
            if(plan.InsulationMm>0.0)
                text+=" 保温厚度 "+F0(plan.InsulationMm)+" mm"+
                    (A2ClampCatalog.AccommodateInsulation?"，已放大内孔。":"（未放大内孔）。");
            return text;
        }
    }
}
