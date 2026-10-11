using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>计算悬臂实长、可选端板及按 B 分档的允许荷载。</summary>
    internal static class D2CantileverCalculator
    {
        internal static D2CantileverPlan Calculate(D2CantileverParameters p, double lengthMm,
            double headingDegrees)
        {
            if (p == null) throw new ArgumentNullException("p");
            if (p.Kind == "G11")
            {
                return G11CantileverCalculator.Calculate(p, lengthMm, headingDegrees);
            }

            D2CantileverCatalog.KeysFor(p.Kind);
            if (p.Type != 1 && (p.Kind != "D3" || p.Type != 2))
                throw new InvalidOperationException("D2 只支持端焊；D3 只支持类型 1、2。");
            if (p.Kind == "D3" && p.AddPlate)
                throw new InvalidOperationException("D3 为侧焊连接，不附加起点端板。");
            bool doubleArm = p.Kind == "D3" && p.Type == 2;
            double available = doubleArm ? lengthMm / 2 : lengthMm;
            if (!Finite(lengthMm) || lengthMm <= 150)
                throw new InvalidOperationException("辅助线长度 L 必须大于 150 mm。");
            if (!Finite(p.LoadDistanceMm) || p.LoadDistanceMm <= 0 || p.LoadDistanceMm > 1000)
                throw new InvalidOperationException("荷载距离 B 必须大于 0 且不超过 1000 mm。");
            if (available - p.LoadDistanceMm < 150)
                throw new InvalidOperationException(doubleArm ? "两侧末端余量 L/2−B 不得小于 150 mm。" : "末端余量 L−B 不得小于 150 mm。");
            if (!Finite(headingDegrees)) throw new InvalidOperationException("辅助线方向无效。");
            var variant = D2CantileverCatalog.Require(p.Kind, p.Subtype);
            var profile = D2CantileverCatalog.Profile(variant);
            double width = profile.Dimensions["B"];
            double height = variant.Family == "equal_angle" ? width : profile.Dimensions["H"];
            G2AnchorPlan plate = null;
            double start = 0;
            if (p.AddPlate)
            {
                if (!Finite(p.PlateOffsetMm) || p.PlateOffsetMm < 0)
                    throw new InvalidOperationException("端板外移量必须不小于零。");
                var item = G2AnchorCatalog.Require(p.PlateSubtype);
                double spacing = Math.Max(item.MinSpacingMm,
                    (Math.Floor(Math.Max(height, width) / 25) + 1) * 25);
                plate = G2AnchorCalculator.Calculate(new G2AnchorParameters {
                    SubtypeKey = p.PlateSubtype, SpacingMm = spacing,
                    HeadingDegrees = headingDegrees, MountFace = G2MountFace.Wall });
                start = p.PlateOffsetMm + plate.PlateThicknessMm;
                if (start >= p.LoadDistanceMm)
                    throw new InvalidOperationException("连接板外移和板厚不能占用荷载点位置。");
            }
            double? vertical = null;
            for (int i = 0; i < D2CantileverCatalog.LoadColumns.Length; i++)
            {
                if (p.LoadDistanceMm <= D2CantileverCatalog.LoadColumns[i])
                {
                    vertical = variant.Loads[i];
                    break;
                }
            }
            string name = string.IsNullOrWhiteSpace(p.Name) ? p.Kind : p.Name.Trim();
            return new D2CantileverPlan {
                Parameters = p, Variant = variant, Plate = plate,
                Number = name + (p.Kind == "D3" ? "-" + p.Type : "") + "-" + p.Subtype + "-" + Math.Floor(lengthMm + 0.5).ToString("0", CultureInfo.InvariantCulture),
                Specification = variant.Section + "；L=" + lengthMm.ToString("0.###", CultureInfo.InvariantCulture) +
                    " mm；B=" + p.LoadDistanceMm.ToString("0.###", CultureInfo.InvariantCulture) +
                    " mm" + (plate == null ? "" : " + G2 端板及锚栓"),
                LengthMm = lengthMm, BeamStartMm = start, BeamLengthMm = lengthMm - start,
                SectionHeightMm = height, SectionWidthMm = width,
                // D3 直接定位于外角点；下角轮廓沿 -Z 放置即得到上翼缘角点。
                SectionAnchorYmm = p.Kind == "D3" || variant.Family == "hot_rolled_h" ? 0 : -width / 2,
                SectionAnchorZmm = variant.Family == "hot_rolled_h" ? -height / 2 : 0,
                RootStationMm = doubleArm ? lengthMm / 2 : 0,
                VerticalLoadKn = vertical, HorizontalLoadKn = vertical.HasValue ? vertical.Value * 0.3 : (double?)null
            };
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }
    }
}
