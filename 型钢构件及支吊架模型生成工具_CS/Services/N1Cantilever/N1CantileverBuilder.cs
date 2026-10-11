using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 使用公共型钢和连接板服务创建 N1 悬臂架实体。
    /// </summary>
    internal static class N1CantileverBuilder
    {

        /// <summary>
        /// 创建尚未写入模型的构件，供预览会话统一管理。
        /// </summary>
        internal static IList<Element> Build(N1CantileverPlan plan, N1CantileverFrame f)
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
                throw new InvalidOperationException("N1 需要三维活动模型。");
            double scale = model.GetModelInfo().UorPerMeter / 1000;
            var run = new DVector3d(f.RunX, f.RunY, 0);
            var side = new DVector3d(-f.RunY, f.RunX, 0);
            var back = new DVector3d(-f.RunX, -f.RunY, 0);
            var down = new DVector3d(0, 0, -1);
            Func<double, double, double, DPoint3d> point = (x, y, z) => { var p = f.Point(x, y, z); return new DPoint3d(p[0] * scale, p[1] * scale, p[2] * scale); };
            var v = plan.Variant;
            var a = ProfileLookup.Profile(RuntimeData.Families, v.Family, v.ProfileA);
            if (a == null)
                throw new InvalidOperationException("型钢目录缺少 " + v.ProfileA);
            double width = a.Dimensions["B"];
            double height = v.Family == "equal_angle" ? width : a.Dimensions["H"];
            // 沿用 N4 的标高约定：辅助线位于构件 A 的承载顶面。
            var body = SteelMemberFactory.AlongAxisBody(N1CantileverCatalog.Mode(v, false),
                point(plan.RootMm, -width / 2, 0), scale, side, down, run, plan.ACutMm);
            if (plan.Parameters.Type == 2)
            {
                // 角钢 B 的上翼缘下表面搭在 A 的顶面。
                // 槽钢 A、B 的截面中心标高一致，A 的末端贴合 B 的腹板内侧面。
                var transverse = SteelMemberFactory.AlongAxisBody(N1CantileverCatalog.Mode(v, true),
                    point(plan.RootMm + plan.L1Mm, -plan.L2Mm / 2, plan.BTopOffsetMm), scale, back, down, side, plan.L2Mm);
                SolidPrimitiveFactory.Union(ref body, new[] { transverse }, "N1 构件 A 与 B 焊接组合");
            }
            var parts = new List<Element> { SolidPrimitiveFactory.Element(body, SupportSteelAppearance.Color) };
            double heading = Math.Atan2(f.RunY, f.RunX) * 180 / Math.PI + 180;
            // N8 原点位于连接板的框架侧表面，板厚向设备侧延伸。
            var plate = N8Catalog.Resolve(v.PlateType, "N", heading, G2MountFace.Wall);
            parts.AddRange(N8Builder.Build(plate, point(plan.RootMm, 0, -height / 2)));
            if (plan.Parameters.ShowPreweld)
            {
                var baseFrame = new G2AnchorFrame(point(plan.RootMm, 0, -height / 2), scale, heading, G2MountFace.Wall);
                var padFrame = new G2AnchorFrame(baseFrame.Point(plate.T, 0, 0), scale, heading, G2MountFace.Wall);
                parts.Add(Transparent(N8Builder.BuildPlate(plate, padFrame)));
                var outer = SolidPrimitiveFactory.Cylinder(baseFrame.Point(2 * plate.T, 0, 0),
                    baseFrame.Point(plan.Parameters.PreweldMm, 0, 0), 50 * scale);
                var inner = SolidPrimitiveFactory.Cylinder(baseFrame.Point(2 * plate.T - 2, 0, 0),
                    baseFrame.Point(plan.Parameters.PreweldMm + 2, 0, 0), 46 * scale);
                SolidPrimitiveFactory.Subtract(ref outer, new[] { inner }, "N1 预焊件占位空心管");
                parts.Add(Transparent(SolidPrimitiveFactory.Element(outer, SupportSteelAppearance.Color)));
            }
            return parts;
        }

        /// <summary>
        /// 为预焊件参考占位设置 75% 透明度。
        /// </summary>
        private static Element Transparent(Element element)
        {
            var style = new ElementPropertiesSetter();
            style.SetTransparency(0.75);
            if (!style.Apply(element))
                throw new InvalidOperationException("N1 预焊件占位透明度设置失败。");
            return element;
        }
    }
}
