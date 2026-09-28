using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页"最近使用"卡片上的相对时间文案。**纯计算**：不引用 WPF / 文件系统 / 系统时钟
    /// （当前时间由调用方传入，否则不可重现、也写不了断言），可被 <c>Development/HomeCheck</c> 链接。
    /// <para>
    /// 输入是 <see cref="HomePreferenceRecord.LastUsedUtc"/> 里存的 ISO 8601（UTC）字符串，
    /// 输出形如"刚刚 / 12 分钟前 / 3 小时前 / 昨天 / 5 天前 / 2026-03-01"。
    /// </para>
    /// </summary>
    internal static class HomeRelativeTime
    {
        /// <summary>解析 ISO 8601 记录时间为 UTC；空串或非法格式返回 null。</summary>
        internal static DateTime? Parse(string lastUsedUtc)
        {
            if (string.IsNullOrEmpty(lastUsedUtc)) return null;
            DateTime value;
            if (!DateTime.TryParse(lastUsedUtc, CultureInfo.InvariantCulture,
                DateTimeStyles.RoundtripKind, out value)) return null;
            if (value.Kind == DateTimeKind.Local) return value.ToUniversalTime();
            if (value.Kind == DateTimeKind.Unspecified) return DateTime.SpecifyKind(value, DateTimeKind.Utc);
            return value;
        }

        /// <summary>相对时间文案；无法解析时返回空串（卡片不显示时间）。</summary>
        internal static string Label(string lastUsedUtc, DateTime utcNow)
        {
            DateTime? parsed = Parse(lastUsedUtc);
            if (!parsed.HasValue) return "";
            return Label(parsed.Value, utcNow);
        }

        internal static string Label(DateTime lastUsedUtc, DateTime utcNow)
        {
            TimeSpan span = utcNow - lastUsedUtc;
            if (span <= TimeSpan.Zero) return "刚刚";
            if (span.TotalMinutes < 1) return "刚刚";
            if (span.TotalMinutes < 60) return ((int)span.TotalMinutes).ToString(CultureInfo.InvariantCulture) + " 分钟前";
            if (span.TotalHours < 24) return ((int)span.TotalHours).ToString(CultureInfo.InvariantCulture) + " 小时前";
            // 超过 24 小时：改按"日历日"算，跨零点后才是"昨天"，避免 25 小时与 23 小时在不同日期却同档。
            int days = (utcNow.Date - lastUsedUtc.Date).Days;
            if (days <= 1) return "昨天";
            if (days < 7) return days.ToString(CultureInfo.InvariantCulture) + " 天前";
            return lastUsedUtc.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        }
    }
}