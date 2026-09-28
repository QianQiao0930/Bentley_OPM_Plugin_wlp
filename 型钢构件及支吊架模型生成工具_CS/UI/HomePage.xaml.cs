using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页：把 <see cref="HomeFeatureCatalog"/> 的入口按 <see cref="HomeFeatureRanker"/> 的顺序渲染成卡片。
    /// <para>
    /// 排序输入（星标 + 使用次数）来自 <see cref="HomePreferences"/>；本页只负责"显示"与"改星标"，
    /// 不承载任何业务参数。进入功能页走 <c>FeatureRequested</c>，由 <c>WorkspaceView</c> 订阅。
    /// </para>
    /// </summary>
    internal partial class HomePage : UserControl
    {
        internal event Action<string> FeatureRequested;

        /// <summary>状态栏消息请求（由 WorkspaceView 接到统一状态栏）。</summary>
        internal event Action<string, bool> StatusRequested;

        /// <summary>当前正在设星标的卡片；ContextMenu 不在可视树上，用字段传递目标更可靠。</summary>
        private HomeCardItem starTarget;

        internal HomePage()
        {
            InitializeComponent();
        }

        /// <summary>
        /// 按当前偏好重排并刷新卡片。**评分时不调用** —— 只在回到首页时调用，
        /// 否则用户刚点完星标的卡片会立刻换位置。
        /// </summary>
        internal void Refresh()
        {
            DateTime utcNow = DateTime.UtcNow;
            List<HomeEntry> ranked = HomePreferences.Rank(utcNow);

            var pinned = new List<HomeCardItem>();
            var others = new List<HomeCardItem>();
            foreach (HomeEntry entry in ranked)
            {
                var item = new HomeCardItem(entry, utcNow);
                if (entry.IsPinned) pinned.Add(item);
                else others.Add(item);
            }

            PinnedList.ItemsSource = pinned;
            OtherList.ItemsSource = others;
            PinnedSection.Visibility = pinned.Count > 0 ? Visibility.Visible : Visibility.Collapsed;
            OtherSectionHint.Text = pinned.Count > 0 ? "按“星级 → 使用频率”排序" : "按使用频率自动排序";
        }

        private void Entry_Click(object sender, RoutedEventArgs e)
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
            double row = Math.Max(MeasureRowWidth(PinnedList), MeasureRowWidth(OtherList));
            return row;
        }

        private static double MeasureRowWidth(ItemsControl list)
        {
            if (list == null || list.Items.Count == 0) return 0;
            var card = list.ItemContainerGenerator.ContainerFromIndex(0) as FrameworkElement;
            if (card == null) return 0;
            // 容器是 ContentPresenter：DesiredSize 已含卡片自身的 Margin（0,0,8,8）。
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
            ItemsControl list = PinnedSection.Visibility == Visibility.Visible ? (ItemsControl)PinnedList : OtherList;
            if (list == null || list.ActualWidth <= 0 || ActualWidth <= 0) return 0;
            double chrome = ActualWidth - list.ActualWidth;
            return chrome > 0 ? chrome : 0;
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
            item.ApplyStars(stars);   // 就地更新显示，不重排

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
