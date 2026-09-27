using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

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

            SteelSections = new SteelSectionPage();
            RegisterPage(SteelSections);
            RegisterPage(new ComponentPropertiesPage());
            RegisterPage(new ElbowTrunnionPage());
            RegisterPage(new SupportStatisticsPage());
            RegisterPage(new TankManholePage());
            RegisterPage(new NozzlePage());
            RegisterPage(new PipeClampPage());
            RegisterPage(new G2AnchorPage());
            ShowHome();
        }

        private void RegisterPage(IWorkspacePage page)
        {
            pages.Add(page.PageId, page);
        }

        private void OpenPage(string id)
        {
            IWorkspacePage page;
            if (!pages.TryGetValue(id, out page)) return;
            if (currentPage != null && !ReferenceEquals(currentPage, page)) currentPage.OnDeactivated();
            currentPage = page;
            PageHost.Content = page.View;
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
            SubtitleText.Text = "选择建模或查询功能";
            HomeButton.Visibility = Visibility.Collapsed;
            SetStatus("请选择一个功能模块。", false);
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

