using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页排序的纯计算检查。断言对象是 <see cref="HomeFeatureRanker"/> 的五级关键字、
    /// 衰减计数与 <see cref="HomeFeatureCatalog"/> 的清单一致性。
    /// <para>
    /// 运行：<c>dotnet run --project Development/HomeCheck/HomeCheck.csproj -c Release</c>。
    /// 本工程只链接纯计算文件，不引用 WPF / Bentley / System.Web。
    /// </para>
    /// </summary>
    internal static class Program
    {
        private static readonly DateTime Now = new DateTime(2026, 9, 27, 12, 0, 0, DateTimeKind.Utc);

        private static void Equal(int a, int b, string label)
        { if (a != b) throw new Exception(label + "：" + a + " != " + b); }

        private static void Equal(string a, string b, string label)
        { if (a != b) throw new Exception(label + "：\"" + a + "\" != \"" + b + "\""); }

        private static void Close(double a, double b, string label)
        { if (Math.Abs(a - b) > 0.000001) throw new Exception(label + "：" + a + " != " + b); }

        private static void True(bool value, string label)
        { if (!value) throw new Exception(label); }

        private static FeatureDescriptor Feature(string id, int order)
        { return new FeatureDescriptor(id, id, "", order); }

        private static HomePreferenceRecord Stars(int stars)
        { return new HomePreferenceRecord { Stars = stars }; }

        private static HomePreferenceRecord Usage(params object[] monthCountPairs)
        {
            var record = new HomePreferenceRecord();
            for (int i = 0; i + 1 < monthCountPairs.Length; i += 2)
            {
                string key = (string)monthCountPairs[i];
                int count = (int)monthCountPairs[i + 1];
                record.MonthlyUse[key] = count;
                record.TotalUseCount += count;
            }
            return record;
        }

        private static string Order(List<HomeEntry> entries)
        {
            var ids = new List<string>();
            foreach (HomeEntry entry in entries) ids.Add(entry.Feature.PageId);
            return string.Join(",", ids.ToArray());
        }

        private static string PinnedOrder(List<HomeEntry> entries)
        {
            var ids = new List<string>();
            foreach (HomeEntry entry in entries) if (entry.IsPinned) ids.Add(entry.Feature.PageId);
            return string.Join(",", ids.ToArray());
        }

        private static void Main()
        {
            CheckCatalog();
            CheckCategories();
            CheckColdStart();
            CheckPinThreshold();
            CheckStarOrder();
            CheckFrequencyOrder();
            CheckDecay();
            CheckTieBreak();
            CheckPlaceholders();
            CheckRobustness();
            CheckUsageLabel();
            CheckRelativeTime();
            Console.WriteLine("首页排序：清单一致性、分区归类、五级关键字、≥3 星置顶、衰减频率、相对时间与容错全部通过。");
        }

        /// <summary>清单本身的自检：PageId 唯一且非空、出厂顺序唯一、占位卡无 PageId。</summary>
        private static void CheckCatalog()
        {
            FeatureDescriptor[] all = HomeFeatureCatalog.All();
            var ready = new List<FeatureDescriptor>();
            var seenIds = new HashSet<string>(StringComparer.Ordinal);
            var seenOrders = new HashSet<int>();
            int placeholders = 0;

            foreach (FeatureDescriptor feature in all)
            {
                if (feature == null) throw new Exception("清单包含空项。");
                if (feature.Title.Length == 0) throw new Exception("清单项缺标题：" + feature.PageId);
                if (feature.Description.Length == 0) throw new Exception("清单项缺说明：" + feature.Title);
                if (!feature.IsReady) { placeholders++; Equal(feature.PageId, "", feature.Title + " 占位卡不应有 PageId"); continue; }
                if (feature.PageId.Length == 0) throw new Exception(feature.Title + " 缺 PageId。");
                if (feature.PageId != feature.PageId.Trim()) throw new Exception(feature.Title + " 的 PageId 含空白：" + feature.PageId);
                if (!seenIds.Add(feature.PageId)) throw new Exception("PageId 重复：" + feature.PageId);
                if (!seenOrders.Add(feature.DefaultOrder)) throw new Exception("出厂顺序重复：" + feature.DefaultOrder);
                ready.Add(feature);
            }

            Equal(ready.Count, 12, "可用功能数");
            Equal(placeholders, 2, "规划中占位卡数");
            Equal(Order(HomeFeatureRanker.Rank(all, new Dictionary<string, HomePreferenceRecord>(), Now)),
                "steel-sections,component-properties,elbow-trunnion,support-statistics,tank-manhole,solid-nozzle," +
                "pipe-clamp,vertical-pipe-support,g2-anchor-plate,n3-single-bracket,n4-double-bracket,n8-connection-plate,,",
                "清单出厂顺序");
        }

        /// <summary>分区归类：每个功能都有已知分区与非空图标；可用功能不得落在"规划中"，占位卡必须落"规划中"。</summary>
        private static void CheckCategories()
        {
            var counts = new Dictionary<string, int>(StringComparer.Ordinal);
            foreach (HomeCategories.Definition section in HomeCategories.Sections())
            {
                True(section.Key.Length > 0, "分区键不能为空");
                True(section.DisplayName.Length > 0, section.Key + " 缺中文名");
                counts[section.Key] = 0;
            }

            foreach (FeatureDescriptor feature in HomeFeatureCatalog.All())
            {
                True(HomeCategories.IsKnown(feature.Category),
                    feature.Title + " 的分区未知：" + feature.Category);
                True(feature.Icon.Length > 0, feature.Title + " 缺图标键");
                counts[feature.Category] = counts[feature.Category] + 1;

                if (feature.IsReady)
                    True(feature.Category != HomeCategories.Planned,
                        "可用功能不应落在规划中：" + feature.Title);
                else
                    Equal(feature.Category, HomeCategories.Planned, feature.Title + " 占位卡分区");
            }

            foreach (KeyValuePair<string, int> item in counts)
                True(item.Value > 0, "分区无任何卡片：" + item.Key);

            // 关键功能的归类（防止日后误改分区）：
            var byId = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (FeatureDescriptor feature in HomeFeatureCatalog.All())
                if (feature.IsReady) byId[feature.PageId] = feature.Category;
            Equal(byId["steel-sections"], HomeCategories.Modeling, "型钢生成分区");
            Equal(byId["elbow-trunnion"], HomeCategories.Modeling, "弯头耳轴分区");
            Equal(byId["n8-connection-plate"], HomeCategories.Support, "N8 分区");
            Equal(byId["support-statistics"], HomeCategories.Stats, "支吊架统计分区");
            Equal(byId["component-properties"], HomeCategories.Stats, "构件特性查询分区");

            Equal(HomeCategories.DisplayNameOf(HomeCategories.Modeling), "建模类", "建模类中文名");
            Equal(HomeCategories.DisplayNameOf("nope"), "", "未知分区应无中文名");
            True(!HomeCategories.IsKnown(""), "空分区键不属于已知分区");
        }

        /// <summary>相对时间文案：刚刚 / 分钟 / 小时 / 昨天 / 天 / 日期，以及非法输入容错。</summary>
        private static void CheckRelativeTime()
        {
            Equal(HomeRelativeTime.Label("", Now), "", "空串无文案");
            Equal(HomeRelativeTime.Label("not-a-date", Now), "", "非法时间无文案");
            Equal(HomeRelativeTime.Label(Now.AddSeconds(-30), Now), "刚刚", "半分钟内");
            Equal(HomeRelativeTime.Label(Now.AddMinutes(-5), Now), "5 分钟前", "分钟档");
            Equal(HomeRelativeTime.Label(Now.AddHours(-3), Now), "3 小时前", "小时档");
            Equal(HomeRelativeTime.Label(Now.AddHours(-25), Now), "昨天", "跨日一天");
            Equal(HomeRelativeTime.Label(Now.AddDays(-3), Now), "3 天前", "天档");
            Equal(HomeRelativeTime.Label(Now.AddDays(-10), Now), "2026-09-17", "超过一周给日期");
            Equal(HomeRelativeTime.Label(Now.AddHours(1), Now), "刚刚", "未来时间视为刚刚");

            // 存盘格式是 ISO 8601（UTC），字符串入口必须能解析回来。
            string iso = Now.AddMinutes(-5).ToString("o", CultureInfo.InvariantCulture);
            Equal(HomeRelativeTime.Label(iso, Now), "5 分钟前", "ISO 记录时间");
            True(HomeRelativeTime.Parse("") == null, "空串不解析");
            True(!HomeRelativeTime.Parse("nonsense").HasValue, "非法串不解析");
        }

        /// <summary>冷启动：没有任何偏好数据时，顺序必须等于出厂顺序（与改造前的首页完全一致）。</summary>
        private static void CheckColdStart()
        {
            List<HomeEntry> entries = HomeFeatureRanker.Rank(HomeFeatureCatalog.All(),
                new Dictionary<string, HomePreferenceRecord>(), Now);
            Equal(entries.Count, 14, "冷启动条目数");
            Equal(PinnedOrder(entries), "", "冷启动不应有置顶项");
            for (int i = 1; i < entries.Count; i++)
            {
                if (entries[i - 1].Feature.DefaultOrder > entries[i].Feature.DefaultOrder)
                    throw new Exception("冷启动未按出厂顺序：" + Order(entries));
            }
        }

        /// <summary>置顶阈值：≥3 星才置顶（这是用户确认的口径）。</summary>
        private static void CheckPinThreshold()
        {
            var features = new FeatureDescriptor[]
            { Feature("zero", 10), Feature("two", 20), Feature("three", 30), Feature("five", 40) };
            var records = new Dictionary<string, HomePreferenceRecord>
            {
                { "two", Stars(2) }, { "three", Stars(3) }, { "five", Stars(5) },
            };
            List<HomeEntry> entries = HomeFeatureRanker.Rank(features, records, Now);

            Equal(PinnedOrder(entries), "five,three", "置顶区应为 5 星与 3 星");
            // 2 星不置顶，但在自动区里仍按星级压过未评分。
            Equal(Order(entries), "five,three,two,zero", "2 星应留在自动区且排在未评分之前");

            Equal(HomeFeatureRanker.PinThreshold, 3, "置顶阈值");
        }

        /// <summary>星级降序：同为置顶项时 5 星在 4 星之前；剔除评分后立即退出置顶区。</summary>
        private static void CheckStarOrder()
        {
            var features = new FeatureDescriptor[]
            { Feature("a", 10), Feature("b", 20), Feature("c", 30) };
            var records = new Dictionary<string, HomePreferenceRecord>
            {
                { "a", Stars(4) }, { "b", Stars(5) }, { "c", Stars(3) },
            };
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "b,a,c", "置顶区按星级降序");

            records["b"].Stars = 2;   // 4 星 → 2 星：掉出置顶区，但星级仍高于 a 以下的 0 星
            Equal(PinnedOrder(HomeFeatureRanker.Rank(features, records, Now)), "a,c", "掉出置顶区");
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "a,c,b", "2 星应排到置顶区之后");
        }

        /// <summary>同星级时按使用频率降序。</summary>
        private static void CheckFrequencyOrder()
        {
            var features = new FeatureDescriptor[]
            { Feature("a", 10), Feature("b", 20), Feature("c", 30) };
            var records = new Dictionary<string, HomePreferenceRecord>
            {
                { "a", Usage("2026-09", 2) }, { "b", Usage("2026-09", 7) }, { "c", Usage("2026-09", 4) },
            };
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "b,c,a", "同星级按频率降序");

            // 星级优先于频率：1 星零使用也要压过 0 星高频。
            records["a"] = Stars(1);
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "a,b,c", "星级优先于频率");
        }

        /// <summary>衰减计数：本月 12 次 &gt; 上月 20 次（12 vs 10），累计总次数不是排序依据。</summary>
        private static void CheckDecay()
        {
            HomePreferenceRecord fresh = Usage("2026-09", 12);
            HomePreferenceRecord fading = Usage("2026-08", 20);
            Close(HomeFeatureRanker.FrequencyScore(fresh, Now), 12.0, "本月权重");
            Close(HomeFeatureRanker.FrequencyScore(fading, Now), 10.0, "上月权重减半");
            True(HomeFeatureRanker.FrequencyScore(fresh, Now) > HomeFeatureRanker.FrequencyScore(fading, Now),
                "正在降温的功能应沉到活跃功能之后");

            var features = new FeatureDescriptor[] { Feature("old", 10), Feature("new", 20) };
            var records = new Dictionary<string, HomePreferenceRecord> { { "old", fading }, { "new", fresh } };
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "new,old", "衰减计数生效");

            // 月初 / 月末同属一个桶，不该出现跨月偏移。
            Close(HomeFeatureRanker.FrequencyScore(fresh, new DateTime(2026, 9, 1, 0, 0, 0, DateTimeKind.Utc)), 12.0, "月初同桶");
            Close(HomeFeatureRanker.FrequencyScore(fresh, new DateTime(2026, 9, 30, 23, 59, 0, DateTimeKind.Utc)), 12.0, "月末同桶");
            Close(HomeFeatureRanker.FrequencyScore(fresh, new DateTime(2026, 10, 1, 0, 0, 0, DateTimeKind.Utc)), 6.0, "跨月后减半");
        }

        /// <summary>出厂顺序是第四关键字；DefaultOrder 相同时用 PageId 字典序保证全序。</summary>
        private static void CheckTieBreak()
        {
            var features = new FeatureDescriptor[] { Feature("b", 10), Feature("a", 20), Feature("c", 20) };
            var records = new Dictionary<string, HomePreferenceRecord>
            {
                { "b", Usage("2026-09", 5) }, { "a", Usage("2026-09", 5) }, { "c", Usage("2026-09", 5) },
            };
            // b 频率最高排最前；a 与 c 同频同序 → 按 PageId 字典序 a 在 c 之前。
            Equal(Order(HomeFeatureRanker.Rank(features, records, Now)), "b,a,c", "频率之后按出厂顺序与 PageId");

            var same = new FeatureDescriptor[] { Feature("zz", 10), Feature("aa", 10) };
            var none = new Dictionary<string, HomePreferenceRecord>();
            Equal(Order(HomeFeatureRanker.Rank(same, none, Now)), "aa,zz", "同键必须回落到 PageId 全序");

            // 排序器不得改变入参顺序（Rank 自己复制一份）。
            List<HomeEntry> first = HomeFeatureRanker.Rank(same, none, Now);
            List<HomeEntry> second = HomeFeatureRanker.Rank(same, none, Now);
            Equal(Order(first), Order(second), "同一输入必须得到同一顺序");
        }

        /// <summary>占位卡（规划中）永远是 0 星、不置顶、排在所有可用功能之后。</summary>
        private static void CheckPlaceholders()
        {
            List<HomeEntry> entries = HomeFeatureRanker.Rank(HomeFeatureCatalog.All(),
                new Dictionary<string, HomePreferenceRecord>
                {
                    { "steel-sections", Stars(5) }, { "n8-connection-plate", Stars(5) },
                }, Now);

            True(entries[0].IsPinned && entries[1].IsPinned, "两个 5 星功能应置顶");
            for (int i = 0; i < entries.Count; i++)
            {
                if (entries[i].Feature.IsReady) continue;
                if (entries[i].IsPinned) throw new Exception("占位卡不应置顶：" + entries[i].Feature.Title);
                Equal(entries[i].Stars, 0, entries[i].Feature.Title + " 占位卡星标");
                True(i >= entries.Count - 2, "占位卡必须排在最后：" + entries[i].Feature.Title);
            }
        }

        /// <summary>脏数据容错：非法桶键、未来月份、过期桶、越界星级、未知 PageId 都不得抛异常或影响排序。</summary>
        private static void CheckRobustness()
        {
            var record = Usage("abc", 99, "2026-13", 99, "202609", 99, "", 99, "2026-10", 99);
            record.MonthlyUse["2026-09"] = 3;
            record.MonthlyUse["2025-09"] = 8;    // 12 个月前：仍保留但权重极低
            record.MonthlyUse["2025-08"] = 8;    // 13 个月前：被丢弃
            double score = HomeFeatureRanker.FrequencyScore(record, Now);
            Close(score, 3.0 + 8.0 * Math.Pow(0.5, 12), "脏桶必须被忽略");

            int monthsAgo;
            True(!HomeFeatureRanker.TryMonthsAgo("2026-10", Now, out monthsAgo), "未来月份应被拒绝");
            True(!HomeFeatureRanker.TryMonthsAgo("abc", Now, out monthsAgo), "非法键应被拒绝");
            True(HomeFeatureRanker.TryMonthsAgo("2026-09", Now, out monthsAgo) && monthsAgo == 0, "本月应为 0 个月前");
            True(HomeFeatureRanker.TryMonthsAgo("2025-09", Now, out monthsAgo) && monthsAgo == 12, "保留期边界");

            var features = new FeatureDescriptor[] { Feature("a", 10), Feature("b", 20) };
            var records = new Dictionary<string, HomePreferenceRecord>
            {
                { "a", Stars(9) }, { "b", Stars(-3) }, { "gone-feature", Stars(5) },
            };
            List<HomeEntry> entries = HomeFeatureRanker.Rank(features, records, Now);
            Equal(entries.Count, 2, "未知 PageId 不应出现在结果里");
            Equal(entries[0].Feature.PageId, "a", "越界星级应被夹到 5");
            Equal(entries[0].Stars, 5, "9 星夹到 5");
            Equal(entries[1].Stars, 0, "-3 星夹到 0");

            Equal(HomeFeatureRanker.Rank(null, null, Now).Count, 0, "空输入不应抛异常");
            Equal(HomeFeatureRanker.Rank(features, null, Now).Count, 2, "无记录时不应抛异常");
            Close(HomeFeatureRanker.FrequencyScore(null, Now), 0.0, "空记录频率为 0");
            Equal(HomeFeatureRanker.MonthKey(Now), "2026-09", "月份桶键");
        }

        private static void CheckUsageLabel()
        {
            Equal(HomeFeatureRanker.UsageLabel(null, Now), "尚未使用", "无记录");
            Equal(HomeFeatureRanker.UsageLabel(new HomePreferenceRecord(), Now), "尚未使用", "零次数");
            Equal(HomeFeatureRanker.UsageLabel(Usage("2026-09", 6, "2026-08", 4), Now), "累计 10 次 · 本月 6 次", "本月有使用");
            Equal(HomeFeatureRanker.UsageLabel(Usage("2026-08", 4), Now), "累计 4 次 · 本月未用", "本月未使用");
        }
    }
}
