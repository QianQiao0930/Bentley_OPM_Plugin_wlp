using System;
using System.ComponentModel;
using System.Globalization;
using System.Windows.Media;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页一张卡片的数据。每次刷新整体重建（只有 12～14 项，成本可忽略）；
    /// 星标属性支持就地变更通知 —— 评分时只更新显示、<b>不重排</b>，
    /// 否则刚点完的卡片会从手下滑走。
    /// <para>
    /// 参与 XAML 绑定的属性必须是 <c>public</c>（WPF 绑定走反射，不认 internal）。
    /// 同一功能可能同时出现在"最近使用"和它所属分类里，因此一个功能会有<b>多个</b>
    /// <see cref="HomeCardItem"/> 实例（只有"最近使用"里那份 <see cref="TimeText"/> 非空），
    /// 评分时由 <c>HomePage</c> 统一刷新同 PageId 的全部实例。
    /// </para>
    /// </summary>
    internal sealed class HomeCardItem : INotifyPropertyChanged
    {
        public event PropertyChangedEventHandler PropertyChanged;

        private bool hasRating;
        private string starGlyph = "☆";
        private string ratingText = "";

        internal FeatureDescriptor Feature { get; private set; }

        internal string PageId { get { return Feature == null ? "" : Feature.PageId; } }

        internal string Category { get { return Feature == null ? "" : Feature.Category; } }

        internal string IconKey { get { return Feature == null ? "" : Feature.Icon; } }

        internal bool CanRate { get { return Feature != null && Feature.IsReady; } }

        public bool IsReady { get { return Feature != null && Feature.IsReady; } }

        public string Title { get; private set; }

        public string Description { get; private set; }

        /// <summary>使用情况文案，作为卡片提示（占位卡为 null，不显示提示）。</summary>
        public string UsageText { get; private set; }

        /// <summary>"最近使用"分区里的相对时间；其它分区为空串。</summary>
        public string TimeText { get; private set; }

        /// <summary>卡片左侧图标的几何形状，由 <c>HomePage</c> 从 XAML 资源解析后注入。</summary>
        public Geometry IconGeometry { get; internal set; }

        /// <summary>是否已评分（用于星标着色）。</summary>
        public bool HasRating
        {
            get { return hasRating; }
            private set { hasRating = value; Raise("HasRating"); }
        }

        /// <summary>星标字形：已评分为 ★、未评分为 ☆。</summary>
        public string StarGlyph
        {
            get { return starGlyph; }
            private set { starGlyph = value; Raise("StarGlyph"); }
        }

        /// <summary>已评分时显示的星数（如 "5"），未评分为空串。</summary>
        public string RatingText
        {
            get { return ratingText; }
            private set { ratingText = value; Raise("RatingText"); }
        }

        internal HomeCardItem(HomeEntry entry, DateTime utcNow, bool showTime)
        {
            Feature = entry.Feature;
            Title = entry.Feature.Title;
            Description = entry.Feature.Description;

            HomePreferenceRecord record = entry.Feature.IsReady
                ? HomePreferences.RecordFor(entry.Feature.PageId)
                : null;
            UsageText = entry.Feature.IsReady
                ? HomeFeatureRanker.UsageLabel(record, utcNow)
                : null;
            TimeText = showTime && record != null
                ? HomeRelativeTime.Label(record.LastUsedUtc, utcNow)
                : "";

            ApplyStars(entry.Stars);
        }

        /// <summary>就地更新星标显示（不触发重排）。</summary>
        internal void ApplyStars(int stars)
        {
            int value = stars < 0 ? 0 : (stars > 5 ? 5 : stars);
            HasRating = value > 0;
            StarGlyph = value > 0 ? "★" : "☆";
            RatingText = value > 0 ? value.ToString(CultureInfo.InvariantCulture) : "";
        }

        private void Raise(string name)
        {
            PropertyChangedEventHandler handler = PropertyChanged;
            if (handler != null) handler(this, new PropertyChangedEventArgs(name));
        }
    }
}