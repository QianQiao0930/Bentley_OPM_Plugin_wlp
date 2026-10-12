using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace SteelSectionProbe
{
    /// <summary>
    /// 离线激活页，不读取或修改 DGN 模型。
    /// </summary>
    internal partial class ActivationPage : UserControl, IWorkspacePage
    {
        public string PageId { get { return "activation"; } }
        public string PageTitle { get { return "软件激活"; } }
        public string PageSubtitle { get { return "永久授权 · 试用授权 · 离线激活"; } }
        public FrameworkElement View { get { return this; } }

        internal ActivationPage()
        {
            InitializeComponent();
        }

        public void OnActivated()
        {
            RefreshStatus();
            ResultText.Text = string.Empty;
        }

        public void OnDeactivated()
        {
            ActivationCodeText.Clear();
        }

        public void OnWorkspaceClosing()
        {
            ActivationCodeText.Clear();
        }

        internal void RefreshStatus()
        {
            ActivationStatusText.Text = LicenseService.DisplayStatus;
            ActivationStatusText.Foreground = (Brush)FindResource(
                LicenseService.IsActivated ? "StatusBrush" : "MutedBrush");
            LicenseInfoText.Text = LicenseService.LicenseDescription;
            if (LicenseService.IsTrial && !LicenseService.IsActivated)
            {
                ResultText.Text = LicenseService.StatusMessage;
                ResultText.Foreground = (Brush)FindResource("ErrorBrush");
            }
            MachineCodeText.Text = LicenseService.MachineCode;
            CopyMachineButton.IsEnabled = MachineCodeText.Text.Length > 0;
            ActivateButton.IsEnabled = true;
        }

        private void CopyMachine_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Clipboard.SetText(LicenseService.MachineCode);
                ShowResult("机器码已复制，请发给软件作者。", false);
            }
            catch (Exception exception)
            {
                ShowResult("复制失败，可选中机器码手动复制：" + exception.Message, true);
            }
        }

        private void Activate_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                LicenseService.Activate(ActivationCodeText.Text);
                ActivationCodeText.Clear();
                RefreshStatus();
                ShowResult(LicenseService.StatusMessage + " 返回首页即可使用全部功能。", false);
            }
            catch (Exception exception)
            {
                ShowResult("激活失败：" + exception.Message, true);
            }
        }

        private void ContactAuthor_Click(object sender, RoutedEventArgs e)
        {
            MainWindow.Current?.ShowAboutPage();
        }

        private void ShowResult(string message, bool isError)
        {
            ResultText.Text = message;
            ResultText.Foreground = (Brush)FindResource(isError ? "ErrorBrush" : "StatusBrush");
            MainWindow.Current?.SetStatus(message, isError);
        }
    }
}
