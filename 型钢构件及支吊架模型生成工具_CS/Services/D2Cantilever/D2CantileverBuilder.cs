using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>以辅助线承载顶面为基准，复用型钢实体及 G2 连接板建模。</summary>
    internal static class D2CantileverBuilder
    {
        internal static IList<Element> Build(D2CantileverPlan plan, PipeClampSelection line)
        {
            if (plan == null) throw new ArgumentNullException("plan");
            if (plan.Parameters.Kind == "G11")
            {
                return G11CantileverBuilder.Build(plan, line);
            }

            if (line == null) throw new ArgumentNullException("line");
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
                throw new InvalidOperationException("悬臂架需要三维活动模型。");
            double length = Math.Sqrt(line.AxisX * line.AxisX + line.AxisY * line.AxisY);
            if (length <= 1e-9) throw new InvalidOperationException("辅助线方向无效。");
            double sign = plan.Parameters.Reverse ? -1 : 1;
            double rx = sign * line.AxisX / length, ry = sign * line.AxisY / length;
            double ox = plan.Parameters.Reverse ? line.EndX : line.StartX;
            double oy = plan.Parameters.Reverse ? line.EndY : line.StartY;
            double oz = plan.Parameters.Reverse ? line.EndZ : line.StartZ;
            double scale = model.GetModelInfo().UorPerMeter / 1000;
            Func<double, double, double, DPoint3d> point = (x, y, z) =>
                new DPoint3d((ox + rx * x - ry * y) * scale,
                    (oy + ry * x + rx * y) * scale, (oz + z) * scale);
            var side = new DVector3d(-ry, rx, 0);
            var run = new DVector3d(rx, ry, 0);
            bool centered = plan.Variant.Family == "hot_rolled_h";
            var up = new DVector3d(0, 0, centered ? 1 : -1);
            var origin = point(plan.BeamStartMm, plan.SectionAnchorYmm, plan.SectionAnchorZmm);
            var body = SteelMemberFactory.AlongAxisBody(D2CantileverCatalog.Mode(plan.Variant),
                origin, scale, side, up, run, plan.BeamLengthMm);
            var parts = new List<Element> { SolidPrimitiveFactory.Element(body, SupportSteelAppearance.Color) };
            if (plan.Plate != null)
                parts.AddRange(G2AnchorBuilder.Build(plan.Plate,
                    point(plan.Parameters.PlateOffsetMm, 0, -plan.SectionHeightMm / 2)));
            return parts;
        }
    }
}
