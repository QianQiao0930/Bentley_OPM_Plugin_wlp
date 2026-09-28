namespace SteelSectionProbe
{
    /// <summary>
    /// 首页分区定义：分区键、中文名与显示顺序的<b>唯一来源</b>。
    /// <para>
    /// <see cref="FeatureDescriptor.Category"/> 只存这里的键；首页按 <see cref="Sections"/> 的顺序
    /// 依次渲染分区，新增或调整分区只需改本文件。占位卡固定落在 <see cref="Planned"/>（"规划中"）。
    /// </para>
    /// 本类型是纯数据，可被 Development 下的纯计算检查工程链接。
    /// </summary>
    internal static class HomeCategories
    {
        internal const string Modeling = "modeling";
        internal const string Support = "support";
        internal const string Stats = "stats";
        internal const string Planned = "planned";

        /// <summary>一个分区的键与中文名。</summary>
        internal sealed class Definition
        {
            public string Key = "";
            public string DisplayName = "";
        }

        /// <summary>分区显示顺序（不含"最近使用"——那一段由首页按最近使用时间单独生成）。</summary>
        internal static Definition[] Sections()
        {
            return new Definition[]
            {
                new Definition { Key = Modeling, DisplayName = "建模类" },
                new Definition { Key = Support, DisplayName = "支撑架类" },
                new Definition { Key = Stats, DisplayName = "统计与扩展" },
                new Definition { Key = Planned, DisplayName = "规划中" },
            };
        }

        internal static bool IsKnown(string key)
        {
            if (string.IsNullOrEmpty(key)) return false;
            foreach (Definition section in Sections())
                if (section.Key == key) return true;
            return false;
        }

        /// <summary>分区键 → 中文名；未知键返回空串（首页对未知分区直接不渲染，不静默串到别的分区）。</summary>
        internal static string DisplayNameOf(string key)
        {
            foreach (Definition section in Sections())
                if (section.Key == key) return section.DisplayName;
            return "";
        }
    }
}