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

        /// <summary>路线图占位卡：无 PageId、不参与排序统计，固定排在所有可用功能之后。</summary>
        internal static FeatureDescriptor Placeholder(string title, string description, int index)
        {
            var descriptor = new FeatureDescriptor("", title, description, PlaceholderDefaultOrder + index);
            descriptor.IsReady = false;
            return descriptor;
        }
    }
}
