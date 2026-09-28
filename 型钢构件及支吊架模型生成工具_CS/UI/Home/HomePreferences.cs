using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页偏好的跨会话存储：星标 + 使用次数，
    /// 落盘 <c>%LOCALAPPDATA%\SteelSectionProbe\home_preferences.json</c>（与各页 LastChoice 同一目录）。
    /// <para>
    /// <b>只存"PageId → 记录"，不存顺序</b>：顺序每次由 <see cref="HomeFeatureRanker"/> 算出来，
    /// 因此增删功能不需要迁移数据，也不会留下"存了顺序但功能已改名"的脏数据。
    /// 未知的 PageId（旧版本遗留）加载后原样保留但不会被渲染。
    /// </para>
    /// </summary>
    internal static class HomePreferences
    {
        /// <summary>落盘结构。Version 供将来改权重或结构时做迁移。</summary>
        internal sealed class Store
        {
            public int Version = 1;
            public Dictionary<string, HomePreferenceRecord> Features = new Dictionary<string, HomePreferenceRecord>();
        }

        private static Store cache;
        private static bool dirty;
        private static readonly HashSet<string> SessionCounted = new HashSet<string>(StringComparer.Ordinal);

        internal static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "home_preferences.json");
            }
        }

        private static Store Data
        {
            get
            {
                if (cache == null) cache = Load();
                return cache;
            }
        }

        private static Store Load()
        {
            try
            {
                if (!File.Exists(FilePath)) return new Store();
                string json;
                using (var reader = new StreamReader(FilePath)) json = reader.ReadToEnd();
                Store store = new JavaScriptSerializer().Deserialize<Store>(json);
                if (store == null) return new Store();
                if (store.Features == null) store.Features = new Dictionary<string, HomePreferenceRecord>();
                foreach (KeyValuePair<string, HomePreferenceRecord> item in store.Features)
                {
                    if (item.Value == null) continue;
                    if (item.Value.MonthlyUse == null)
                        item.Value.MonthlyUse = new Dictionary<string, int>(StringComparer.Ordinal);
                }
                return store;
            }
            catch
            {
                // 记不住就记不住，绝不能因此挡住首页。
                return new Store();
            }
        }

        /// <summary>写盘。仅在有改动时真正写文件，且用"临时文件 + 原子替换"避免半写损坏。</summary>
        internal static void Save()
        {
            if (!dirty || cache == null) return;
            string temp = FilePath + ".tmp";
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
                File.WriteAllText(temp, new JavaScriptSerializer().Serialize(cache));
                if (File.Exists(FilePath)) File.Replace(temp, FilePath, null);
                else File.Move(temp, FilePath);
                dirty = false;
            }
            catch
            {
                try
                {
                    File.Copy(temp, FilePath, true);
                    File.Delete(temp);
                    dirty = false;
                }
                catch
                {
                    // 落盘失败不影响使用：内存里的顺序仍然是对的，下次再试。
                }
            }
        }

        private static HomePreferenceRecord RecordOf(string pageId, bool create)
        {
            if (string.IsNullOrEmpty(pageId)) return null;
            HomePreferenceRecord record;
            if (Data.Features.TryGetValue(pageId, out record) && record != null) return record;
            if (!create) return null;
            record = new HomePreferenceRecord();
            Data.Features[pageId] = record;
            dirty = true;
            return record;
        }

        internal static HomePreferenceRecord RecordFor(string pageId)
        {
            return RecordOf(pageId, false);
        }

        internal static int StarsOf(string pageId)
        {
            HomePreferenceRecord record = RecordOf(pageId, false);
            return record == null ? 0 : record.Stars;
        }

        /// <summary>设置星标，0 表示清除评分。</summary>
        internal static void SetStars(string pageId, int stars)
        {
            HomePreferenceRecord record = RecordOf(pageId, true);
            if (record == null) return;
            int value = stars < 0 ? 0 : (stars > 5 ? 5 : stars);
            if (record.Stars == value) return;
            record.Stars = value;
            dirty = true;
            Save();
        }

        /// <summary>
        /// 记一次"进入功能页"。<b>同一次会话内同一功能只记一次</b> ——
        /// 首页要表达的是"我多常需要这个功能"，不是"我点了多少下按钮"。
        /// </summary>
        internal static void RecordUsage(string pageId)
        {
            if (string.IsNullOrEmpty(pageId)) return;
            if (!SessionCounted.Add(pageId)) return;

            HomePreferenceRecord record = RecordOf(pageId, true);
            if (record == null) return;

            DateTime utcNow = DateTime.UtcNow;
            string key = HomeFeatureRanker.MonthKey(utcNow);
            int current;
            record.MonthlyUse.TryGetValue(key, out current);
            record.MonthlyUse[key] = current + 1;
            record.TotalUseCount = record.TotalUseCount + 1;
            record.LastUsedUtc = utcNow.ToString("o", CultureInfo.InvariantCulture);
            Prune(record, utcNow);
            dirty = true;
            Save();
        }

        /// <summary>丢弃格式非法、未来月份或超过保留期的桶，避免文件无限增长。</summary>
        private static void Prune(HomePreferenceRecord record, DateTime utcNow)
        {
            List<string> stale = null;
            foreach (string key in record.MonthlyUse.Keys)
            {
                int monthsAgo;
                if (HomeFeatureRanker.TryMonthsAgo(key, utcNow, out monthsAgo)) continue;
                if (stale == null) stale = new List<string>();
                stale.Add(key);
            }
            if (stale == null) return;
            foreach (string key in stale) record.MonthlyUse.Remove(key);
        }

        /// <summary>清空全部星标与使用统计，首页恢复出厂顺序。</summary>
        internal static void Reset()
        {
            cache = new Store();
            dirty = true;
            Save();
        }

        /// <summary>按当前偏好给出排序后的卡片顺序。</summary>
        internal static List<HomeEntry> Rank(DateTime utcNow)
        {
            return HomeFeatureRanker.Rank(HomeFeatureCatalog.All(), Data.Features, utcNow);
        }
    }
}
