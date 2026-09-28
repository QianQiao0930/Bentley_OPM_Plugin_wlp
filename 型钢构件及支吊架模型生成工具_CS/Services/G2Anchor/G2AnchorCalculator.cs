using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// G2 混凝土锚板的参数校验与尺寸解析。与 Python
    /// <c>模块/公共/混凝土锚板.py</c> 的 <c>resolve_options</c> / <c>describe_spec</c> 逐项对齐。
    /// 纯计算，不引用 Bentley API。
    /// </summary>
    internal static class G2AnchorCalculator
    {
        private static string F0(double value) { return value.ToString("0",CultureInfo.InvariantCulture); }

        /// <summary>合并默认值、校验输入，并算出本次生成用的全部毫米尺寸。</summary>
        internal static G2AnchorPlan Calculate(G2AnchorParameters parameters)
        {
            if(parameters==null) throw new ArgumentNullException("parameters");
            var item=G2AnchorCatalog.Require(parameters.SubtypeKey);
            if(!Enum.IsDefined(typeof(G2MountFace),parameters.MountFace))
                throw new InvalidOperationException("安装面只支持：竖直墙面 / 水平楼板顶面 / 水平楼板底面。");

            double spacing;
            if(parameters.SpacingMm.HasValue)
            {
                spacing=parameters.SpacingMm.Value;
                if(double.IsNaN(spacing) || double.IsInfinity(spacing) || spacing<=0.0)
                    throw new InvalidOperationException("螺栓间距 S 必须是正数（mm）。");
                if(spacing<item.MinSpacingMm)
                    throw new InvalidOperationException("螺栓间距 S="+F0(spacing)+
                        " mm 小于 MIN.S="+F0(item.MinSpacingMm)+" mm。");
            }
            else spacing=item.MinSpacingMm;

            double heading=parameters.HeadingDegrees;
            if(double.IsNaN(heading) || double.IsInfinity(heading))
                throw new InvalidOperationException("朝向必须是有限数字（度）。");

            // 螺杆外端 = 螺母外端面 + 露出的丝头；总长 L 不变，多出的部分全部埋入。
            double nutOuter=item.PlateThicknessMm+item.WasherThicknessMm+item.NutHeightMm;
            double outLength=nutOuter+G2AnchorCatalog.BoltProtrusionMm;
            double embedment=item.BoltLengthMm-outLength;
            if(embedment<item.RequiredEmbedmentMm)
                throw new InvalidOperationException("M"+F0(item.BoltDiameterMm)+" 锚栓有效埋深 "+
                    embedment.ToString("0.#",CultureInfo.InvariantCulture)+" mm 小于要求的 "+
                    F0(item.RequiredEmbedmentMm)+" mm，请核对数据表。");

            string plateSpecification=F0(spacing+2.0*G2AnchorCatalog.PlateMarginMm)+"×"+
                F0(spacing+2.0*G2AnchorCatalog.PlateMarginMm)+"×"+F0(item.PlateThicknessMm)+
                "（S="+F0(spacing)+"，4-φ"+F0(item.HoleDiameterMm)+"）";
            string boltSpecification="M"+F0(item.BoltDiameterMm)+"×"+F0(item.BoltLengthMm);

            return new G2AnchorPlan {
                Parameters=parameters,Item=item,
                SpacingMm=spacing,
                PlateSideMm=spacing+2.0*G2AnchorCatalog.PlateMarginMm,
                PlateThicknessMm=item.PlateThicknessMm,
                HoleDiameterMm=item.HoleDiameterMm,
                BoltDiameterMm=item.BoltDiameterMm,
                BoltLengthMm=item.BoltLengthMm,
                BoltOutLengthMm=outLength,
                RequiredEmbedmentMm=item.RequiredEmbedmentMm,
                ActualEmbedmentMm=embedment,
                SleeveDiameterMm=item.BoltDiameterMm*G2AnchorCatalog.SleeveDiameterFactor,
                SleeveLengthMm=embedment*G2AnchorCatalog.SleeveEmbedFraction,
                NutAcrossFlatsMm=item.NutAcrossFlatsMm,
                NutHeightMm=item.NutHeightMm,
                WasherOutsideMm=item.WasherOutsideMm,
                WasherThicknessMm=item.WasherThicknessMm,
                MinEdgeDistanceMm=item.MinEdgeDistanceMm,
                MinThicknessMm=item.MinThicknessMm,
                TensionKn=item.TensionKn,
                ShearKn=item.ShearKn,
                BoltCount=4,
                CellName=G2AnchorCatalog.CellName,
                AssemblyTag="G2-"+item.Key,
                PlateSpecification=plateSpecification,
                BoltSpecification=boltSpecification,
                AssemblySpecification="G2-"+item.Key+"：锚板 "+plateSpecification+
                    "，膨胀锚栓 "+boltSpecification+" ×4"
            };
        }

        /// <summary>子项下拉项的标签，例如 “A  |  M8×80  |  板厚 10  |  孔 φ10”。</summary>
        internal static string DescribeItem(G2AnchorItem item)
        {
            if(item==null) throw new ArgumentNullException("item");
            return item.Key+"  |  M"+F0(item.BoltDiameterMm)+"×"+F0(item.BoltLengthMm)+
                "  |  板厚 "+F0(item.PlateThicknessMm)+"  |  孔 φ"+F0(item.HoleDiameterMm);
        }

        /// <summary>该子项在 MIN.S 下的标准锚板尺寸读数。</summary>
        internal static string DescribePlate(G2AnchorItem item)
        {
            if(item==null) throw new ArgumentNullException("item");
            double side=item.MinSpacingMm+2.0*G2AnchorCatalog.PlateMarginMm;
            return F0(side)+"×"+F0(side)+"×"+F0(item.PlateThicknessMm)+"（板厚 T="+
                F0(item.PlateThicknessMm)+"）";
        }

        /// <summary>该子项的锚栓读数。</summary>
        internal static string DescribeBolt(G2AnchorItem item)
        {
            if(item==null) throw new ArgumentNullException("item");
            return "M"+F0(item.BoltDiameterMm)+"×"+F0(item.BoltLengthMm)+" 膨胀锚栓，孔径 φ"+
                F0(item.HoleDiameterMm);
        }

        /// <summary>面板规格信息行。</summary>
        internal static string Describe(G2AnchorPlan plan)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            return plan.Item.Key+" 子项：锚板 "+F0(plan.PlateSideMm)+"×"+F0(plan.PlateSideMm)+"×"+
                F0(plan.PlateThicknessMm)+"，4-φ"+F0(plan.HoleDiameterMm)+" 孔（S="+F0(plan.SpacingMm)+
                "）；M"+F0(plan.BoltDiameterMm)+"×"+F0(plan.BoltLengthMm)+" 膨胀锚栓 ×"+plan.BoltCount+
                "，有效埋深 "+F0(plan.ActualEmbedmentMm)+"（≥"+F0(plan.RequiredEmbedmentMm)+
                "）；混凝土边缘 MIN.C="+F0(plan.MinEdgeDistanceMm)+"、MIN.h="+F0(plan.MinThicknessMm)+"。"+
                "允许拉力 "+plan.TensionKn.ToString("0.#",CultureInfo.InvariantCulture)+
                " kN、剪力 "+plan.ShearKn.ToString("0.#",CultureInfo.InvariantCulture)+" kN。";
        }

        internal static string DescribeMountFace(G2MountFace face)
        {
            switch(face)
            {
                case G2MountFace.FloorTop: return "水平楼板顶面（螺栓朝下）";
                case G2MountFace.CeilingBottom: return "水平楼板底面（螺栓朝上）";
                default: return "竖直墙面（螺栓水平）";
            }
        }

        /// <summary>
        /// 局部坐标轴在世界系中的单位方向，与 Python <c>_PlateFrame.__init__</c> 逐项一致。
        /// 纯数学，供 <see cref="G2AnchorFrame"/> 与纯计算检查工程共用，避免两份定义。
        /// 局部 +X 恒为混凝土外法向（锚栓露出的那一侧）。
        /// </summary>
        internal static void Axes(G2MountFace mount,double headingDegrees,
            out double[] axisX,out double[] axisY,out double[] axisZ)
        {
            double angle=headingDegrees*Math.PI/180.0;
            double c=Math.Cos(angle),s=Math.Sin(angle);
            switch(mount)
            {
                case G2MountFace.FloorTop:
                    axisX=new double[]{0.0,0.0,1.0};
                    axisY=new double[]{c,s,0.0};
                    axisZ=new double[]{-s,c,0.0};
                    break;
                case G2MountFace.CeilingBottom:
                    axisX=new double[]{0.0,0.0,-1.0};
                    axisY=new double[]{c,s,0.0};
                    axisZ=new double[]{s,-c,0.0};
                    break;
                default:
                    axisX=new double[]{c,s,0.0};
                    axisY=new double[]{-s,c,0.0};
                    axisZ=new double[]{0.0,0.0,1.0};
                    break;
            }
        }
    }
}
