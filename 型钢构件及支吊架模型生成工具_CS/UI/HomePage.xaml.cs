using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页：把 <see cref="HomeFeatureCatalog"/> 的入口按"最近使用 + 分类分区"渲染成卡片。
    /// <para>
    /// 排序输入（星标 + 使用次数 + 最近进入时间）来自 <see cref="HomePreferences"/>；
    /// 本页只负责"显示、过滤、排序与改星标"，不承载任何业务参数。
    /// 进入功能页走 <c>FeatureRequested</c>，由 <c>WorkspaceView</c> 订阅。
    /// </para>
    /// </summary>
    internal partial class HomePage : UserControl
    {
        internal event Action<string> FeatureRequested;

        /// <summary>状态栏消息请求（由 WorkspaceView 接到统一状态栏）。</summary>
        internal event Action<string, bool> StatusRequested;

        /// <summary>排序下拉的三档，见 <see cref="HomePage"/> 注释。</summary>
        private enum SortMode { Default, RecentlyUsed, Frequent }

        /// <summary>"最近使用"最多显示的卡片数。</summary>
        private const int RecentLimit = 4;

        /// <summary>当前正在设星标的卡片；ContextMenu 不在可视树上，用字段传递目标更可靠。</summary>
        private HomeCardItem starTarget;

        private SortMode sortMode = SortMode.Default;
        private string searchText = "";
        private bool ready;

        /// <summary>同一功能的所有卡片实例（最近使用 + 所属分类可能各一份），评分时一起刷新。</summary>
        private readonly Dictionary<string, List<HomeCardItem>> itemsByPageId =
            new Dictionary<string, List<HomeCardItem>>(StringComparer.Ordinal);

        /// <summary>参与行宽/开销实测的卡片列表；校准只取其中第一个非空项。</summary>
        private ItemsControl[] cardLists;

        internal HomePage()
        {
            InitializeComponent();
            cardLists = new ItemsControl[] { RecentList, ModelingList, SupportList, StatsList, PlannedList };
            SortBox.SelectedIndex = 0;
            ready = true;
            Refresh();
        }

        /// <summary>
        /// 按当前偏好、搜索词与排序方式重建卡片。**评分时不调用** —— 只在回到首页、
        /// 切换排序/搜索时调用，否则用户刚点完星标的卡片会立刻换位置。
        /// </summary>
        internal void Refresh()
        {
            DateTime utcNow = DateTime.UtcNow;
            List<HomeEntry> ranked = HomePreferences.Rank(utcNow);
            Dictionary<string, int> rankOf = RankIndexMap(ranked);

            var filtered = new List<HomeEntry>();
            foreach (HomeEntry entry in ranked)
                if (Matches(entry.Feature)) filtered.Add(entry);

            itemsByPageId.Clear();

            // ---- 最近使用（仅无搜索词时显示；按最近进入时间降序，最多 RecentLimit 张） ----
            var recent = new List<HomeEntry>();
            if (searchText.Length == 0)
            {
                foreach (HomeEntry entry in ranked)
                {
                    if (!entry.Feature.IsReady) continue;
                    HomePreferenceRecord record = HomePreferences.RecordFor(entry.Feature.PageId);
                    if (record == null || !HomeRelativeTime.Parse(record.LastUsedUtc).HasValue) continue;
                    recent.Add(entry);
                }
                recent.Sort(CompareRecent);
                if (recent.Count > RecentLimit) recent.RemoveRange(RecentLimit, recent.Count - RecentLimit);
            }
            List<HomeCardItem> recentItems = BuildItems(recent, utcNow, true);
            RecentList.ItemsSource = recentItems;
            SetSection(RecentSection, recentItems.Count);

            // ---- 分类分区（建模类 / 支撑架类 / 统计与扩展 / 规划中）。顺序与显示名来自 HomeCategories ----
            var hosts = new Dictionary<string, FrameworkElement>(StringComparer.Ordinal);
            var lists = new Dictionary<string, ItemsControl>(StringComparer.Ordinal);
            hosts[HomeCategories.Modeling] = ModelingSection;
            hosts[HomeCategories.Support] = SupportSection;
            hosts[HomeCategories.Stats] = StatsSection;
            hosts[HomeCategories.Planned] = PlannedSection;
            lists[HomeCategories.Modeling] = ModelingList;
            lists[HomeCategories.Support] = SupportList;
            lists[HomeCategories.Stats] = StatsList;
            lists[HomeCategories.Planned] = PlannedList;

            int shown = 0;
            foreach (HomeCategories.Definition section in HomeCategories.Sections())
            {
                List<HomeEntry> group = GroupOf(filtered, section.Key);
                SortGroup(group, rankOf);
                List<HomeCardItem> items = BuildItems(group, utcNow, false);
                lists[section.Key].ItemsSource = items;
                SetSection(hosts[section.Key], items.Count);
                shown += items.Count;
            }

            EmptyHint.Visibility = shown == 0 ? Visibility.Visible : Visibility.Collapsed;
        }

        /// <summary>未知分类的卡片不渲染（不静默串到别的分区），因此只在已知分区里收集。</summary>
        private static List<HomeEntry> GroupOf(List<HomeEntry> filtered, string category)
        {
            var group = new List<HomeEntry>();
            foreach (HomeEntry entry in filtered)
                if (entry.Feature.Category == category) group.Add(entry);
            return group;
        }

        /// <summary>把一批排序结果变成卡片实例，并登记进 <see cref="itemsByPageId"/>。</summary>
        private List<HomeCardItem> BuildItems(List<HomeEntry> entries, DateTime utcNow, bool showTime)
        {
            var items = new List<HomeCardItem>();
            foreach (HomeEntry entry in entries)
            {
                var item = new HomeCardItem(entry, utcNow, showTime);
                item.IconGeometry = ResolveIcon(item.IconKey);
                items.Add(item);

                if (string.IsNullOrEmpty(item.PageId)) continue;
                List<HomeCardItem> bucket;
                if (!itemsByPageId.TryGetValue(item.PageId, out bucket))
                {
                    bucket = new List<HomeCardItem>();
                    itemsByPageId[item.PageId] = bucket;
                }
                bucket.Add(item);
            }
            return items;
        }

        /// <summary>按 <c>FeatureDescriptor.Icon</c> 查 <c>HomeIcon_&lt;key&gt;</c> 几何；查不到返回 null（图标位留空）。</summary>
        private Geometry ResolveIcon(string key)
        {
            if (string.IsNullOrEmpty(key)) return null;
            return TryFindResource("HomeIcon_" + key) as Geometry;
        }

        /// <summary>搜索是否命中：标题、说明或所属分区中文名包含关键词（忽略大小写）。</summary>
        private bool Matches(FeatureDescriptor feature)
        {
            if (searchText.Length == 0) return true;
            if (Contains(feature.Title, searchText)) return true;
            if (Contains(feature.Description, searchText)) return true;
            return Contains(HomeCategories.DisplayNameOf(feature.Category), searchText);
        }

        private static bool Contains(string source, string value)
        {
            return !string.IsNullOrEmpty(source)
                && source.IndexOf(value, StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static void SetSection(FrameworkElement host, int count)
        {
            if (host == null) return;
            host.Visibility = count > 0 ? Visibility.Visible : Visibility.Collapsed;
        }

        /// <summary>PageId → 排序器里的名次，作为分区内排序的稳定兜底。</summary>
        private static Dictionary<string, int> RankIndexMap(List<HomeEntry> ranked)
        {
            var map = new Dictionary<string, int>(StringComparer.Ordinal);
            int index = 0;
            foreach (HomeEntry entry in ranked)
            {
                string id = entry.Feature.PageId;
                if (string.IsNullOrEmpty(id) || map.ContainsKey(id)) { index++; continue; }
                map[id] = index++;
            }
            return map;
        }

        private static int RankIndexOf(Dictionary<string, int> rankOf, HomeEntry entry)
        {
            int index;
            if (rankOf != null && !string.IsNullOrEmpty(entry.Feature.PageId)
                && rankOf.TryGetValue(entry.Feature.PageId, out index)) return index;
            return int.MaxValue;
        }

        private static DateTime LastUsedOf(HomeEntry entry)
        {
            HomePreferenceRecord record = HomePreferences.RecordFor(entry.Feature.PageId);
            DateTime? value = record == null ? null : HomeRelativeTime.Parse(record.LastUsedUtc);
            return value.HasValue ? value.Value : DateTime.MinValue;
        }

        /// <summary>最近进入时间降序；同刻按 PageId 全序兜底（List.Sort 不稳定）。</summary>
        private static int CompareRecent(HomeEntry a, HomeEntry b)
        {
            int compare = LastUsedOf(b).CompareTo(LastUsedOf(a));
            if (compare != 0) return compare;
            return string.CompareOrdinal(a.Feature.PageId ?? "", b.Feature.PageId ?? "");
        }

        /// <summary>
        /// 分区内排序：默认沿用排序器给出的全序；"最近使用/常用优先"是用户显式指定的另一种口径，
        /// 同值时仍回落到排序器名次，避免顺序漂移。
        /// </summary>
        private void SortGroup(List<HomeEntry> group, Dictionary<string, int> rankOf)
        {
            if (sortMode == SortMode.Default || group.Count < 2) return;

            Comparison<HomeEntry> comparison;
            if (sortMode == SortMode.RecentlyUsed)
            {
                comparison = delegate(HomeEntry a, HomeEntry b)
                {
                    int compare = CompareRecent(a, b);
                    if (compare != 0) return compare;
                    return RankIndexOf(rankOf, a).CompareTo(RankIndexOf(rankOf, b));
                };
            }
            else
            {
                comparison = delegate(HomeEntry a, HomeEntry b)
                {
                    if (a.FrequencyScore != b.FrequencyScore)
                        return b.FrequencyScore.CompareTo(a.FrequencyScore);
                    int compare = RankIndexOf(rankOf, a).CompareTo(RankIndexOf(rankOf, b));
                    if (compare != 0) return compare;
                    return a.Feature.DefaultOrder.CompareTo(b.Feature.DefaultOrder);
                };
            }
            group.Sort(comparison);
        }

        private void Search_TextChanged(object sender, TextChangedEventArgs e)
        {
            SearchPlaceholder.Visibility = SearchBox.Text.Length == 0
                ? Visibility.Visible : Visibility.Collapsed;
            if (!ready) return;
            searchText = (SearchBox.Text ?? "").Trim();
            Refresh();
        }

        private void Sort_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!ready) return;
            switch (SortBox.SelectedIndex)
            {
                case 1: sortMode = SortMode.RecentlyUsed; break;
                case 2: sortMode = SortMode.Frequent; break;
                default: sortMode = SortMode.Default; break;
            }
            Refresh();
        }

        private void Card_Click(object sender, MouseButtonEventArgs e)
        {
            HomeCardItem item = ItemOf(sender);
            if (item == null || !item.CanRate) return;
            if (FeatureRequested != null) FeatureRequested(item.PageId);
        }

        /// <summary>
        /// 一行两张卡片实际需要多宽（含卡片间距与右外边距，单位 = WPF 逻辑宽）。
        /// <para>
        /// 取值来自**真实可视树**，不看 <c>HomeCardStyle</c> 里写死的数字，也不依赖当前是排成
        /// 一行还是两行（内容尺寸与排布结果无关）。可视树尚未布局时返回 0，调用方应保留原宽度。
        /// </para>
        /// </summary>
        internal double MeasureRowWidth()
        {
            foreach (ItemsControl list in cardLists)
            {
                if (list == null || list.Items.Count == 0) continue;
                double row = MeasureRowWidth(list);
                if (row > 0) return row;
            }
            return 0;
        }

        private static double MeasureRowWidth(ItemsControl list)
        {
            if (list == null || list.Items.Count == 0) return 0;
            var card = list.ItemContainerGenerator.ContainerFromIndex(0) as FrameworkElement;
            if (card == null) return 0;
            // 容器是 ContentPresenter：DesiredSize 已含卡片自身的 Margin（0,0,12,12）。
            double outer = card.DesiredSize.Width;
            if (outer <= 0) outer = card.ActualWidth + card.Margin.Left + card.Margin.Right;
            return outer <= 0 ? 0 : outer * 2;
        }

        /// <summary>
        /// 卡片可用视口之外的开销（竖向滚动条 + ScrollViewer 右内边距），单位 = WPF 逻辑宽。
        /// 用"页面宽度 − 列表宽度"实测，因此滚动条是否出现都算得准。
        /// </summary>
        internal double MeasureChromeWidth()
        {
            if (ActualWidth <= 0) return 0;
            foreach (ItemsControl list in cardLists)
            {
                if (list == null || list.ActualWidth <= 0) continue;
                double chrome = ActualWidth - list.ActualWidth;
                if (chrome > 0) return chrome;
            }
            return 0;
        }

        /// <summary>点星标按钮：打开 1～5 星的评分菜单。</summary>
        private void Star_Click(object sender, RoutedEventArgs e)
        {
            var button = sender as Button;
            if (button == null) return;
            starTarget = button.DataContext as HomeCardItem;
            if (starTarget == null || !starTarget.CanRate) return;
            ContextMenu menu = button.ContextMenu;
            if (menu == null) return;
            menu.PlacementTarget = button;
            menu.Placement = PlacementMode.Bottom;
            menu.IsOpen = true;
        }

        /// <summary>右键也能打开同一个菜单，这里补一次目标（并拦住占位卡）。</summary>
        private void Star_MenuOpening(object sender, ContextMenuEventArgs e)
        {
            var button = sender as Button;
            starTarget = button == null ? null : button.DataContext as HomeCardItem;
            if (starTarget == null || !starTarget.CanRate) e.Handled = true;
        }

        private void SetStars_Click(object sender, RoutedEventArgs e)
        {
            HomeCardItem item = starTarget;
            starTarget = null;
            var menuItem = sender as MenuItem;
            if (item == null || menuItem == null || menuItem.Tag == null) return;

            int stars;
            if (!int.TryParse(menuItem.Tag.ToString(), out stars)) return;
            HomePreferences.SetStars(item.PageId, stars);

            // 同一功能可能同时显示在"最近使用"与所属分类里，就地刷新它的全部实例。
            List<HomeCardItem> bucket;
            if (itemsByPageId.TryGetValue(item.PageId, out bucket))
                foreach (HomeCardItem each in bucket) each.ApplyStars(stars);

            string message;
            if (stars <= 0)
                message = "已清除“" + item.Title + "”的星标。";
            else if (stars >= HomeFeatureRanker.PinThreshold)
                message = "已把“" + item.Title + "”标为 " + stars + " 星，将置顶显示；回到首页即按新顺序排列。";
            else
                message = "已把“" + item.Title + "”标为 " + stars + " 星（3 星及以上才会置顶）。";
            if (StatusRequested != null) StatusRequested(message, false);
        }

        private void Reset_Click(object sender, RoutedEventArgs e)
        {
            MessageBoxResult answer = MessageBox.Show(
                "将清除所有星标与使用统计，首页恢复为出厂顺序。确定继续吗？",
                "重置排序", MessageBoxButton.OKCancel, MessageBoxImage.Question);
            if (answer != MessageBoxResult.OK) return;

            HomePreferences.Reset();
            Refresh();
            if (StatusRequested != null) StatusRequested("首页排序已重置为出厂顺序。", false);
        }

        private static HomeCardItem ItemOf(object sender)
        {
            var element = sender as FrameworkElement;
            return element == null ? null : element.DataContext as HomeCardItem;
        }
    }
}