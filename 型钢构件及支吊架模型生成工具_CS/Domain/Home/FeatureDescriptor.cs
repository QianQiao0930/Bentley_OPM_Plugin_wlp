namespace SteelSectionProbe
{
    /// <summary>
    /// 首页功能入口的描述符。只描述"首页上要显示哪一项"，不承载任何业务参数。
    /// <para>
    /// <see cref="PageId"/> 必须与对应功能页 <see cref="IWorkspacePage.PageId"/> 逐字一致，
    /// 否则 <c>WorkspaceView.OpenPage</c> 找不到页面；<see cref="DefaultOrder"/> 即"出厂顺序"，
    /// 等于改造前 <c>HomePage.xaml</c> 的卡片顺序，未评分且从未使用的功能按它排列。
    /// </para>
    /// </summary>
    internal sealed class FeatureDescriptor
    {
        /// <summary>占位卡（"规划中"）的出厂顺序基准，保证它们永远排在可用功能之后。</summary>
        internal const int PlaceholderDefaultOrder = 9000;

        public string PageId = "";
        public string Title = "";
        public string Description = "";
        public int DefaultOrder;

        /// <summary>
        /// 首页分区键（见 <c>Data/Home/HomeCategories.cs</c>：建模类 / HGT21629 支吊架 / 统计与扩展 / 规划中）。
        /// 首页据此把卡片分组显示；本类型只存字符串，不认识具体分类名，保持 Domain 层纯净。
        /// </summary>
        public string Category = "";

        /// <summary>卡片左侧图标键（如 <c>elbow</c>），首页据此在 <c>HomePage.xaml</c> 里查几何资源。</summary>
        public string Icon = "";

        /// <summary>false = 尚未开工的占位卡：不参与星标与使用统计，也没有进入按钮。</summary>
        public bool IsReady = true;

        public FeatureDescriptor() { }

        public FeatureDescriptor(string pageId, string title, string description, int defaultOrder)
        {
            PageId = pageId;
            Title = title;
            Description = description;
            DefaultOrder = defaultOrder;
        }

        public FeatureDescriptor(string pageId, string title, string description, int defaultOrder,
            string category, string icon)
        {
            PageId = pageId;
            Title = title;
            Description = description;
            DefaultOrder = defaultOrder;
            Category = category;
            Icon = icon;
        }

        /// <summary>路线图占位卡：无 PageId、不参与排序统计，固定排在所有可用功能之后。</summary>
        internal static FeatureDescriptor Placeholder(string title, string description, int index,
            string category, string icon)
        {
            var descriptor = new FeatureDescriptor("", title, description, PlaceholderDefaultOrder + index,
                category, icon);
            descriptor.IsReady = false;
            return descriptor;
        }
    }
}
