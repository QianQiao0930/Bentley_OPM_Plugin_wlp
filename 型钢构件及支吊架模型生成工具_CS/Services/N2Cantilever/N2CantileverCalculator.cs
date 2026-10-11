using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 计算 N2 悬臂架的尺寸、编号和辅助线局部坐标。
    /// </summary>
    internal static class N2CantileverCalculator
    {

        /// <summary>
        /// 校验输入，并根据辅助线长度（毫米）计算建模计划。
        /// </summary>
        internal static N2CantileverPlan Calculate(N2CantileverParameters p, double length)
        {
            if (p == null)
                throw new ArgumentNullException("p");
            if (p.Type != 1 && p.Type != 2)
                throw new InvalidOperationException("当前仅支持 N2 类型 1、2。");
            Positive(length, "辅助线 L");
            Positive(p.EquipmentOdMm, "设备外径 2R");
            Nonnegative(p.PreweldMm, "预焊件长度 D");
            var v = N2CantileverCatalog.Require(p.Subtype);
            if (!Finite(p.L2Mm) || p.L2Mm < v.MinimumL2Mm || p.L2Mm > 1000)
                throw new InvalidOperationException("该子项 L2 必须在 " + v.MinimumL2Mm + "～1000 mm 内。");
            double radius = p.EquipmentOdMm / 2, half = p.L2Mm / 2;
            if (half >= radius)
                throw new InvalidOperationException("L2 必须小于设备外径，才能定位两处设备生根点。");
            double root = Math.Sqrt(radius * radius - half * half) + p.PreweldMm;
            double supportOffset = 0;
            if (p.Type == 1)
            {
                Positive(p.PipeOdMm, "管道外径");
                Nonnegative(p.ShoeHeightMm, "管托高度");
                supportOffset = p.PipeOdMm / 2 + p.ShoeHeightMm;
            }
            double l1 = length - root - supportOffset;
            Positive(l1, "换算后的 L1");
            double l3 = 0, l4 = 0;
            if (p.Type == 2)
            {
                Positive(p.L3Mm, "L3");
                Nonnegative(p.L4Mm, "L4");
                l3 = p.L3Mm;
                l4 = p.L4Mm;
            }
            var a = ProfileLookup.Profile(RuntimeData.Families, v.Family, v.ProfileA);
            var b = ProfileLookup.Profile(RuntimeData.Families, v.Family, v.ProfileB);
            if (a == null || b == null)
                throw new InvalidOperationException("型钢目录缺少 N2 构件 A/B。");
            double width = a.Dimensions["B"], bw = b.Dimensions["B"];
            double height = v.Family == "equal_angle" ? width : a.Dimensions["H"];
            // L2 沿用 N4 的两根 A 截面轴线间距；B 安装在两根 A 的内侧腹板之间。
            double span = p.L2Mm - width;
            Positive(span, "构件 B 实长");
            if (p.Type == 2 && l4 > 0 && l1 - l4 - bw <= 0)
                throw new InvalidOperationException("内侧构件 B 不得越过设备生根端，请减小 L4。");
            var plate = N8Catalog.Resolve(v.PlateType, "N", 0, G2MountFace.Wall);
            if (p.L2Mm < plate.E)
                throw new InvalidOperationException("两块 N8 连接板不能重叠。");
            if (p.ShowPreweld && p.PreweldMm <= 2 * plate.T)
                throw new InvalidOperationException("预焊件占位要求 D 大于两块连接板总厚度（" + (2 * plate.T) + " mm）。");
            var result = new N2CantileverPlan
            {
                Parameters = p,
                Variant = v,
                LMm = length,
                RootMm = root,
                L1Mm = l1,
                L2Mm = p.L2Mm,
                LoadArmMm = length - radius,
                VerticalLoadKn = N2CantileverCatalog.AllowableLoad(v, length - radius),
                ACutMm = l1 + (p.Type == 2 ? l3 + bw : 0) + 50,
                BLengthMm = span,
                BCount = p.Type == 2 && l4 > 0 ? 2 : 1,
                OuterBFaceMm = root + l1 + l3,
                InnerBFaceMm = root + l1 - l4,
                AHeightMm = height,
                AWidthMm = width,
                BWidthMm = bw,
                BTopOffsetMm = 0
            };
            result.Number = "N2-" + p.Type + "-" + p.Subtype + "-" + Round(l1) + "-" + Round(p.L2Mm) +
                (p.Type == 2 ? "-" + Round(l3) + (Math.Abs(l4 - l3) < 1e-6 ? "" : "-" + Round(l4)) : "");
            result.Specification = "类型 " + p.Type + "；子项 " + p.Subtype + "；L1=" + Format(l1) + "；L2=" + Format(p.L2Mm) +
                (p.Type == 2 ? "；L3=" + Format(l3) + "；L4=" + Format(l4) : "；管道外径=" + Format(p.PipeOdMm) + "；管托高度=" + Format(p.ShoeHeightMm) + "；S=" + Format(supportOffset)) +
                "；构件 A/B " + v.SectionA + "（顶平）；A 实长=" + Format(result.ACutMm) + "；B 实长=" + Format(span) +
                "；N8-" + v.PlateType + "；L=" + Format(length) + "；设备外径=" + Format(p.EquipmentOdMm) +
                "；D=" + Format(p.PreweldMm) + "；a=" + Format(result.LoadArmMm) + "；允许垂直荷载=" + Format(result.VerticalLoadKn) + " kN" +
                (p.ShowPreweld ? "；含透明预焊件参考占位（不计清单）" : "");
            return result;
        }

        /// <summary>
        /// 根据活动模型中的毫米坐标建立水平局部坐标系，支持反转辅助线方向。
        /// </summary>
        internal static N2CantileverFrame Frame(double sx, double sy, double sz, double ex, double ey, double ez, bool reverse)
        {
            foreach (double value in new[] { sx, sy, sz, ex, ey, ez })
                if (!Finite(value))
                    throw new InvalidOperationException("辅助线坐标无效。");
            if (reverse)
            {
                double t = sx;
                sx = ex;
                ex = t;
                t = sy;
                sy = ey;
                ey = t;
                t = sz;
                sz = ez;
                ez = t;
            }
            double dx = ex - sx, dy = ey - sy, dz = ez - sz, length = Math.Sqrt(dx * dx + dy * dy);
            if (length <= 1e-6)
                throw new InvalidOperationException("辅助线水平长度为零。");
            // 设备中心至管道中心的径向辅助线必须水平，不能将斜线直接投影为水平线。
            if (Math.Abs(dz) > 1)
                throw new InvalidOperationException("请选择水平辅助线，两端标高差不能超过 1 mm。");
            return new N2CantileverFrame { X = sx, Y = sy, Z = sz, RunX = dx / length, RunY = dy / length, LengthMm = length };
        }

        private static bool Finite(double v)
        {
            return !double.IsNaN(v) && !double.IsInfinity(v);
        }

        private static void Positive(double v, string label)
        {
            if (!Finite(v) || v <= 0)
                throw new InvalidOperationException(label + "必须为有效正数。");
        }

        private static void Nonnegative(double v, string label)
        {
            if (!Finite(v) || v < 0)
                throw new InvalidOperationException(label + "必须为有效非负数。");
        }

        private static string Round(double v)
        {
            return Math.Floor(v + 0.5).ToString("0", CultureInfo.InvariantCulture);
        }

        private static string Format(double v)
        {
            return v.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
