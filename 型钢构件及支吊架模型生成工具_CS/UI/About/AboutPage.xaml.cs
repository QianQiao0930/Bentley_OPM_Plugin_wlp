using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;

namespace SteelSectionProbe
{
    /// <summary>
    /// 无需授权即可访问的作者联系页。只复制邮箱或打开邮件草稿，不自动发送邮件。
    /// </summary>
    internal partial class AboutPage : UserControl, IWorkspacePage
    {
        public string PageId { get { return "about"; } }
        public string PageTitle { get { return "关于与联系作者"; } }
        public string PageSubtitle { get { return LicenseService.IsLicensingEnabled ? "版本信息 · 问题反馈 · 授权申请" : "版本信息 · 问题反馈"; } }
        public FrameworkElement View { get { return this; } }

        internal AboutPage()
        {
            InitializeComponent();
            VersionText.Text = ProductInfo.DisplayVersion;
            AuthorText.Text = "作者：" + ProductInfo.AuthorName;
            EmailText.Text = ProductInfo.AuthorEmail;
            LicensingCard.Visibility = LicenseService.IsLicensingEnabled ? Visibility.Visible : Visibility.Collapsed;
            if (!LicenseService.IsLicensingEnabled)
            {
                ContactPurposeText.Text = "反馈问题 · 提出建议";
            }
        }

        public void OnActivated()
        {
        }

        public void OnDeactivated()
        {
        }

        public void OnWorkspaceClosing()
        {
        }

        private void CopyEmail_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Clipboard.SetText(ProductInfo.AuthorEmail);
                MainWindow.Current?.SetStatus("作者邮箱已复制。", false);
            }
            catch (Exception exception)
            {
                MainWindow.Current?.SetStatus("复制失败，可选中邮箱手动复制：" + exception.Message, true);
            }
        }

        private void OpenEmail_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string subject = Uri.EscapeDataString(
                    (LicenseService.IsLicensingEnabled ? "软件反馈与授权申请 · " : "软件反馈 · ") + ProductInfo.DisplayVersion);
                using (Process process = Process.Start(new ProcessStartInfo(
                    "mailto:" + ProductInfo.AuthorEmail + "?subject=" + subject) { UseShellExecute = true }))
                {
                    MainWindow.Current?.SetStatus("已请求打开邮件程序，请填写内容后自行发送。", false);
                }
            }
            catch (Exception exception)
            {
                MainWindow.Current?.SetStatus("无法打开邮件程序，请复制邮箱联系作者：" + exception.Message, true);
            }
        }

        private void OpenActivation_Click(object sender, RoutedEventArgs e)
        {
            MainWindow.Current?.ShowActivationPage();
        }
    }
}
