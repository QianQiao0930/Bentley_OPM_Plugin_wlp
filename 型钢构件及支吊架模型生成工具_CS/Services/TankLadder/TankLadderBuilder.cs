using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class TankLadderBuilder
    {
        internal static Element Build(TankLadderPlan plan, DPoint3d origin)
        {
            if (plan == null) throw new ArgumentNullException("plan");
            if (double.IsNaN(origin.X) || double.IsInfinity(origin.X) || double.IsNaN(origin.Y) ||
                double.IsInfinity(origin.Y) || double.IsNaN(origin.Z) || double.IsInfinity(origin.Z))
                throw new InvalidOperationException("水箱爬梯放置点无效。");
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d) throw new InvalidOperationException("水箱爬梯需要三维活动模型。");
            double scale = model.GetModelInfo().UorPerMeter / 1000;
            if (scale <= 0 || double.IsNaN(scale) || double.IsInfinity(scale))
                throw new InvalidOperationException("模型长度单位无效。");
            var angle = ProfileLookup.Mode(RuntimeData.Families, "equal_angle", TankLadderCatalog.AngleProfile, "outer_corner");
            var bodies = new List<SolidKernelEntity>();
            // Join from the bottom angle, so each successive member touches the connected structure.
            bodies.Add(SteelMemberFactory.AlongAxisBody(angle, P(plan.BottomAngleOrigin, scale), scale,
                new DVector3d(0, 1, 0), new DVector3d(0, 0, 1), new DVector3d(1, 0, 0), plan.BottomAngleLengthMm));
            for (int i = 0; i < 2; i++)
                bodies.Add(SteelMemberFactory.AlongAxisBody(angle, P(plan.PostOrigins[i], scale), scale,
                    new DVector3d(i == 0 ? -1 : 1, 0, 0), new DVector3d(0, -1, 0), new DVector3d(0, 0, 1), TankLadderCatalog.FrameHeightMm));
            foreach (var leg in plan.Legs) bodies.Add(Leg(leg, scale));
            foreach (var at in plan.ReinforcementOrigins)
            {
                double t = TankLadderCatalog.ReinforcementThicknessMm / 2, w = TankLadderCatalog.ReinforcementWidthMm / 2;
                bodies.Add(SolidPrimitiveFactory.PolygonPrism(new[] { P(at.X - t, at.Y, at.Z - w, scale),
                    P(at.X + t, at.Y, at.Z - w, scale), P(at.X + t, at.Y, at.Z + w, scale),
                    P(at.X - t, at.Y, at.Z + w, scale) }, new DVector3d(0, TankLadderCatalog.ReinforcementLengthMm * scale, 0)));
            }
            foreach (var at in plan.RungCenters)
                bodies.Add(SolidPrimitiveFactory.Cylinder(P(at.X - plan.RungLengthMm / 2, at.Y, at.Z, scale),
                    P(at.X + plan.RungLengthMm / 2, at.Y, at.Z, scale), TankLadderCatalog.RungDiameterMm / 2 * scale));
            var parts = new List<Element>();
            if (plan.Parameters.MergeComponents)
            {
                var merged = bodies[0];
                for (int i = 1; i < bodies.Count; i++)
                    SolidPrimitiveFactory.Union(ref merged, new[] { bodies[i] }, "水箱爬梯构件 " + (i + 1));
                parts.Add(SolidPrimitiveFactory.Element(merged, uint.MaxValue));
            }
            else foreach (var body in bodies) parts.Add(SolidPrimitiveFactory.Element(body, uint.MaxValue));
            var cell = new CellHeaderElement(model, TankLadderCatalog.CellName, DPoint3d.Zero, DMatrix3d.Identity, parts);
            var rotation = DTransform3d.Rotation(2, Angle.FromRadians(plan.Parameters.HeadingDegrees * Math.PI / 180));
            cell.ApplyTransform(new TransformInfo(DTransform3d.Multiply(DTransform3d.FromTranslation(origin), rotation)));
            return cell;
        }

        private static SolidKernelEntity Leg(TankLadderLeg leg, double scale)
        {
            double t = TankLadderCatalog.LegThicknessMm / 2, w = TankLadderCatalog.LegWidthMm / 2;
            var at = leg.Start;
            var profile = CurveVector.Create(CurveVector.BoundaryType.Outer);
            var corners = new[] { P(at.X - t, at.Y, at.Z - w, scale), P(at.X + t, at.Y, at.Z - w, scale),
                P(at.X + t, at.Y, at.Z + w, scale), P(at.X - t, at.Y, at.Z + w, scale) };
            for (int i = 0; i < 4; i++) profile.Add(CurvePrimitive.CreateLine(new DSegment3d(corners[i], corners[(i + 1) % 4])));
            var path = CurveVector.Create(CurveVector.BoundaryType.Open);
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(P(at, scale), P(leg.ShortEnd, scale))));
            DEllipse3d arc;
            if (!DEllipse3d.TryCircularArcFromStartMiddleEnd(P(leg.ShortEnd, scale), P(leg.ArcMiddle, scale), P(leg.VerticalStart, scale), out arc))
                throw new InvalidOperationException("梯腿R150圆角路径无效。");
            path.Add(CurvePrimitive.CreateArc(arc));
            path.Add(CurvePrimitive.CreateLine(new DSegment3d(P(leg.VerticalStart, scale), P(leg.Bottom, scale))));
            return SolidPrimitiveFactory.Sweep(profile, path);
        }

        private static DPoint3d P(TankLadderPoint at, double scale) { return P(at.X, at.Y, at.Z, scale); }
        private static DPoint3d P(double x, double y, double z, double scale) { return new DPoint3d(x * scale, y * scale, z * scale); }
    }
}
