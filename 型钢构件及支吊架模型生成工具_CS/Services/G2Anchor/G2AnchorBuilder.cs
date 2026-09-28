using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 构造 G2 混凝土锚板单元的子元素：一块带 4 个螺栓孔的正方形锚板 + 4 根膨胀锚栓。
    /// 与 Python <c>模块/公共/混凝土锚板.py</c> 的 <c>_add_plate</c> / <c>_add_bolt</c> 逐项对齐。
    /// 所有输入尺寸为毫米，只有 <see cref="G2AnchorFrame.Point"/> 转成 UOR。
    /// </summary>
    internal static class G2AnchorBuilder
    {
        internal static List<Element> Build(G2AnchorPlan plan,DPoint3d origin)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)
                throw new InvalidOperationException("G2 混凝土锚板需要在三维 DGN 模型中放置。");
            var frame=new G2AnchorFrame(origin,model.GetModelInfo().UorPerMeter/1000.0,
                plan.Parameters.HeadingDegrees,plan.MountFace);
            var result=new List<Element>();
            AddPlate(result,frame,plan);
            AddBolts(result,frame,plan);
            return result;
        }

        /// <summary>正方形锚板 (S+100)×(S+100)×T，一次拉伸 + 四个螺栓孔。</summary>
        private static void AddPlate(List<Element> result,G2AnchorFrame frame,G2AnchorPlan plan)
        {
            double half=plan.PlateSideMm/2.0;
            // (y, z) 逆时针 -> 法向 +X，沿 +X 拉伸到 x ∈ [0, T]。
            var corners=new[]{ frame.Point(0.0,-half,-half),frame.Point(0.0,half,-half),
                frame.Point(0.0,half,half),frame.Point(0.0,-half,half) };
            var body=SolidPrimitiveFactory.PolygonPrism(corners,
                frame.Direction(plan.PlateThicknessMm,0.0,0.0));

            double holeRadius=plan.HoleDiameterMm/2.0*frame.Scale;
            double holeHalf=plan.SpacingMm/2.0;
            var cutters=new List<SolidKernelEntity>();
            foreach(double y in new[]{-holeHalf,holeHalf})
                foreach(double z in new[]{-holeHalf,holeHalf})
                    cutters.Add(SolidPrimitiveFactory.Cylinder(
                        frame.Point(-G2AnchorCatalog.CutterExtensionMm,y,z),
                        frame.Point(plan.PlateThicknessMm+G2AnchorCatalog.CutterExtensionMm,y,z),
                        holeRadius));
            SolidPrimitiveFactory.Subtract(ref body,cutters,"锚板螺栓孔");
            result.Add(SolidPrimitiveFactory.Element(body,G2AnchorCatalog.PlateColor));
        }

        private static void AddBolts(List<Element> result,G2AnchorFrame frame,G2AnchorPlan plan)
        {
            double half=plan.SpacingMm/2.0;
            foreach(double y in new[]{-half,half})
                foreach(double z in new[]{-half,half})
                    AddBolt(result,frame,plan,y,z);
        }

        /// <summary>一根膨胀锚栓：埋入端套管 + 螺杆 + 垫圈 + 六角螺母，不做布尔融合（允许重合）。</summary>
        private static void AddBolt(List<Element> result,G2AnchorFrame frame,G2AnchorPlan plan,
            double y,double z)
        {
            double embed=plan.ActualEmbedmentMm;
            double outLength=plan.BoltOutLengthMm;
            double plateT=plan.PlateThicknessMm;

            // 埋入端膨胀套管（比螺杆略粗，只占埋入段的前一部分）
            result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                frame.Point(-embed,y,z),frame.Point(-embed+plan.SleeveLengthMm,y,z),
                plan.SleeveDiameterMm/2.0*frame.Scale),G2AnchorCatalog.SleeveColor));

            // 螺杆：从埋入端一直伸到外端（外端超出螺母一个露头长度）
            result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                frame.Point(-embed,y,z),frame.Point(outLength,y,z),
                plan.BoltDiameterMm/2.0*frame.Scale),G2AnchorCatalog.BoltColor));

            // 垫圈：紧贴板正面
            result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                frame.Point(plateT,y,z),frame.Point(plateT+plan.WasherThicknessMm,y,z),
                plan.WasherOutsideMm/2.0*frame.Scale),G2AnchorCatalog.BoltColor));

            // 六角螺母：垫圈外侧；螺杆再向外露出露头长度
            result.Add(SolidPrimitiveFactory.Element(HexPrism(frame,y,z,plateT+plan.WasherThicknessMm,
                plan.NutHeightMm,plan.NutAcrossFlatsMm),G2AnchorCatalog.NutColor));
        }

        /// <summary>正六边形拉伸（螺母外形）。xBack 为螺母内端面的局部 X。</summary>
        private static SolidKernelEntity HexPrism(G2AnchorFrame frame,double y,double z,
            double xBack,double height,double acrossFlats)
        {
            double radius=acrossFlats/Math.Sqrt(3.0);
            var points=new List<DPoint3d>();
            for(int index=0;index<6;index++)
            {
                double angle=Math.PI*index/3.0;
                points.Add(frame.Point(xBack,y+radius*Math.Cos(angle),
                    z+radius*Math.Sin(angle)));
            }
            return SolidPrimitiveFactory.PolygonPrism(points,frame.Direction(height,0.0,0.0));
        }
    }
}
