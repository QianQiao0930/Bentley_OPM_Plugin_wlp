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
        private readonly DispatcherTimer licenseTimer;
        private bool panelHidden;

        internal event Action CloseRequested;
        internal SteelSectionPage SteelSections { get; private set; }

        internal WorkspaceView()
        {
            InitializeComponent();

            homePage = new HomePage();
            homePage.FeatureRequested += OpenPage;
            homePage.StatusRequested += SetStatus;
            homePage.SelectionChanged += selected=>HomeEnterButton.IsEnabled=selected;

#if ENABLE_LICENSING
            RegisterPage(new ActivationPage());
#endif
            RegisterPage(new AboutPage());
            SteelSections = new SteelSectionPage();
            RegisterPage(SteelSections);
            RegisterPage(new HandrailPage());
            RegisterPage(new SpiralStairPage());
            RegisterPage(new TankLadderPage());
            RegisterPage(new WallLadderPage());
            RegisterPage(new MagneticGaugePage());
            RegisterPage(new EquipmentLevelPage());
            RegisterPage(new PipeAlignmentPage());
            RegisterPage(new ComponentPropertiesPage());
            RegisterPage(new LineCoordinatesPage());
            RegisterPage(new SupportBindingPage());
            RegisterPage(new ElbowTrunnionPage());
            RegisterPage(new SupportStatisticsPage());
            RegisterPage(new TankManholePage());
            RegisterPage(new SquareManholePage());
            RegisterPage(new NozzlePage());
            RegisterPage(new FireCabinetPage());
            RegisterPage(new HoseCabinetPage());
            RegisterPage(new PipeClampPage());
            RegisterPage(new Q1SupportPage());
            RegisterPage(new G2AnchorPage());
            RegisterPage(new VerticalPipeSupportPage());
            RegisterPage(new ColdRiserGuidePage());
            RegisterPage(new N1CantileverPage());
            RegisterPage(new N2CantileverPage());
            RegisterPage(new N3Page());
            RegisterPage(new N4Page());
            RegisterPage(new D2CantileverPage());
            RegisterPage(new TriangleBracketPage());
            RegisterPage(new LBracketPage());
            RegisterPage(new PortalFramePage());
            RegisterPage(new TFramePage());
            RegisterPage(new PadPlatePage());
            RegisterPage(new N8Page());
            ShowHome();
            licenseTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            licenseTimer.Tick += LicenseTimer_Tick;
            if (LicenseService.IsLicensingEnabled)
            {
                licenseTimer.Start();
            }
        }

        private void RegisterPage(IWorkspacePage page)
        {
            pages.Add(page.PageId, page);
        }

        private void OpenPage(string id)
        {
            if (!CanLeaveCurrentPage()) return;
            if (id != "activation" && id != "about" && !LicenseService.IsActivated)
            {
                ShowActivationPage();
                SetStatus("请先激活软件，再使用功能模块。", true);
                return;
            }

            IWorkspacePage page;
            if (!pages.TryGetValue(id, out page))
            {
                // 首页清单（HomeFeatureCatalog）与页面注册表不一致时才会命中；
                // 不要静默返回，否则表现为"点了没反应"，无从排查。
                SetStatus("未注册的功能模块：" + id, true);
                return;
            }
            // 首页"使用频率"统计的唯一埋点：命令行入口（STEELPROBE PLACE）也走这条路径。
            if (id != "activation" && id != "about")
            {
                HomePreferences.RecordUsage(id);
            }
            if (currentPage != null && !ReferenceEquals(currentPage, page)) currentPage.OnDeactivated();
            currentPage = page;
            PageHost.Content = page.View;
            NativePanelLayout.Apply(page.View);
            bool prototypePage = id == "q1-small-pipe-support" || Equals(page.View.Tag, "prototype-v4");
            if(MainWindow.Current!=null)MainWindow.Current.SetHomeLayout(false, prototypePage);
            page.OnActivated();
            SubtitleText.Text = page.PageTitle + " · " + page.PageSubtitle;
            HomeButton.Visibility = Visibility.Visible;
            SetHeaderVisible(!prototypePage);
            SetStatus("已进入“" + page.PageTitle + "”。", false);
        }

        internal void ShowActivationPage()
        {
            if (LicenseService.IsLicensingEnabled)
            {
                OpenPage("activation");
            }
        }

        internal void ShowAboutPage()
        {
            OpenPage("about");
        }

        private void LicenseTimer_Tick(object sender, EventArgs e)
        {
            if (!LicenseService.IsTrial)
            {
                return;
            }

            homePage.RefreshLicenseStatus();
#if ENABLE_LICENSING
            if (currentPage is ActivationPage activationPage)
            {
                activationPage.RefreshStatus();
            }
#endif

            if (!LicenseService.IsActivated && currentPage != null &&
                currentPage.PageId != "activation" && currentPage.PageId != "about")
            {
                // 通过正常页面生命周期退出点取并清理未确认预览。
                ShowActivationPage();
                SetStatus(LicenseService.StatusMessage, true);
            }
        }

        internal void ShowSteelSectionsPage()
        {
            OpenPage("steel-sections");
        }

        internal void ShowComponentPropertiesPage()
        {
            OpenPage("component-properties");
        }

        internal void ShowHome()
        {
            if (!CanLeaveCurrentPage()) return;
            if (currentPage != null) currentPage.OnDeactivated();
            currentPage = null;
            PageHost.Content = homePage;
            NativePanelLayout.Apply(homePage);
            if(MainWindow.Current!=null)MainWindow.Current.SetHomeLayout(true);
            // 回到首页是唯一的重排时机：评分只就地改显示，卡片不会在用户手下滑走。
            homePage.Refresh();
            SubtitleText.Text = "选择建模或查询功能";
            HomeButton.Visibility = Visibility.Collapsed;
            SetHeaderVisible(false);
            SetStatus("请选择一个功能模块进入工作区。", false);
            ScheduleHomeWidthCheck();
        }

        /// <summary>
        /// 首页由 <see cref="HomePage"/> 自带标题栏（应用图标 + 标题 + 搜索/排序），所以隐藏本层共用标题栏；
        /// 功能页仍用共用标题栏显示"标题 + 副标题 + 返回首页"。行的 <c>MinHeight</c> 一并归零，
        /// 否则隐藏后仍会留下 88 像素空白。
        /// </summary>
        private void SetHeaderVisible(bool visible)
        {
            HeaderRow.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
            HeaderRowDef.MinHeight = visible ? 88 : 0;
        }

        private bool CanLeaveCurrentPage()
        {
            var busyPage = currentPage as IWorkspaceBusyPage;
            if (busyPage == null || !busyPage.IsBusy) return true;
            SetStatus("设备正在处理中，请等待完成后切换页面。", false);
            return false;
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
            BuildStatusPanel.Visibility=Visibility.Collapsed;StatusText.Visibility=Visibility.Visible;
            if(StatusText.Text!=message)StatusText.Text = message;
            StatusText.Foreground = ReferenceEquals(PageHost.Content,homePage)&&!isError?new SolidColorBrush(Color.FromRgb(91,107,123)):(Brush)FindResource(isError ? "ErrorBrush" : "StatusBrush");
            StatusDot.Fill = ReferenceEquals(PageHost.Content,homePage)&&!isError?new SolidColorBrush(Color.FromRgb(232,163,23)):(Brush)FindResource(isError ? "ErrorBrush" : "AccentBrush");
        }
        internal void SetBuildProgress(int percent,string stage,int seconds)
        {
            if(BuildStatusPanel.Visibility!=Visibility.Visible)StatusDot.Fill=(Brush)FindResource("AccentBrush");
            StatusText.Visibility=Visibility.Collapsed;BuildStatusPanel.Visibility=Visibility.Visible;
            string progress="盘梯 "+percent+"%",elapsed="用时 "+seconds+"s";
            if(BuildPercentText.Text!=progress)BuildPercentText.Text=progress;
            if(BuildStageText.Text!=stage){BuildStageText.Text=stage;BuildStageText.ToolTip=stage;}
            if(BuildElapsedText.Text!=elapsed)BuildElapsedText.Text=elapsed;
        }

        internal void OnWorkspaceClosing()
        {
            // Keep expiry checks alive if a page refuses cleanup and unloading is aborted.
            foreach (IWorkspacePage page in pages.Values) page.OnWorkspaceClosing();
            licenseTimer.Stop();
            licenseTimer.Tick -= LicenseTimer_Tick;
            currentPage = null;
            HomePreferences.Save();
        }

        internal void OnPanelHidden()
        {
            if (panelHidden) return;
            if (currentPage != null) currentPage.OnDeactivated();
            HomePreferences.Save();
            licenseTimer.Stop();
            panelHidden = true;
        }

        internal void OnPanelShown()
        {
            if (!panelHidden) return;
            if (currentPage != null)
            {
                if (currentPage.PageId != "activation" && currentPage.PageId != "about" && !LicenseService.IsActivated)
                    ShowActivationPage();
                else currentPage.OnActivated();
            }
            else homePage.Refresh();
            panelHidden = false;
            if (LicenseService.IsLicensingEnabled) licenseTimer.Start();
        }

        private void HomeEnter_Click(object sender,RoutedEventArgs e){homePage.EnterSelected();}

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

