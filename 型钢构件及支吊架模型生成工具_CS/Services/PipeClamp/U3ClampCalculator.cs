using System;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class U3ClampCalculator
    {
        internal static U3ClampPlan Calculate(int fallbackDn, bool isPipe, double? nominal,
            double? outside, double? insulation, string item, string material, double steel,
            double top, double rubber, double wall, double angle, string pipe)
        {
            int dn = fallbackDn;
            if (isPipe && nominal.HasValue && nominal.Value > 0)
            {
                var matched = U3ClampCatalog.Rows.FirstOrDefault(x => Math.Abs(x.Dn - nominal.Value) < .5);
                if (matched == null) throw new InvalidOperationException("U3 管径须为 DN15～150（1/2\"～6\"）。");
                dn = matched.Dn;
            }
            if (!U3ClampCatalog.Rows.Any(x => x.Dn == dn)) throw new InvalidOperationException("U3 管径须为 DN15～150。");
            if (item != "A" && item != "G") throw new InvalidOperationException("U3 子项须为 A 或 G。");
            if (material != "C1" && material != "S" && material != "S1") throw new InvalidOperationException("U3 材料代码须为 C1、S 或 S1。");
            Positive(steel, "已有钢构厚度", 100);
            Positive(top, "管卡中心到钢构顶面的高度", 500);
            Positive(wall, "管壁厚度", 100);
            if (material == "S1") Positive(rubber, "EPDM 厚度", 10);
            else rubber = 0;
            if (insulation.HasValue && (!Finite(insulation.Value) || insulation.Value != 0))
                throw new InvalidOperationException("U3 请选择不保温立管。");
            var clamp = A1ClampCalculator.Calculate(dn, false, null, angle, pipe);
            double radius = clamp.Row.OutsideMm / 2;
            if (outside.HasValue && (!Finite(outside.Value) || Math.Abs(outside.Value - 2 * radius) > 2))
                throw new InvalidOperationException("管道外径与 A1 管卡规格不匹配。");
            if (wall >= radius) throw new InvalidOperationException("管壁厚度须小于管道半径。");
            if (top <= clamp.Row.Bolt / 2 + (rubber > 0 ? Math.Max(2, rubber) : 0)) throw new InvalidOperationException("钢构顶面应高于管卡及衬垫，避免与承重块重叠。");
            double gap = item == "G" ? 3 : 0;
            clamp.LegSpacingMm = 2 * (radius + rubber + gap) + clamp.Row.Bolt;
            double near = radius + rubber, far = near + steel, nut = clamp.NutHeightMm;
            clamp.NutLow1Mm = item == "G" ? near - nut : far;
            clamp.NutCenterMm = clamp.NutLow1Mm + nut;
            clamp.NutLow2Mm = item == "G" ? far : far + nut;
            clamp.StraightLegMm = Math.Max(clamp.Row.D, clamp.NutLow2Mm + nut + clamp.Row.Bolt);
            double height = dn <= 65 ? 50 : 100, projection = dn <= 65 ? 30 : 50;
            if (rubber + steel >= Math.Sqrt(radius*radius - 25) + projection - radius) throw new InvalidOperationException("钢构厚度及衬垫超过承重块有效伸出长度。");
            string boltMaterial = material == "S" ? "06Cr19Ni10" : "Q235B或20";
            string blockMaterial = material == "C1" ? "Q235B" : "06Cr19Ni10";
            clamp.BoltLengthMm = 2 * clamp.StraightLegMm.Value + Math.PI * clamp.LegSpacingMm.Value / 2;
            clamp.BoltSpecification = "A1 M" + clamp.Row.Bolt + " / " + boltMaterial + " / C=" + F(clamp.LegSpacingMm.Value) + " / D=" + F(clamp.StraightLegMm.Value);
            clamp.NutSpecification += " / " + boltMaterial;
            string number = "U3-" + item + "-DN" + dn + "-" + material;
            return new U3ClampPlan {
                Clamp = clamp, Subitem = item, MaterialCode = material, BoltMaterial = boltMaterial, BlockMaterial = blockMaterial,
                Number = number, BlockHeightMm = height, BlockProjectionMm = projection, BlockThicknessMm = 10,
                SteelThicknessMm = steel, SupportTopMm = top, RubberMm = rubber, GuideGapMm = gap, WeldMm = Math.Min(6, wall),
                Specification = number + " / " + (item == "A" ? "承重/固定，两螺母在同一外侧" : "承重/导向，两螺母一边一个，净间隙3 mm") +
                    " / 承重块 " + height + "×" + projection + "×10 / " + blockMaterial + " / 长边沿立管焊接，焊高 " + F(Math.Min(6, wall)) + " mm" +
                    (material == "S1" ? " / EPDM " + F(rubber) + " mm，管温≤120°C" : material == "S" ? " / 钢构接触处另配不锈钢垫板或护板 Y1/Y2" : "")
            };
        }
        internal static void ValidateAxis(double x, double y, double z)
        {
            double length = Math.Sqrt(x*x + y*y + z*z);
            if (!Finite(length) || length < 1e-9 || Math.Sqrt(x*x + y*y) / length > .001)
                throw new InvalidOperationException("U3 承重块管卡须点取立管或竖直辅助线。");
        }
        private static void Positive(double value, string label, double max)
        { if (!Finite(value) || value <= 0 || value > max) throw new InvalidOperationException(label + "须大于0且不超过" + max + " mm。"); }
        private static bool Finite(double x) { return !double.IsNaN(x) && !double.IsInfinity(x); }
        private static string F(double x) { return x.ToString("0.###", CultureInfo.InvariantCulture); }
    }
}
