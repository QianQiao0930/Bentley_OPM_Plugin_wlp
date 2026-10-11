using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 使用公共型钢和连接板服务创建 N2 悬臂架实体。
    /// </summary>
    internal static class N2CantileverBuilder
    {

        /// <summary>
        /// 创建尚未写入模型的构件，供预览会话统一管理。
        /// </summary>
        internal static IList<Element> Build(N2CantileverPlan plan, N2CantileverFrame f)
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
                throw new InvalidOperationException("N2 需要三维活动模型。");
            double scale = model.GetModelInfo().UorPerMeter / 1000;
            var run = new DVector3d(f.RunX, f.RunY, 0);
            var side = new DVector3d(-f.RunY, f.RunX, 0);
            var back = new DVector3d(-f.RunX, -f.RunY, 0);
            var down = new DVector3d(0, 0, -1);
            Func<double, double, double, DPoint3d> point = (x, y, z) => { var p = f.Point(x, y, z); return new DPoint3d(p[0] * scale, p[1] * scale, p[2] * scale); };
            var v = plan.Variant;
            var bodies = new List<SolidKernelEntity>();
            // 两根 A 的腹板朝框架内侧，翼缘朝外；两根构件的顶面均为局部 Z = 0。
            foreach (int sign in new[] { -1, 1 })
            {
                var outward = new DVector3d(sign * side.X, sign * side.Y, 0);
                bodies.Add(SteelMemberFactory.AlongAxisBody(N2CantileverCatalog.Mode(v, false),
                    point(plan.RootMm, sign * (plan.L2Mm - plan.AWidthMm) / 2, 0), scale, outward, down, run, plan.ACutMm));
            }
            // 类型 1 的外侧腹板面按 L1 定位；类型 2 的 B 构件开口背离管道。
            var stations = plan.BCount == 2 ? new[] { plan.OuterBFaceMm, plan.InnerBFaceMm } : new[] { plan.OuterBFaceMm };
            for (int i = 0; i < stations.Length; i++)
            {
                var profileX = plan.Parameters.Type == 2 && i == 0 ? run : back;
                bodies.Add(SteelMemberFactory.AlongAxisBody(N2CantileverCatalog.Mode(v, true),
                    point(stations[i], -plan.BLengthMm / 2, 0), scale, profileX, down, side, plan.BLengthMm));
            }
            var body = bodies[0];
            bodies.RemoveAt(0);
            // 先连接横向构件，再连接第二根 A，使相并顺序保持接触面连续。
            var secondA = bodies[0];
            bodies.RemoveAt(0);
            bodies.Add(secondA);
            SolidPrimitiveFactory.Union(ref body, bodies, "N2 顶平双悬臂焊接组合");
            var parts = new List<Element> { SolidPrimitiveFactory.Element(body, SupportSteelAppearance.Color) };
            double heading = Math.Atan2(f.RunY, f.RunX) * 180 / Math.PI + 180;
            var plate = N8Catalog.Resolve(v.PlateType, "N", heading, G2MountFace.Wall);
            foreach (int sign in new[] { -1, 1 })
            {
                var anchor = point(plan.RootMm, sign * plan.L2Mm / 2, -plan.AHeightMm / 2);
                parts.AddRange(N8Builder.Build(plate, anchor));
                if (plan.Parameters.ShowPreweld)
                {
                    var baseFrame = new G2AnchorFrame(anchor, scale, heading, G2MountFace.Wall);
                    var padFrame = new G2AnchorFrame(baseFrame.Point(plate.T, 0, 0), scale, heading, G2MountFace.Wall);
                    parts.Add(Transparent(N8Builder.BuildPlate(plate, padFrame)));
                    var outer = SolidPrimitiveFactory.Cylinder(baseFrame.Point(2 * plate.T, 0, 0),
                        baseFrame.Point(plan.Parameters.PreweldMm, 0, 0), 50 * scale);
                    var inner = SolidPrimitiveFactory.Cylinder(baseFrame.Point(2 * plate.T - 2, 0, 0),
                        baseFrame.Point(plan.Parameters.PreweldMm + 2, 0, 0), 46 * scale);
                    SolidPrimitiveFactory.Subtract(ref outer, new[] { inner }, "N2 预焊件占位空心管");
                    parts.Add(Transparent(SolidPrimitiveFactory.Element(outer, SupportSteelAppearance.Color)));
                }
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
                throw new InvalidOperationException("N2 预焊件占位透明度设置失败。");
            return element;
        }
    }
}
