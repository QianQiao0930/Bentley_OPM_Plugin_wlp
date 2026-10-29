using System;
using System.Reflection;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.Windowing;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool pass, string label) { checks++; if (!pass) throw new Exception(label); }
        [STAThread] private static int Main()
        {
            try
            {
                var addIn = (SteelSectionAddIn)Activator.CreateInstance(typeof(SteelSectionAddIn),
                    BindingFlags.Instance | BindingFlags.NonPublic, null, new object[] { IntPtr.Zero }, null);
                MainWindow.ShowWindow();
                var window = MainWindow.Current;
                var manager = WindowManager.Instance;
                var panel = manager.Panel;
                Check(manager.Registrations == 1 && manager.Location == DockLocation.Right, "首次只注册一个右侧停靠面板");
                Check((string)manager.Id == "SteelSectionProbe.Workspace", "稳定面板标识");
                Check(window.UseHostSize && !window.TopLevel, "由宿主管理尺寸与窗口层级");
                Check(panel.CanDockVertically && !panel.CanDockHorizontally && panel.CanDockInCenter && panel.CanAutoHide, "左右/标签/自动隐藏能力");
                Check(panel.FormBorderStyle == System.Windows.Forms.FormBorderStyle.Sizable, "浮动窗口保留可拖动边框");
                Check(window.MaximumSize.IsEmpty && window.Region == null && window.MinimumSize.Height < 880, "没有固定880高度及圆角裁切");
                window.ShowSteelSectionsPage();
                var page = TestPage.All["steel-sections"];
                Check(page.Activated == 1, "正常进入页面");
                var size = window.Size;
                window.SetHomeLayout(true); window.SetHomeLayout(false, true);
                Check(window.Size == size, "页面切换不改变停靠尺寸");
                MainWindow.ShowWindow();
                Check(manager.Registrations == 1 && page.Activated == 1, "重复打开不重复注册或激活页面");
                panel.Unpinned = true; MainWindow.ShowWindow();
                Check(panel.Expands == 1 && page.Deactivated == 0, "展开自动隐藏面板不取消工具");
                panel.Hide(); panel.Show();
                Check(page.Deactivated == 0, "自动隐藏/标签切换不走关闭清理");
                window.Close();
                Check(!panel.Visible && !window.IsDisposed && page.Deactivated == 1, "底部关闭先清理再隐藏，保留宿主");
                window.Close(); Check(page.Deactivated == 1, "重复关闭幂等");
                MainWindow.ShowWindow();
                Check(ReferenceEquals(window, MainWindow.Current) && manager.Registrations == 1 && page.Activated == 2, "原位置重新打开同一面板并激活");
                page.FailCleanup = true;
                Check(panel.NativeClose() == ContentCloseAction.Disabled && panel.Visible, "清理失败阻止原生关闭");
                window.Close(); Check(panel.Visible, "清理失败阻止底部关闭");
                page.FailCleanup = false;
                Check(panel.NativeClose() == ContentCloseAction.Hide && !panel.Visible && page.Deactivated == 2, "原生X清理后隐藏");
                LicenseService.IsActivated = false; MainWindow.ShowWindow();
                Check(TestPage.All["activation"].Activated == 1 && page.Activated == 2, "隐藏期间授权到期重新打开走激活页");
                Check(HomePreferences.Saves >= 2, "关闭保存用户偏好");
                panel.NativeClose(false);
                Check(window.IsDisposed && MainWindow.Current == null, "宿主销毁释放WPF并清单例");
                foreach (var entry in TestPage.All.Values) Check(entry.Closed == 1, "各页面关闭清理一次 " + entry.PageId);
                MainWindow.ShowWindow();
                Check(manager.Registrations == 2 && !ReferenceEquals(window, MainWindow.Current), "宿主销毁后可以重建");
                var last = MainWindow.Current;
                TestPage.All["steel-sections"].FailClose = true;
                Check(addIn.TryUnload() == Bentley.MstnPlatformNET.AddIn.UnloadingEventArgs.Response.UnloadAbort
                    && !last.IsDisposed && manager.Removals == 0, "清理失败拒绝卸载并保留面板所有权");
                var workspace = typeof(MainWindow).GetField("workspace", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(last);
                var timer = (DispatcherTimer)typeof(WorkspaceView).GetField("licenseTimer", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(workspace);
                Check(timer.IsEnabled, "卸载失败后继续检查授权到期");
                TestPage.All["steel-sections"].FailClose = false;
                Check(addIn.TryUnload() == Bentley.MstnPlatformNET.AddIn.UnloadingEventArgs.Response.UnloadProceed
                    && last.IsDisposed && MainWindow.Current == null && manager.Removals == 1, "卸载解除面板注册并释放工作区");
                addIn.TryUnload(); Check(manager.Removals == 1, "重复卸载幂等");
                LicenseService.IsActivated = true;
                var guarded = new WorkspaceView();
                var open = typeof(WorkspaceView).GetMethod("OpenPage", BindingFlags.NonPublic | BindingFlags.Instance);
                open.Invoke(guarded, new object[] { "equipment-level" });
                var equipment = (EquipmentLevelPage)TestPage.All["equipment-level"];
                Check(equipment.Activated == 1, "设备页面已实际进入");
                equipment.IsBusy = true;
                guarded.ShowHome();
                Check(equipment.Deactivated == 0, "设备处理期间返回首页被阻止");
                open.Invoke(guarded, new object[] { "steel-sections" });
                Check(equipment.Deactivated == 0 && TestPage.All["steel-sections"].Activated == 0, "设备处理期间切换模块被阻止");
                equipment.IsBusy = false; guarded.ShowHome();
                Check(equipment.Deactivated == 1, "设备处理完成后恢复导航");
                guarded.OnWorkspaceClosing();
                Console.WriteLine("PASS: " + checks + " 真实MainWindow/WorkspaceView停靠调用与关闭/重开生命周期检查；Bentley窗口API使用替身，宿主效果需实测。");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
    }
}
