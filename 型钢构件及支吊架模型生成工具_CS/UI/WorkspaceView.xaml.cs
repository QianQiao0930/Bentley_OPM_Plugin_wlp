using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace SteelSectionProbe
{
    internal partial class WorkspaceView : UserControl
    {
        private readonly Dictionary<string, IWorkspacePage> pages = new Dictionary<string, IWorkspacePage>();
        private readonly HomePage homePage;
        private IWorkspacePage currentPage;

        internal event Action CloseRequested;
        internal SteelSectionPage SteelSections { get; private set; }

        internal WorkspaceView()
        {
            InitializeComponent();

            homePage = new HomePage();
            homePage.FeatureRequested += OpenPage;
            homePage.StatusRequested += SetStatus;

            SteelSections = new SteelSectionPage();
            RegisterPage(SteelSections);
            RegisterPage(new ComponentPropertiesPage());
            RegisterPage(new ElbowTrunnionPage());
            RegisterPage(new SupportStatisticsPage());
            RegisterPage(new TankManholePage());
            RegisterPage(new NozzlePage());
            RegisterPage(new PipeClampPage());
            RegisterPage(new G2AnchorPage());
            RegisterPage(new VerticalPipeSupportPage());
            RegisterPage(new N3Page());
            RegisterPage(new N4Page());
            RegisterPage(new N8Page());
            ShowHome();
        }

        private void RegisterPage(IWorkspacePage page)
        {
            pages.Add(page.PageId, page);
        }

        private void OpenPage(string id)
        {
            IWorkspacePage page;
            if (!pages.TryGetValue(id, out page))
            {
                // 首页清单（HomeFeatureCatalog）与页面注册表不一致时才会命中；
                // 不要静默返回，否则表现为"点了没反应"，无从排查。
                SetStatus("未注册的功能模块：" + id, true);
                return;
            }
            // 首页"使用频率"统计的唯一埋点：命令行入口（STEELPROBE PLACE）也走这条路径。
            HomePreferences.RecordUsage(id);
            if (currentPage != null && !ReferenceEquals(currentPage, page)) currentPage.OnDeactivated();
            currentPage = page;
            PageHost.Content = page.View;
            if(MainWindow.Current!=null)MainWindow.Current.SetHomeLayout(false);
            page.OnActivated();
            SubtitleText.Text = page.PageTitle + " · " + page.PageSubtitle;
            HomeButton.Visibility = Visibility.Visible;
            SetStatus("已进入“" + page.PageTitle + "”。", false);
        }

        internal void ShowSteelSectionsPage()
        {
            OpenPage("steel-sections");
        }

        internal void ShowHome()
        {
            if (currentPage != null) currentPage.OnDeactivated();
            currentPage = null;
            PageHost.Content = homePage;
            if(MainWindow.Current!=null)MainWindow.Current.SetHomeLayout(true);
            // 回到首页是唯一的重排时机：评分只就地改显示，卡片不会在用户手下滑走。
            homePage.Refresh();
            SubtitleText.Text = "选择建模或查询功能";
            HomeButton.Visibility = Visibility.Collapsed;
            SetStatus("请选择一个功能模块。", false);
            ScheduleHomeWidthCheck();
        }

        /// <summary>首页宽度校准的剩余尝试次数（防止布局抖动时反复改窗口尺寸）。</summary>
        private int homeWidthChecksLeft;

        /// <summary>
        /// 按**真实可视树**校准首页窗口宽度：卡片行需要多宽 + 页边距 + 滚动条开销，
        /// 全部实测得到，不依赖任何写死的数字。
        /// <para>
        /// 这样即使卡片尺寸、字体、Dpi 缩放或页面边距发生变化，首页也总能恰好容纳两列；
        /// 万一环境与预期不符（例如实测宽度更大），也只会自动加宽，绝不会掉成单列。
        /// </para>
        /// </summary>
        internal void ScheduleHomeWidthCheck()
        {
            homeWidthChecksLeft = 3;
            Dispatcher.BeginInvoke(new Action(CheckHomeWidth), DispatcherPriority.Background);
        }

        private void CheckHomeWidth()
        {
            if (homeWidthChecksLeft <= 0) return;
            if (!ReferenceEquals(PageHost.Content, homePage)) return;   // 已经不在首页了
            if (MainWindow.Current == null) return;

            double row = homePage.MeasureRowWidth();
            double chrome = homePage.MeasureChromeWidth();
            if (row <= 0)
            {
                // 还没布局出来（首帧/刚切页面）：稍后再量，不要就这么放弃校准。
                homeWidthChecksLeft--;
                if (homeWidthChecksLeft > 0)
                    Dispatcher.BeginInvoke(new Action(CheckHomeWidth), DispatcherPriority.Background);
                return;
            }

            // 页面（PageHost）左右被外边距吃掉的宽度：用"工作区宽 − 页面宽"实测，而不是读 Margin 设定值。
            double pageMargin = ActualWidth - PageHost.ActualWidth;
            if (pageMargin < 0) pageMargin = 0;

            double needed = pageMargin + row + chrome + 8;   // +8 = 右侧呼吸余量
            homeWidthChecksLeft--;
            if (!MainWindow.Current.ApplyHomeWidth(needed)) homeWidthChecksLeft = 0;   // 已收敛
            if (homeWidthChecksLeft > 0)
                Dispatcher.BeginInvoke(new Action(CheckHomeWidth), DispatcherPriority.Background);
        }

        internal void SetStatus(string message, bool isError)
        {
            if (!Dispatcher.CheckAccess())
            {
                Dispatcher.BeginInvoke(new Action(delegate { SetStatus(message, isError); }));
                return;
            }
            StatusText.Text = message;
            StatusText.Foreground = (Brush)FindResource(isError ? "ErrorBrush" : "StatusBrush");
            StatusDot.Fill = (Brush)FindResource(isError ? "ErrorBrush" : "AccentBrush");
        }

        internal void OnWorkspaceClosing()
        {
            foreach (IWorkspacePage page in pages.Values) page.OnWorkspaceClosing();
            currentPage = null;
            HomePreferences.Save();
        }

        private void HomeButton_Click(object sender, RoutedEventArgs e)
        {
            ShowHome();
        }

        private void CloseButton_Click(object sender, RoutedEventArgs e)
        {
            if (CloseRequested != null) CloseRequested();
        }
    }
}

