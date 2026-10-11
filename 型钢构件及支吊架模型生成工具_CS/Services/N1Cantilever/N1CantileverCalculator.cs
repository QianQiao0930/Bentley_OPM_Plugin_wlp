using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 计算 N1 悬臂架的尺寸、编号和辅助线局部坐标。
    /// </summary>
    internal static class N1CantileverCalculator
    {

        /// <summary>
        /// 校验输入，并根据辅助线长度（毫米）计算建模计划。
        /// </summary>
        internal static N1CantileverPlan Calculate(N1CantileverParameters p, double length)
        {
            if (p == null)
                throw new ArgumentNullException("p");
            if (p.Type != 1 && p.Type != 2)
                throw new InvalidOperationException("当前资料只支持 N1 类型 1、2。");
            Positive(length, p.Type == 1 ? "悬臂辅助线 L1" : "辅助线 L");
            var v = N1CantileverCatalog.Require(p.Subtype);
            double arm = 0, root = 0, l1 = length;
            if (p.Type == 2)
            {
                Positive(p.EquipmentOdMm, "设备外径 2R");
                if (!Finite(p.PreweldMm) || p.PreweldMm < 0)
                    throw new InvalidOperationException("预焊件长度 D 不能为负。");
                arm = length - p.EquipmentOdMm / 2;
                root = p.EquipmentOdMm / 2 + p.PreweldMm;
                l1 = length - root;
                if (l1 <= 0)
                    throw new InvalidOperationException("立管中心必须位于设备及预焊件外侧。");
                if (!Finite(p.L2Mm) || p.L2Mm <= 0 || p.L2Mm > 600)
                    throw new InvalidOperationException("类型 2 的 L2 必须大于 0 且不超过 600 mm。");
                var profile = ProfileLookup.Profile(RuntimeData.Families, v.Family, v.ProfileA);
                if (profile == null)
                    throw new InvalidOperationException("型钢目录缺少构件 A。");
                if (p.L2Mm < profile.Dimensions["B"])
                    throw new InvalidOperationException("L2 不能小于构件 A 的宽度。");
            }
            if (p.ShowPreweld)
            {
                // 参考 N4，预焊件占位包含两块相邻连接板和一段仅供显示的管体。
                double plate = N8Catalog.Resolve(v.PlateType, "N", 0, G2MountFace.Wall).T;
                if (!Finite(p.PreweldMm) || p.PreweldMm <= 2 * plate)
                    throw new InvalidOperationException("生成预焊件占位时，D 必须大于两块连接板的总厚度（" + (2 * plate) + " mm）。");
            }
            // 角钢按 B-B 保留 10 mm 缩进；槽钢 A 的末端贴合 B 的腹板内侧面。
            double cut = p.Type == 1 ? l1 : l1 - N1CantileverCatalog.AEndSetback(v);
            Positive(cut, "构件 A 长度");
            var result = new N1CantileverPlan
            {
                Parameters = p,
                Variant = v,
                LMm = length,
                LoadArmMm = arm,
                RootMm = root,
                L1Mm = l1,
                L2Mm = p.Type == 2 ? p.L2Mm : 0,
                ACutMm = cut,
                BTopOffsetMm = p.Type == 2 ? N1CantileverCatalog.BTopOffset(v) : 0,
                HasLoad = p.Type == 2,
                VerticalLoadKn = p.Type == 2 ? N1CantileverCatalog.AllowableLoad(v, arm) : 0
            };
            result.Number = "N1-" + p.Type + "-" + p.Subtype + "-" + Round(l1) + (p.Type == 2 ? "-" + Round(p.L2Mm) : "");
            result.Specification = "类型 " + p.Type + "；子项 " + p.Subtype + "；L1=" + Format(l1) +
                (p.Type == 2 ? "；L2=" + Format(p.L2Mm) : "") +
                "；构件 A " + v.SectionA + (p.Type == 2 ? "；构件 B " + v.SectionB : "") +
                "；N8-" + v.PlateType +
                (p.Type == 2 ? "；L=" + Format(length) + "；设备外径=" + Format(p.EquipmentOdMm) +
                    "；预焊件 D=" + Format(p.PreweldMm) + "；a=" + Format(arm) +
                    "；允许垂直荷载=" + Format(result.VerticalLoadKn) + " kN" :
                    "；按悬臂辅助线直接取 L1；未提供载荷位置，不计算允许荷载") +
                (p.ShowPreweld ? "；透明预焊件占位 D=" + Format(p.PreweldMm) : "");
            return result;
        }

        /// <summary>
        /// 根据活动模型中的毫米坐标建立水平局部坐标系，支持反转辅助线方向。
        /// </summary>
        internal static N1CantileverFrame Frame(double sx, double sy, double sz, double ex, double ey, double ez, bool reverse)
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
            return new N1CantileverFrame { X = sx, Y = sy, Z = sz, RunX = dx / length, RunY = dy / length, LengthMm = length };
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static void Positive(double value, string label)
        {
            if (!Finite(value) || value <= 0)
                throw new InvalidOperationException(label + "必须为有效正数。");
        }

        private static string Round(double value)
        {
            return Math.Floor(value + 0.5).ToString("0", CultureInfo.InvariantCulture);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
