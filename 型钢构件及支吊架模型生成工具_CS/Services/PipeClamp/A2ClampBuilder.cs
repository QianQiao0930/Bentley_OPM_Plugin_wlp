using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// A2 标准型 2 螺栓管夹建模：圆柱 ∪ 长方体 → 管夹状剪切截面 → 耳板螺栓孔 → 2 套简化紧固件。
    /// 与 Python <c>A2-[标准型2螺栓管夹].py</c> 的 <c>build_clamp</c> 逐项对齐。
    /// 尺寸为毫米，只有 <see cref="PipeClampFrame.Point"/> 转成 UOR。
    /// </summary>
    internal static class A2ClampBuilder
    {
        internal static List<Element> Build(A2ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)
                throw new InvalidOperationException("A2 管夹需要在三维 DGN 模型中放置。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var frame=new PipeClampFrame(center,scale,axis.X,axis.Y,axis.Z);
            var result=new List<Element>();

            double halfWidth=plan.WidthMm/2.0;
            // 1) 圆柱：轴向沿局部 X，长 = w。
            var body=SolidPrimitiveFactory.Cylinder(frame.Point(-halfWidth,0.0,0.0),
                frame.Point(halfWidth,0.0,0.0),plan.CylinderRadiusMm*scale);
            // 2) 长方体：与圆柱同厚 w（沿 X），长 box_length（沿 Y），宽 box_width（沿 Z）。
            var box=Box(frame,-halfWidth,halfWidth,-plan.BoxLengthMm/2.0,plan.BoxLengthMm/2.0,
                -plan.BoxWidthMm/2.0,plan.BoxWidthMm/2.0);
            SolidPrimitiveFactory.Union(ref body,new[]{box},"长方体与圆柱布尔并");

            // 3) 剪切截面（φA 圆 + 长度 A+2t+2D、宽度 C 的矩形）贯穿减去，成管夹状。
            double margin=A2ClampCatalog.ThroughMarginMm;
            double throughHalf=plan.WidthMm/2.0+margin;
            double cutterLength=plan.InnerDiameterMm+2.0*plan.PlateThicknessMm+
                2.0*plan.EndOffsetDm+2.0*margin;
            var cutters=new List<SolidKernelEntity>();
            cutters.Add(SolidPrimitiveFactory.Cylinder(frame.Point(-throughHalf,0.0,0.0),
                frame.Point(throughHalf,0.0,0.0),plan.InnerDiameterMm/2.0*scale));
            cutters.Add(Box(frame,-throughHalf,throughHalf,-cutterLength/2.0,cutterLength/2.0,
                -plan.PlateWidthCm/2.0,plan.PlateWidthCm/2.0));
            SolidPrimitiveFactory.Subtract(ref body,cutters,"剪切截面裁切管架本体");

            // 4) 上下两对耳板开螺栓孔：孔心距中心 B（沿局部 Y），沿局部 Z 贯穿。
            double holeHalf=plan.BoxWidthMm/2.0+margin;
            var holes=new List<SolidKernelEntity>();
            foreach(double sign in new[]{1.0,-1.0})
            {
                double y=sign*plan.BoltCenterMm;
                holes.Add(SolidPrimitiveFactory.Cylinder(frame.Point(0.0,y,-holeHalf),
                    frame.Point(0.0,y,holeHalf),plan.HoleRadiusMm*scale));
            }
            SolidPrimitiveFactory.Subtract(ref body,holes,"耳板开螺栓孔");
            result.Add(SolidPrimitiveFactory.Element(body,A2ClampCatalog.BodyColor));

            // 5) 每个螺栓孔穿一套简化紧固件（独立实体，与本体分开）。
            foreach(double sign in new[]{1.0,-1.0})
                AddFastener(result,frame,plan,0.0,sign*plan.BoltCenterMm);
            return result;
        }

        /// <summary>轴向沿局部 X 的长方体：截面在 x=x0 平面，沿 +X 拉伸到 x1。</summary>
        private static SolidKernelEntity Box(PipeClampFrame frame,double x0,double x1,
            double y0,double y1,double z0,double z1)
        {
            var points=new[]{ frame.Point(x0,y0,z0),frame.Point(x0,y1,z0),
                frame.Point(x0,y1,z1),frame.Point(x0,y0,z1) };
            return SolidPrimitiveFactory.PolygonPrism(points,frame.Direction(x1-x0,0.0,0.0));
        }

        /// <summary>沿局部 Z 拉伸的六角棱柱（六角螺栓头 / 螺母）。</summary>
        private static SolidKernelEntity Hex(PipeClampFrame frame,double x,double y,
            double z0,double z1,double acrossFlats)
        {
            double radius=acrossFlats/(2.0*Math.Cos(Math.PI/6.0));
            var points=new List<DPoint3d>();
            for(int index=0;index<6;index++)
            {
                double theta=Math.PI/6.0+index*Math.PI/3.0;
                points.Add(frame.Point(x+radius*Math.Cos(theta),y+radius*Math.Sin(theta),z0));
            }
            return SolidPrimitiveFactory.PolygonPrism(points,frame.Direction(0.0,0.0,z1-z0));
        }

        /// <summary>一套简化紧固件：贯穿的螺杆 + 一侧六角螺栓头 + 另一侧六角螺母。</summary>
        private static void AddFastener(List<Element> result,PipeClampFrame frame,
            A2ClampPlan plan,double x,double y)
        {
            double d=plan.BoltDiameterMm;
            double seat=plan.BoxWidthMm/2.0;
            double headHeight=d*A2ClampCatalog.BoltHeadHeightRatio;
            double nutHeight=d*A2ClampCatalog.NutHeightRatio;
            double across=d*A2ClampCatalog.HexAcrossFlatsRatio;
            double margin=A2ClampCatalog.ThroughMarginMm;

            var shank=SolidPrimitiveFactory.Cylinder(
                frame.Point(x,y,-seat-nutHeight-A2ClampCatalog.BoltTipExtraMm),
                frame.Point(x,y,seat),d/2.0*frame.Scale);
            var head=Hex(frame,x,y,seat,seat+headHeight,across);
            var nut=Hex(frame,x,y,-seat-nutHeight,-seat,across);
            SolidPrimitiveFactory.Subtract(ref nut,new[]{SolidPrimitiveFactory.Cylinder(
                frame.Point(x,y,-seat-nutHeight-margin),frame.Point(x,y,-seat+margin),
                plan.HoleRadiusMm*frame.Scale)},"螺母中心孔");

            result.Add(SolidPrimitiveFactory.Element(shank,A2ClampCatalog.BoltColor));
            result.Add(SolidPrimitiveFactory.Element(head,A2ClampCatalog.BoltColor));
            result.Add(SolidPrimitiveFactory.Element(nut,A2ClampCatalog.BoltColor));
        }
    }
}
