using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页：通常按分类分区显示；最近排序将所有可用入口合并为一个列表。
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

        /// <summary>排序下拉的四档；整数值同时用于界面偏好，保持兼容。</summary>
        private enum SortMode { Default, RecentlyUsed, Frequent, Name }

        /// <summary>"最近使用"最多显示的卡片数。</summary>
        private const int RecentLimit = 4;

        /// <summary>当前正在设星标的卡片；ContextMenu 不在可视树上，用字段传递目标更可靠。</summary>
        private HomeCardItem starTarget;

        private SortMode sortMode = SortMode.Default;
        private string searchText = "";
        private bool ready,compact,pin=true;
        private string categoryTab="all",selectedPageId="";
        internal event Action<bool> SelectionChanged;
        public static readonly DependencyProperty ShowRanksProperty=DependencyProperty.Register("ShowRanks",typeof(bool),typeof(HomePage),new PropertyMetadata(false));
        public bool ShowRanks {get{return (bool)GetValue(ShowRanksProperty);}private set{SetValue(ShowRanksProperty,value);}}
        private Dictionary<string,int> rankForView;
        private int maximumUses=1;

        /// <summary>同一功能的所有卡片实例（最近使用 + 所属分类可能各一份），评分时一起刷新。</summary>
        private readonly Dictionary<string, List<HomeCardItem>> itemsByPageId =
            new Dictionary<string, List<HomeCardItem>>(StringComparer.Ordinal);

        /// <summary>参与行宽/开销实测的卡片列表；校准只取其中第一个非空项。</summary>
        private ItemsControl[] cardLists;

        internal HomePage()
        {
            InitializeComponent();
            cardLists = new ItemsControl[] { RecentList, SortedList, ModelingList, SupportList, StatsList, PlannedList };
            HomePreferences.ViewPreferences view = HomePreferences.ReadView();
            compact = view.Compact;
            sortMode = (SortMode)view.SortMode;
            categoryTab = view.CategoryTab;
            pin = view.PinStars;
            SortBox.SelectedIndex = (int)sortMode;
            ShowRanks = sortMode == SortMode.Frequent;
            SyncViewControls();
            ready = true;
            Refresh();
        }

        /// <summary>
        /// 按当前偏好、搜索词与排序方式重建卡片。调用时机：回到首页、切换排序/搜索，
        /// 以及**点星标之后**（用户要求的"即时重排"，见 <see cref="SetStars_Click"/>）。
        /// </summary>
        internal void Refresh()
        {
            RefreshLicenseStatus();
            VersionText.Text = ProductInfo.DisplayVersion.TrimStart('V');
            AuthorText.Text = "BY " + ProductInfo.AuthorName;
            DateTime utcNow = DateTime.UtcNow;
            List<HomeEntry> ranked = HomePreferences.Rank(utcNow);
            Dictionary<string, int> rankOf = RankIndexMap(ranked);rankForView=rankOf;
            maximumUses=1;foreach(var entry in ranked){var record=HomePreferences.RecordFor(entry.Feature.PageId);if(record!=null)maximumUses=Math.Max(maximumUses,record.TotalUseCount);}

            var filtered = new List<HomeEntry>();
            foreach (HomeEntry entry in ranked)
                if (Matches(entry.Feature)&&MatchesTab(entry)) filtered.Add(entry);

            itemsByPageId.Clear();

            // ---- 最近使用（仅无搜索词时显示；按最近进入时间降序，最多 RecentLimit 张） ----
            var recent = new List<HomeEntry>();
            bool globalRecent = sortMode == SortMode.RecentlyUsed;
            if (!globalRecent && searchText.Length == 0&&categoryTab=="all")
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
            SetSection(RecentSection, recentItems.Count);RecentCountText.Text=recentItems.Count+" 项";

            // ---- 分类分区（建模类 / HGT21629 支吊架 / 统计与扩展 / 规划中）。
            //      顺序与显示名来自 HomeCategories —— 标题文本不写死在 XAML 里，避免两处漂移。 ----
            var hosts = new Dictionary<string, FrameworkElement>(StringComparer.Ordinal);
            var lists = new Dictionary<string, ItemsControl>(StringComparer.Ordinal);
            var titles = new Dictionary<string, TextBlock>(StringComparer.Ordinal);
            var counts = new Dictionary<string, TextBlock>(StringComparer.Ordinal);
            hosts[HomeCategories.Modeling] = ModelingSection;
            hosts[HomeCategories.Support] = SupportSection;
            hosts[HomeCategories.Stats] = StatsSection;
            hosts[HomeCategories.Planned] = PlannedSection;
            lists[HomeCategories.Modeling] = ModelingList;
            lists[HomeCategories.Support] = SupportList;
            lists[HomeCategories.Stats] = StatsList;
            lists[HomeCategories.Planned] = PlannedList;
            titles[HomeCategories.Modeling] = ModelingTitleText;
            titles[HomeCategories.Support] = SupportTitleText;
            titles[HomeCategories.Stats] = StatsTitleText;
            titles[HomeCategories.Planned] = PlannedTitleText;
            counts[HomeCategories.Modeling] = ModelingCountText;
            counts[HomeCategories.Support] = SupportCountText;
            counts[HomeCategories.Stats] = StatsCountText;
            counts[HomeCategories.Planned] = PlannedCountText;

            int shown = 0;
            var sorted = new List<HomeEntry>();
            if (globalRecent)
            {
                foreach (HomeEntry entry in filtered)
                    if (entry.Feature.IsReady) sorted.Add(entry);
                SortGroup(sorted, rankOf);
            }
            SortedList.ItemsSource = BuildItems(sorted, utcNow, true);
            SetSection(SortedSection, sorted.Count);
            SortedCountText.Text = sorted.Count + " 项";
            shown += sorted.Count;
            foreach (HomeCategories.Definition section in HomeCategories.Sections())
            {
                List<HomeEntry> group = globalRecent ? new List<HomeEntry>() : GroupOf(filtered, section.Key);
                SortGroup(group, rankOf);
                List<HomeCardItem> items = BuildItems(group, utcNow, false);
                lists[section.Key].ItemsSource = items;
                SetSection(hosts[section.Key], items.Count);
                SetSectionHeader(titles, counts, section, items.Count);
                shown += items.Count;
            }

            int total=0,months=0,favs=0,models=0,supports=0,stats=0;
            foreach(var entry in ranked)
            {
                if(!entry.Feature.IsReady)continue;total++;
                if(entry.Stars>0)favs++;
                if(entry.Feature.Category==HomeCategories.Modeling)models++;
                if(entry.Feature.Category==HomeCategories.Support)supports++;
                if(entry.Feature.Category==HomeCategories.Stats)stats++;
                var record=HomePreferences.RecordFor(entry.Feature.PageId);int count;
                if(record!=null&&record.MonthlyUse!=null&&record.MonthlyUse.TryGetValue(utcNow.ToString("yyyy-MM",CultureInfo.InvariantCulture),out count))months+=count;
            }
            TotalText.Text=total.ToString();MonthText.Text=months.ToString();FavoriteText.Text=favs.ToString();
            AllTab.Content="全部 "+total;ModelTab.Content="建模 "+models;SupportTab.Content="支吊架 "+supports;StatsTab.Content="查询 "+stats;FavTab.Content="★ 收藏 "+favs;
            ApplyCardView();UpdateSelection();
            EmptyHint.Visibility = shown == 0 ? Visibility.Visible : Visibility.Collapsed;
        }

        /// <summary>分区标题与卡片计数（如「HGT21629 支吊架 · 7 项」）；未知分区不写。 </summary>
        private static void SetSectionHeader(Dictionary<string, TextBlock> titles,
            Dictionary<string, TextBlock> counts, HomeCategories.Definition section, int count)
        {
            TextBlock title;
            if (titles.TryGetValue(section.Key, out title) && title != null)
                title.Text = section.Key==HomeCategories.Modeling?"建模":section.Key==HomeCategories.Stats?"查询与统计":HomeCategories.DisplayNameOf(section.Key);
            TextBlock countText;
            if (counts.TryGetValue(section.Key, out countText) && countText != null)
                countText.Text = count.ToString(CultureInfo.InvariantCulture) + " 项";
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
                item.RankLabel=entry.Feature.IsReady?(RankIndexOf(rankForView,entry)+1).ToString("00"):"";
                item.UsageRatio=100.0*item.UseCount/maximumUses;
                item.IconGeometry = ResolveIcon(item.IconKey);item.IsSelected=item.PageId==selectedPageId;
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
            if (searchText.Length == 0&&categoryTab=="all") return true;
            if (Contains(HomePresentation.Code(feature.PageId),searchText))return true;
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
        /// <para>
        /// ⚠️ 两档显式排序都**先过 <see cref="HomeFeatureRanker.CompareStarTier"/>**（置顶区 → 星级降序）：
        /// 星标是用户的显式意图，不能被"最近/常用"覆盖（曾出现"常用优先时 5 星没有置顶"）。
        /// </para>
        /// </summary>
        private void SortGroup(List<HomeEntry> group, Dictionary<string, int> rankOf)
        {
            if(group.Count<2)return;
            if(sortMode==SortMode.Default&&pin)return;
            if(sortMode==SortMode.Default){group.Sort((a,b)=>a.Feature.DefaultOrder.CompareTo(b.Feature.DefaultOrder));return;}
            if(sortMode==SortMode.Name)
            {
                group.Sort((a,b)=>{int star=pin?HomeFeatureRanker.CompareStarTier(a,b):0;return star!=0?star:string.Compare(a.Feature.Title,b.Feature.Title,StringComparison.CurrentCulture);});return;
            }

            Comparison<HomeEntry> comparison;
            if (sortMode == SortMode.RecentlyUsed)
            {
                comparison = delegate(HomeEntry a, HomeEntry b)
                {
                    int compare = pin?HomeFeatureRanker.CompareStarTier(a, b):0;
                    if (compare != 0) return compare;
                    compare = CompareRecent(a, b);
                    if (compare != 0) return compare;
                    return RankIndexOf(rankOf, a).CompareTo(RankIndexOf(rankOf, b));
                };
            }
            else
            {
                comparison = delegate(HomeEntry a, HomeEntry b)
                {
                    int compare = pin?HomeFeatureRanker.CompareStarTier(a, b):0;
                    if (compare != 0) return compare;
                    if (a.FrequencyScore != b.FrequencyScore)
                        return b.FrequencyScore.CompareTo(a.FrequencyScore);
                    compare = RankIndexOf(rankOf, a).CompareTo(RankIndexOf(rankOf, b));
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
                case 3: sortMode=SortMode.Name;break;
                default: sortMode = SortMode.Default; break;
            }
            ShowRanks=sortMode==SortMode.Frequent;SyncViewControls();SaveView();Refresh();
        }

        private void Card_Click(object sender, RoutedEventArgs e)
        {
            HomeCardItem item = ItemOf(sender);
            if (item == null || !item.CanRate) return;
            if (FeatureRequested != null) FeatureRequested(item.PageId);
        }

        /// <summary>
        /// 一行两张卡片实际需要多宽（含卡片间距与右外边距，单位 = WPF 逻辑宽）。
        /// <para>
        /// 取值来自**真实可视树**，不看 <c>HomeCardButtonStyle</c> 里写死的数字，也不依赖当前是排成
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

        internal void RefreshLicenseStatus()
        {
            ActivationButton.Visibility = LicenseService.IsLicensingEnabled ? Visibility.Visible : Visibility.Collapsed;
            ActivationButton.Content = LicenseService.DisplayStatus;
            ActivationButton.ToolTip = LicenseService.LicenseDescription;
            ActivationButton.Foreground=new SolidColorBrush(LicenseService.IsActivated?Color.FromRgb(34,160,107):Color.FromRgb(181,122,0));
            ActivationButton.Background=new SolidColorBrush(LicenseService.IsActivated?Color.FromRgb(232,247,240):Color.FromRgb(255,246,224));
        }

        private void About_Click(object sender, RoutedEventArgs e)
        {
            FeatureRequested?.Invoke("about");
        }

        private void Activation_Click(object sender, RoutedEventArgs e)
        {
            FeatureRequested?.Invoke("activation");
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

            // 同一功能可能同时显示在"最近使用"与所属分类里，先就地刷新它的全部实例
            //（星标字形立刻变化，不必等重建完成）。
            List<HomeCardItem> bucket;
            if (itemsByPageId.TryGetValue(item.PageId, out bucket))
                foreach (HomeCardItem each in bucket) each.ApplyStars(stars);

            string message;
            if (stars <= 0)
                message = "已清除“" + item.Title + "”的星标，已按新顺序重排。";
            else if (stars >= HomeFeatureRanker.PinThreshold)
                message = "已把“" + item.Title + "”标为 " + stars + " 星，已将卡片置顶。";
            else
                message = "已把“" + item.Title + "”标为 " + stars + " 星（3 星及以上才会置顶）。";
            if (StatusRequested != null) StatusRequested(message, false);

            // ⚠️ **即时重排**：星标一改就重建卡片顺序，不等回到首页。
            // 不能直接在这里 Refresh()：此刻 ContextMenu 还没关（正处在它自己的菜单项 Click 里），
            // 重建 ItemsSource 会把菜单的 PlacementTarget 从可视树上摘掉。改排队到 Background 优先级，
            // 它在"本帧输入处理完（菜单关完）"之后执行，视觉上仍是点完即变。
            Dispatcher.BeginInvoke(new Action(Refresh), DispatcherPriority.Background);
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

        private bool MatchesTab(HomeEntry entry)
        {return categoryTab=="all"||categoryTab==entry.Feature.Category||(categoryTab=="fav"&&entry.Stars>0);}
        private void Tab_Click(object sender,RoutedEventArgs e)
        {
            categoryTab=((FrameworkElement)sender).Tag.ToString();
            SyncViewControls();SaveView();
            Refresh();HomeScroll.ScrollToTop();
        }
        private void Sort_Click(object sender,RoutedEventArgs e)
        {
            var button=(ToggleButton)sender;int index=int.Parse(button.Tag.ToString());SortBox.SelectedIndex=index;
            foreach(var tab in new[]{DefaultSort,RecentSort,FrequentSort,NameSort})tab.IsChecked=tab.Tag.ToString()==index.ToString();
        }
        private void Pin_Click(object sender,RoutedEventArgs e){pin=PinToggle.IsChecked==true;SaveView();Refresh();}
        private void View_Click(object sender,RoutedEventArgs e)
        {
            compact=((FrameworkElement)sender).Tag.ToString()=="compact";
            SyncViewControls();SaveView();ApplyCardView();
        }
        private void SaveView()
        { HomePreferences.SaveView(compact, (int)sortMode, categoryTab, pin); }

        private void SyncViewControls()
        {
            DetailToggle.IsChecked = !compact; CompactToggle.IsChecked = compact;
            PinToggle.IsChecked = pin;
            foreach (var tab in new[] { AllTab, ModelTab, SupportTab, StatsTab, FavTab })
                tab.IsChecked = tab.Tag.ToString() == categoryTab;
            foreach (var tab in new[] { DefaultSort, RecentSort, FrequentSort, NameSort })
                tab.IsChecked = tab.Tag.ToString() == ((int)sortMode).ToString(CultureInfo.InvariantCulture);
        }
        private void ApplyCardView()
        {
            foreach(var list in new[]{SortedList,ModelingList,SupportList,StatsList,PlannedList})
            {
                list.ItemTemplate=(DataTemplate)FindResource(compact?"CompactCardTemplate":"FeatureCardTemplate");
                list.ItemsPanel=(ItemsPanelTemplate)FindResource(compact?"HomeTwoColumns":"HomeSingleColumn");
                list.Margin=compact?new Thickness(-3,0,-3,-6):new Thickness(0);
            }
        }
        private void FilterReset_Click(object sender,RoutedEventArgs e)
        {
            SearchBox.Clear();categoryTab="all";AllTab.IsChecked=true;
            foreach(var tab in new[]{ModelTab,SupportTab,StatsTab,FavTab})tab.IsChecked=false;
            pin=true;PinToggle.IsChecked=true;SortBox.SelectedIndex=0;
            SyncViewControls();SaveView();Refresh();
        }
        private void Section_Click(object sender,RoutedEventArgs e)
        {var list=FindName(((FrameworkElement)sender).Tag.ToString()) as ItemsControl;if(list!=null)list.Visibility=list.Visibility==Visibility.Visible?Visibility.Collapsed:Visibility.Visible;}
        private void SelectCard_Click(object sender,RoutedEventArgs e)
        {
            var item=ItemOf(sender);if(item==null||!item.IsReady)return;
            selectedPageId=item.PageId;UpdateSelection();
            StatusRequested?.Invoke("已选择“"+item.Title+"”，双击或点击进入。",false);
        }
        private void UpdateSelection()
        {
            bool selected=false;
            foreach(var bucket in itemsByPageId.Values)foreach(var item in bucket){item.IsSelected=item.PageId==selectedPageId;selected|=item.IsSelected;}
            SelectionChanged?.Invoke(selected);
        }
        internal void EnterSelected()
        {
            List<HomeCardItem> bucket;
            if(!itemsByPageId.TryGetValue(selectedPageId,out bucket)||bucket.Count==0||!bucket[0].CanRate)return;
            FeatureRequested?.Invoke(selectedPageId);
        }
        private void Go_Click(object sender,RoutedEventArgs e){SelectCard_Click(sender,e);EnterSelected();}
        private void Card_Focused(object sender,System.Windows.Input.KeyboardFocusChangedEventArgs e){SelectCard_Click(sender,new RoutedEventArgs());}
        private void Card_DoubleClick(object sender,System.Windows.Input.MouseButtonEventArgs e){SelectCard_Click(sender,e);EnterSelected();}
        private void Home_KeyDown(object sender,System.Windows.Input.KeyEventArgs e)
        {
            if(e.Key==System.Windows.Input.Key.K&&(System.Windows.Input.Keyboard.Modifiers&System.Windows.Input.ModifierKeys.Control)!=0){SearchBox.Focus();SearchBox.SelectAll();e.Handled=true;}
            else if(e.Key==System.Windows.Input.Key.Enter&&e.OriginalSource is FrameworkElement&&((FrameworkElement)e.OriginalSource).Name=="CardFace"){EnterSelected();e.Handled=true;}
        }
        private void Title_Drag(object sender,System.Windows.Input.MouseButtonEventArgs e){if(e.ChangedButton==System.Windows.Input.MouseButton.Left)MainWindow.Current?.BeginTitleDrag();}
        private void Minimize_Click(object sender,RoutedEventArgs e){MainWindow.Current?.MinimizeFromHome();}
        private void WindowClose_Click(object sender,RoutedEventArgs e){MainWindow.Current?.Close();}

        private static HomeCardItem ItemOf(object sender)
        {
            var element = sender as FrameworkElement;
            return element == null ? null : element.DataContext as HomeCardItem;
        }
    }
}
