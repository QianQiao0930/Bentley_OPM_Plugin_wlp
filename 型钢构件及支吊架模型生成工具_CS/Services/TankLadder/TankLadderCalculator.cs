using System;

namespace SteelSectionProbe
{
    internal static class TankLadderCalculator
    {
        internal static TankLadderPlan Calculate(TankLadderParameters input)
        {
            if (input == null) throw new ArgumentNullException("input");
            if (!Finite(input.TankHeightMm) || input.TankHeightMm <= 0 || input.TankHeightMm > 50000)
                throw new InvalidOperationException("水箱高度须大于0且不超过50000 mm（建模上限）。");
            if (!Finite(input.WidthMm) || input.WidthMm <= 2 * TankLadderCatalog.LegThicknessMm || input.WidthMm > 5000)
                throw new InvalidOperationException("顶部两角钢净距须大于20且不超过5000 mm。");
            if (!Finite(input.ReinforcementSpacingMm) || input.ReinforcementSpacingMm <= 0)
                throw new InvalidOperationException("加强撑间距必须是有限正数。");
            if (!Finite(input.HeadingDegrees)) throw new InvalidOperationException("朝向角必须是有限数值。");
            double supports = Math.Max(0, Math.Floor((input.TankHeightMm - TankLadderCatalog.ReinforcementBottomMm) /
                input.ReinforcementSpacingMm) + 1);
            double rungs = Math.Floor(input.TankHeightMm / TankLadderCatalog.RungSpacingMm);
            if (!Finite(supports) || supports * 2 + rungs + 5 > TankLadderCatalog.MaxComponents)
                throw new InvalidOperationException("构件数量超过500，请增大加强撑间距或减小水箱高度。");
            var p = new TankLadderParameters { TankHeightMm = input.TankHeightMm, WidthMm = input.WidthMm,
                ReinforcementSpacingMm = input.ReinforcementSpacingMm,
                HeadingDegrees = (input.HeadingDegrees % 360 + 360) % 360, MergeComponents = input.MergeComponents };
            double legX = p.WidthMm / 2 - TankLadderCatalog.LegThicknessMm / 2;
            double legY = -TankLadderCatalog.FrameWidthMm / 2;
            double legZ = TankLadderCatalog.FrameHeightMm - TankLadderCatalog.LegWidthMm / 2 - TankLadderCatalog.LegDropMm;
            double centerline = TankLadderCatalog.TopLengthMm - TankLadderCatalog.LegWidthMm / 2;
            double verticalHeight = p.TankHeightMm + TankLadderCatalog.LegExtraHeightMm;
            var plan = new TankLadderPlan { Parameters = p, LegVerticalHeightMm = verticalHeight,
                BottomAngleLengthMm = p.WidthMm + 2 * TankLadderCatalog.FrameWidthMm,
                BottomAngleOrigin = new TankLadderPoint(-(p.WidthMm + 2 * TankLadderCatalog.FrameWidthMm) / 2, 0, 0),
                PostOrigins = new[] { new TankLadderPoint(-p.WidthMm / 2, 0, 0), new TankLadderPoint(p.WidthMm / 2, 0, 0) },
                Legs = new[] { Leg(-legX, legY, legZ, centerline, verticalHeight), Leg(legX, legY, legZ, centerline, verticalHeight) },
                ReinforcementOrigins = new TankLadderPoint[(int)supports * 2], RungCenters = new TankLadderPoint[(int)rungs],
                RungLengthMm = p.WidthMm + 10, LegClearWidthMm = p.WidthMm - 2 * TankLadderCatalog.LegThicknessMm,
                ComponentCount = 5 + (int)supports * 2 + (int)rungs };
            for (int i = 0; i < supports; i++)
            {
                double z = -p.TankHeightMm + TankLadderCatalog.ReinforcementBottomMm + i * p.ReinforcementSpacingMm;
                double x = legX + TankLadderCatalog.ReinforcementOffsetMm;
                plan.ReinforcementOrigins[2 * i] = new TankLadderPoint(-x, legY - centerline, z);
                plan.ReinforcementOrigins[2 * i + 1] = new TankLadderPoint(x, legY - centerline, z);
            }
            for (int i = 0; i < rungs; i++)
                plan.RungCenters[i] = new TankLadderPoint(0, legY - centerline,
                    -p.TankHeightMm + TankLadderCatalog.RungBottomMm + i * TankLadderCatalog.RungSpacingMm);
            return plan;
        }

        private static TankLadderLeg Leg(double x, double y, double z, double length, double height)
        {
            double radius = TankLadderCatalog.BendRadiusMm, q = Math.Sqrt(0.5);
            return new TankLadderLeg { Start = new TankLadderPoint(x, y, z),
                ShortEnd = new TankLadderPoint(x, y - length + radius, z),
                ArcMiddle = new TankLadderPoint(x, y - length + radius - radius * q, z - radius + radius * q),
                VerticalStart = new TankLadderPoint(x, y - length, z - radius),
                Bottom = new TankLadderPoint(x, y - length, z - height) };
        }

        private static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
    }
}
