using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>排序结果：一个功能入口 + 它的排序输入（星标、衰减频率、是否置顶）。</summary>
    internal sealed class HomeEntry
    {
        public FeatureDescriptor Feature;
        public int Stars;

        /// <summary>衰减后的使用频率得分；占位卡固定为 -1，保证排在所有可用功能之后。</summary>
        public double FrequencyScore;

        /// <summary>达到 <see cref="HomeFeatureRanker.PinThreshold"/> 星才为 true（进置顶区）。</summary>
        public bool IsPinned;
    }

    /// <summary>
    /// 首页排序器：<b>纯计算</b>，不引用 WPF、文件系统与系统时钟
    /// （当前时间必须由调用方传入，否则不可重现、也写不了断言）。
    /// <para>唯一比较器的关键字，从高到低：</para>
    /// <list type="number">
    /// <item><description>置顶区（星级 ≥ <see cref="PinThreshold"/>）整体在前；</description></item>
    /// <item><description>星级降序 —— 自动区里 1～2 星同样压过未评分；</description></item>
    /// <item><description>使用频率降序（衰减计数）；</description></item>
    /// <item><description>出厂顺序升序 —— 冷启动/从未使用时的兜底，等于改造前的首页顺序；</description></item>
    /// <item><description>PageId 字典序 —— 全序兜底。List.Sort 是<b>不稳定</b>排序，缺这一级会让同键卡片每次渲染顺序漂移。</description></item>
    /// </list>
    /// </summary>
    internal static class HomeFeatureRanker
    {
        /// <summary>达到这个星级才进置顶区（1～2 星只在自动区内享受星级优先）。</summary>
        internal const int PinThreshold = 3;

        /// <summary>使用频率的半衰期（月）：每过一个月，该月权重减半。</summary>
        internal const int DecayHalfLifeMonths = 1;

        /// <summary>超过这个月数的桶不再计入频率，同时在写盘时被裁剪。</summary>
        internal const int MaxRetainedMonths = 12;

        /// <summary>月份的桶键，形如 <c>2026-09</c>（UTC，与界面语言无关）。</summary>
        internal static string MonthKey(DateTime utc)
        {
            return utc.ToString("yyyy-MM", CultureInfo.InvariantCulture);
        }

        private static int MonthNumber(DateTime utc)
        {
            return utc.Year * 12 + (utc.Month - 1);
        }

        /// <summary>把桶键解析成月份序号；格式非法返回 -1。</summary>
        private static int MonthNumberOfKey(string key)
        {
            if (key == null || key.Length != 7 || key[4] != '-') return -1;
            int year, month;
            if (!int.TryParse(key.Substring(0, 4), NumberStyles.None, CultureInfo.InvariantCulture, out year)) return -1;
            if (!int.TryParse(key.Substring(5, 2), NumberStyles.None, CultureInfo.InvariantCulture, out month)) return -1;
            if (month < 1 || month > 12) return -1;
            return year * 12 + (month - 1);
        }

        /// <summary>桶是否可用于统计：格式合法、不是未来月份、且未超过保留期。</summary>
        internal static bool TryMonthsAgo(string key, DateTime utcNow, out int monthsAgo)
        {
            monthsAgo = 0;
            int number = MonthNumberOfKey(key);
            if (number < 0) return false;
            int diff = MonthNumber(utcNow) - number;
            if (diff < 0 || diff > MaxRetainedMonths) return false;
            monthsAgo = diff;
            return true;
        }

        /// <summary>
        /// 衰减计数：<c>Σ 该月次数 × 0.5^(距今天数月)</c>。
        /// 用衰减而不是累计总数，是为了让"半年前的高频功能"自然沉下去 ——
        /// 累计次数会让它永久霸榜。
        /// </summary>
        internal static double FrequencyScore(HomePreferenceRecord record, DateTime utcNow)
        {
            if (record == null || record.MonthlyUse == null) return 0.0;
            double score = 0.0;
            foreach (KeyValuePair<string, int> bucket in record.MonthlyUse)
            {
                int monthsAgo;
                if (!TryMonthsAgo(bucket.Key, utcNow, out monthsAgo)) continue;
                if (bucket.Value <= 0) continue;
                score += bucket.Value * Math.Pow(0.5, (double)monthsAgo / DecayHalfLifeMonths);
            }
            return score;
        }

        /// <summary>卡片上的一行使用情况说明（纯字符串计算，便于断言）。</summary>
        internal static string UsageLabel(HomePreferenceRecord record, DateTime utcNow)
        {
            if (record == null || record.TotalUseCount <= 0) return "尚未使用";
            int current;
            record.MonthlyUse.TryGetValue(MonthKey(utcNow), out current);
            if (current > 0) return "累计 " + record.TotalUseCount.ToString(CultureInfo.InvariantCulture)
                + " 次 · 本月 " + current.ToString(CultureInfo.InvariantCulture) + " 次";
            return "累计 " + record.TotalUseCount.ToString(CultureInfo.InvariantCulture) + " 次 · 本月未用";
        }

        internal static List<HomeEntry> Rank(IEnumerable<FeatureDescriptor> features,
            IDictionary<string, HomePreferenceRecord> records, DateTime utcNow)
        {
            var entries = new List<HomeEntry>();
            if (features == null) return entries;

            foreach (FeatureDescriptor feature in features)
            {
                if (feature == null) continue;
                HomePreferenceRecord record = null;
                if (records != null && !string.IsNullOrEmpty(feature.PageId))
                    records.TryGetValue(feature.PageId, out record);

                var entry = new HomeEntry();
                entry.Feature = feature;
                // 占位卡不参与星标与统计：恒 0 星、频率 -1，永远排在可用功能之后。
                entry.Stars = feature.IsReady ? Clamp(record == null ? 0 : record.Stars, 0, 5) : 0;
                entry.FrequencyScore = feature.IsReady ? FrequencyScore(record, utcNow) : -1.0;
                entry.IsPinned = entry.Stars >= PinThreshold;
                entries.Add(entry);
            }

            entries.Sort(Compare);
            return entries;
        }

        private static int Clamp(int value, int min, int max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }

        /// <summary>
        /// 星级优先级：置顶区（≥ <see cref="PinThreshold"/> 星）整体在前，再按星级降序。
        /// 返回 0 = 两者同档，调用方再按自己的口径（最近时间 / 使用频率）继续比。
        /// <para>
        /// ⚠️ 首页的显式排序（「最近使用」「常用优先」）**必须先过这一级**：
        /// 否则 5 星但用得少的功能会被"常用优先"挤到列表后面 —— 用户标星的意图被排序模式覆盖。
        /// 放在这里（而不是页面里）是为了能被 <c>Development/HomeCheck</c> 断言。
        /// </para>
        /// </summary>
        internal static int CompareStarTier(HomeEntry a, HomeEntry b)
        {
            if (a == null || b == null) return 0;
            if (a.IsPinned != b.IsPinned) return a.IsPinned ? -1 : 1;
            return b.Stars.CompareTo(a.Stars);
        }

        /// <summary>全序比较器，见类型注释里的关键字表。</summary>
        internal static int Compare(HomeEntry x, HomeEntry y)
        {
            if (x.IsPinned != y.IsPinned) return x.IsPinned ? -1 : 1;
            if (x.Stars != y.Stars) return y.Stars.CompareTo(x.Stars);
            if (x.FrequencyScore != y.FrequencyScore)
                return y.FrequencyScore.CompareTo(x.FrequencyScore);
            int order = x.Feature.DefaultOrder.CompareTo(y.Feature.DefaultOrder);
            if (order != 0) return order;
            return string.CompareOrdinal(x.Feature.PageId ?? "", y.Feature.PageId ?? "");
        }
    }
}
