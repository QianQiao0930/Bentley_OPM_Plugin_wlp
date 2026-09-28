using System;
using System.ComponentModel;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页一张卡片的数据。每次刷新整体重建（只有 12～14 项，成本可忽略）；
    /// 星标三个属性支持就地变更通知 —— 评分时只更新显示、<b>不重排</b>，
    /// 否则刚点完的卡片会从手下滑走。
    /// <para>
    /// 参与 XAML 绑定的属性必须是 <c>public</c>（WPF 绑定走反射，不认 internal）。
    /// </para>
    /// </summary>
    internal sealed class HomeCardItem : INotifyPropertyChanged
    {
        public event PropertyChangedEventHandler PropertyChanged;

        private string starFilled = "";
        private string starEmpty = "☆";
        private string starHint = "评分";

        internal FeatureDescriptor Feature { get; private set; }

        internal string PageId { get { return Feature == null ? "" : Feature.PageId; } }

        internal bool CanRate { get { return Feature != null && Feature.IsReady; } }

        public bool IsReady { get { return Feature != null && Feature.IsReady; } }

        public string Title { get; private set; }

        public string Description { get; private set; }

        public string UsageText { get; private set; }

        /// <summary>已评分的实心星（★ N 个）；未评分为空串。</summary>
        public string StarFilled
        {
            get { return starFilled; }
            private set { starFilled = value; Raise("StarFilled"); }
        }

        /// <summary>未点亮的位置（☆ 5−N 个）；未评分时为单个 ☆。</summary>
        public string StarEmpty
        {
            get { return starEmpty; }
            private set { starEmpty = value; Raise("StarEmpty"); }
        }

        /// <summary>未评分时的"评分"提示文字，已评分时为空。</summary>
        public string StarHint
        {
            get { return starHint; }
            private set { starHint = value; Raise("StarHint"); }
        }

        internal HomeCardItem(HomeEntry entry, DateTime utcNow)
        {
            Feature = entry.Feature;
            Title = entry.Feature.Title;
            Description = entry.Feature.Description;
            UsageText = entry.Feature.IsReady
                ? HomeFeatureRanker.UsageLabel(HomePreferences.RecordFor(entry.Feature.PageId), utcNow)
                : "";
            ApplyStars(entry.Stars);
        }

        /// <summary>就地更新星标显示（不触发重排）。</summary>
        internal void ApplyStars(int stars)
        {
            int value = stars < 0 ? 0 : (stars > 5 ? 5 : stars);
            StarFilled = value > 0 ? new string('★', value) : "";
            StarEmpty = value > 0 ? new string('☆', 5 - value) : "☆";
            StarHint = value > 0 ? "" : "评分";
        }

        private void Raise(string name)
        {
            PropertyChangedEventHandler handler = PropertyChanged;
            if (handler != null) handler(this, new PropertyChangedEventArgs(name));
        }
    }
}
