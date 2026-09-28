using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>
    /// 单个首页功能入口的跨会话偏好：用户星标与使用次数。
    /// <para>
    /// 使用次数按<b>月分桶</b>（键 = <c>yyyy-MM</c>，UTC），不是只记一个总数：
    /// 排序用的是"衰减计数"（见 <see cref="HomeFeatureRanker.FrequencyScore"/>），
    /// 只有分桶才能让久不使用的功能自然下沉。
    /// </para>
    /// 本类型是纯数据，可被 Development 下的纯计算检查工程链接。
    /// </summary>
    internal sealed class HomePreferenceRecord
    {
        /// <summary>0 = 未评分；1～5 = 用户星标。</summary>
        public int Stars;

        /// <summary>累计进入次数，仅用于界面展示与排查（排序不用它）。</summary>
        public int TotalUseCount;

        /// <summary>最近一次进入的时间，ISO 8601（UTC）。空串 = 从未记录。</summary>
        public string LastUsedUtc = "";

        public Dictionary<string, int> MonthlyUse = new Dictionary<string, int>(StringComparer.Ordinal);
    }
}
