using System;
using System.Windows;
using System.Windows.Controls;
namespace SteelSectionProbe
{
    internal interface IWorkspacePage
    {
        string PageId { get; } string PageTitle { get; } string PageSubtitle { get; } FrameworkElement View { get; }
        void OnActivated(); void OnDeactivated(); void OnWorkspaceClosing();
    }
    internal static class ProductInfo { internal const string DisplayVersion="V0.0.3", AuthorName="魏", AuthorEmail="yo196544wobi@163.com"; }
    internal static class LicenseService
    {
        internal static bool IsLicensingEnabled=true, IsActivated=false, IsTrial=false;
        internal static string DisplayStatus { get { return IsActivated ? "已激活" : "未激活"; } }
        internal const string LicenseDescription="离线展示夹具：永久授权或试用授权。", MachineCode="1234567890ABCDEF1234567890ABCDEF12", StatusMessage="离线授权展示状态";
        internal static void Activate(string text) { throw new InvalidOperationException("UI检查不写入授权文件"); }
    }
    internal sealed class MainWindow
    {
        internal static MainWindow Current=new MainWindow(); internal bool Returned;
        internal string Status; internal bool Error;
        internal void ShowHome(){Returned=true;} internal void ShowActivationPage(){} internal void ShowAboutPage(){}
        internal void BeginTitleDrag(){} internal void MinimizeFromHome(){} internal void Close(){} internal void SetStatus(string text,bool error){Status=text;Error=error;}
    }
    // 查询页使用展示夹具，业务读取与导出另由真实纯计算回归及源码不变检查覆盖。
    internal partial class ComponentPropertiesPage : UserControl
    {
        internal ComponentPropertiesPage(){InitializeComponent();}
        private void Pick_Click(object sender,RoutedEventArgs e){} private void Stop_Click(object sender,RoutedEventArgs e){}
        private void Unit_SelectionChanged(object sender,RoutedEventArgs e){} private void View_Changed(object sender,RoutedEventArgs e){} private void CopyResults_Click(object sender,RoutedEventArgs e){}
    }
    internal partial class SupportStatisticsPage : UserControl
    {
        internal SupportStatisticsPage(){InitializeComponent();}
        private void ReportScrollViewer_SizeChanged(object sender,SizeChangedEventArgs e){} private void ReportScrollViewer_ScrollChanged(object sender,ScrollChangedEventArgs e){}
        private void Refresh_Click(object sender,RoutedEventArgs e){} private void Excel_Click(object sender,RoutedEventArgs e){} private void Json_Click(object sender,RoutedEventArgs e){}
    }
}
