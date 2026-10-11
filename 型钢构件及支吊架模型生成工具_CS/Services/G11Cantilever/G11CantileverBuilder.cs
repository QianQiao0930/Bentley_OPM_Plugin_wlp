using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>以辅助线顶面标高生成 G11 型钢及锚栓，全部几何复用公共工厂。</summary>
    internal static class G11CantileverBuilder
    {
        internal static IList<Element> Build(D2CantileverPlan plan, PipeClampSelection line)
        {
            if (plan == null || plan.ConcreteAnchor == null)
            {
                throw new ArgumentNullException(nameof(plan));
            }

            if (line == null)
            {
                throw new ArgumentNullException(nameof(line));
            }

            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
            {
                throw new InvalidOperationException("G11 悬臂架需要三维活动模型。");
            }

            double horizontalLength = Math.Sqrt(line.AxisX * line.AxisX + line.AxisY * line.AxisY);
            if (horizontalLength <= 1e-9)
            {
                throw new InvalidOperationException("辅助线方向无效。");
            }

            double sign = plan.Parameters.Reverse ? -1 : 1;
            double runX = sign * line.AxisX / horizontalLength;
            double runY = sign * line.AxisY / horizontalLength;
            double originX = plan.Parameters.Reverse ? line.EndX : line.StartX;
            double originY = plan.Parameters.Reverse ? line.EndY : line.StartY;
            double originZ = plan.Parameters.Reverse ? line.EndZ : line.StartZ;
            double scale = model.GetModelInfo().UorPerMeter / 1000;
            Func<double, double, double, DPoint3d> point = (x, y, z) => new DPoint3d(
                (originX + runX * x - runY * y) * scale,
                (originY + runY * x + runX * y) * scale,
                (originZ + z) * scale);
            var run = new DVector3d(runX, runY, 0);
            var side = new DVector3d(-runY, runX, 0);
            G11CantileverPlan anchorPlan = plan.ConcreteAnchor;
            var parts = new List<Element>();
            var beam = SteelMemberFactory.AlongAxisBody(D2CantileverCatalog.Mode(plan.Variant),
                point(0, plan.SectionAnchorYmm, plan.SectionAnchorZmm), scale, side,
                new DVector3d(0, 0, anchorPlan.BeamVerticalSign), run, plan.BeamLengthMm);
            parts.Add(SolidPrimitiveFactory.Element(beam, SupportSteelAppearance.Color));

            if (anchorPlan.ConnectionLengthMm > 0)
            {
                // 槽钢绕竖轴转 90° 后以翼缘锚固，开口沿 side，与横担一致。
                // 角钢下置段的上端与侧面分别贴合横担水平肢和竖直肢的内表面。
                string modeName = anchorPlan.ConnectionWidthAlongSide ? "lower_left" : "outer_corner";
                ModeData mode = ProfileLookup.Mode(RuntimeData.Families, plan.Variant.Family,
                    D2CantileverCatalog.Profile(plan.Variant).Name, modeName);
                var connection = SteelMemberFactory.AlongAxisBody(mode,
                    point(anchorPlan.ConnectionStartXMm, anchorPlan.ConnectionStartYMm, anchorPlan.ConnectionStartZMm),
                    scale, anchorPlan.ConnectionWidthAlongSide ? side : run,
                    anchorPlan.ConnectionWidthAlongSide ? new DVector3d(-run.X, -run.Y, 0) : side, new DVector3d(0, 0, plan.Parameters.Type == 2 ? 1 : -1),
                    anchorPlan.ConnectionLengthMm);
                parts.Add(SolidPrimitiveFactory.Element(connection, SupportSteelAppearance.Color));
            }

            var normal = new DVector3d(
                anchorPlan.BoltNormalX * run.X + anchorPlan.BoltNormalY * side.X,
                anchorPlan.BoltNormalX * run.Y + anchorPlan.BoltNormalY * side.Y,
                anchorPlan.BoltNormalZ);
            DVector3d boltPlaneY = anchorPlan.BoltNormalX != 0 ? side : run;
            var boltPlaneZ = new DVector3d(
                normal.Y * boltPlaneY.Z - normal.Z * boltPlaneY.Y,
                normal.Z * boltPlaneY.X - normal.X * boltPlaneY.Z,
                normal.X * boltPlaneY.Y - normal.Y * boltPlaneY.X);

            foreach (G11AnchorLocation location in anchorPlan.Anchors)
            {
                var frame = new G2AnchorFrame(point(location.XMm, location.YMm, location.ZMm),
                    scale, normal, boltPlaneY, boltPlaneZ);
                parts.AddRange(G2AnchorBuilder.BuildSingleBolt(anchorPlan.Bolt, frame));
            }

            return parts;
        }
    }
}
