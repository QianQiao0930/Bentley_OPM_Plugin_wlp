using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Windows.Forms.Integration;
using Bentley.MstnPlatformNET.WinForms;
using Bentley.Windowing;

namespace SteelSectionProbe
{
    /// <summary>
    /// Bentley owns the docking frame; ElementHost carries the existing WPF workspace.
    /// </summary>
    internal sealed class MainWindow : Adapter
    {
        private readonly ElementHost elementHost = new ElementHost();
        private readonly WorkspaceView workspace;

        private const string PanelId = "SteelSectionProbe.Workspace";
        private WindowContent panel;
        private Timer floatingChromeTimer;
        private Form floatingChromeHost;
        private bool panelOpen;
        private bool workspaceDisposed;
        internal static MainWindow Current;
        internal SteelSectionPage SteelSections { get { return workspace.SteelSections; } }

        internal static void ShowWindow()
        {
            if (Current == null || Current.IsDisposed) Current = new MainWindow();
            Current.ShowPanel();
        }

        internal static void UnloadWindow()
        {
            MainWindow window = Current;
            if (window == null || window.IsDisposed) return;
            // Keep the live owner if preview cleanup fails; the AddIn can refuse unloading.
            window.ReleaseWorkspace();
            if (window.panel != null) WindowManager.GetForMicroStation().RemoveContent(window.panel);
            window.Dispose();
        }

        private MainWindow()
        {
            Text = "型钢构件及支吊架模型生成工具";
            Name = PanelId;
            TopLevel = false;
            FormBorderStyle = FormBorderStyle.None;
            AutoScaleMode = AutoScaleMode.None;
            BackColor = Color.FromArgb(245, 246, 248);
            DoubleBuffered = true;

            UseHostSize = true;

            workspace = new WorkspaceView();
            workspace.CloseRequested += Close;
            elementHost.Dock = DockStyle.Fill;
            elementHost.BackColor = BackColor;
            elementHost.Child = workspace;
            Controls.Add(elementHost);

            MinimumSize = new Size(ToDevicePixels(400), ToDevicePixels(560));
            Size = new Size(ToDevicePixels(400), ToDevicePixels(720));
        }

        private void ShowPanel()
        {
            if (panel == null)
            {
                // Stable identity lets Bentley reuse its saved zone and tab group.
                // Do not also AttachAsTopLevelForm: that creates a second window owner.
                panel = WindowManager.GetForMicroStation().DockPanel(this, PanelId, Text,
                    DockLocation.Right, Size, Size);
                panel.CanDockVertically = true;
                panel.CanDockHorizontally = false;
                panel.CanDockInCenter = true;
                panel.CanAutoHide = true;
                panel.Closeable = true;
                // 浮动后若没有边框，窗口没有可拖动的标题栏，会停在拉出时的位置。
                panel.FormBorderStyle = FormBorderStyle.Sizable;
                panel.MinimumSize = MinimumSize;
                panel.ContentCloseQuery += Panel_CloseQuery;
            }
            if (!panelOpen)
            {
                workspace.OnPanelShown();
                panelOpen = true;
            }
            panel.Show();
            EnsureFloatingChrome();
            if (floatingChromeTimer == null)
            {
                floatingChromeTimer = new Timer { Interval = 400 };
                floatingChromeTimer.Tick += delegate { EnsureFloatingChrome(); };
            }
            floatingChromeTimer.Start();
            UpdateMinimumSize();
            if (panel.Unpinned) panel.AutoHideExpand();
            panel.Zone.SetFocus();
        }

        private void Panel_CloseQuery(object sender, ContentCloseEventArgs e)
        {
            ContentCloseAction action = e.UserAction ? ContentCloseAction.Hide : e.CloseAction;
            e.CloseAction = ContentCloseAction.Disabled;
            try
            {
                if (panelOpen) workspace.OnPanelHidden();
                panelOpen = false;
                if (floatingChromeTimer != null) floatingChromeTimer.Stop();
                e.CloseAction = action;
            }
            catch (Exception ex)
            {
                // A failed preview cleanup must leave its owner available for retry.
                workspace.SetStatus("关闭前清理失败，请重试：" + ex.Message, true);
            }
        }

        public new void Close()
        {
            if (panel == null || !panelOpen) return;
            try
            {
                workspace.OnPanelHidden();
                if (floatingChromeTimer != null) floatingChromeTimer.Stop();
                panel.Hide();
                panelOpen = false;
            }
            catch (Exception ex)
            {
                workspace.SetStatus("关闭前清理失败，请重试：" + ex.Message, true);
            }
        }

        // Retained for existing page event handlers. Native caption owns these actions.
        internal void BeginTitleDrag()
        {
            Form host = panel == null ? null : panel.FloatingHostForm;
            if (host == null || host.IsDisposed || !host.IsHandleCreated) return;
            EnsureFloatingChrome();
            // 只移动 Bentley 的浮动宿主，内容仍留在停靠区里，才能再拖回边缘停靠。
            ReleaseCapture();
            SendMessage(host.Handle, 0xA1, (IntPtr)2, IntPtr.Zero);
        }

        private void EnsureFloatingChrome()
        {
            Form host = panel == null ? null : panel.FloatingHostForm;
            if (host == null || host.IsDisposed)
            {
                floatingChromeHost = null;
                return;
            }
            if (!ReferenceEquals(floatingChromeHost, host))
            {
                if (floatingChromeHost != null) floatingChromeHost.FormClosing -= FloatingHost_FormClosing;
                floatingChromeHost = host;
                host.FormClosing += FloatingHost_FormClosing;
            }
            host.ShowInTaskbar = false;
            host.Text = Text;
            if (host.FormBorderStyle != FormBorderStyle.Sizable)
                host.FormBorderStyle = FormBorderStyle.Sizable;
            host.ControlBox = true;
            host.MinimizeBox = true;
            host.MaximizeBox = true;
        }

        private void FloatingHost_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (e.CloseReason != CloseReason.UserClosing) return;
            e.Cancel = true;
            Close();
        }
        internal void MinimizeFromHome() { if (panel != null) panel.AutoHideUnpin(); }

        internal void ShowActivationPage()
        {
            workspace.ShowActivationPage();
        }

        internal void ShowAboutPage()
        {
            workspace.ShowAboutPage();
        }

        internal void ShowSteelSectionsPage()
        {
            workspace.ShowSteelSectionsPage();
        }

        internal void ShowComponentPropertiesPage()
        {
            workspace.ShowComponentPropertiesPage();
        }

        internal void ShowHome()
        {
            workspace.ShowHome();
        }

        /// <summary>页面切换不能修改 Bentley 停靠区域的尺寸。</summary>
        internal void SetHomeLayout(bool home, bool prototypeModule = false)
        {
        }

        /// <summary>保留校准接口；宽度只由 Bentley 分隔条管理。</summary>
        internal bool ApplyHomeWidth(double measuredLogicalWidth)
        {
            return false; // Width belongs to Bentley's docking splitter.
        }

        /// <summary>逻辑宽度（96 dpi 基准）→ 当前 DPI 的设备像素。取不到 DPI 时按 1:1 处理。</summary>
        private int ToDevicePixels(int logicalWidth)
        {
            double scale = DeviceDpi / 96.0;
            try
            {
                if (elementHost.Child != null && System.Windows.PresentationSource.FromVisual(elementHost.Child) != null)
                {
                    // 全限定名：本文件已有 System.Drawing（Color/Size），不要再 using System.Windows.Media。
                    var dpi = System.Windows.Media.VisualTreeHelper.GetDpi(
                        (System.Windows.Media.Visual)elementHost.Child);
                    if (dpi.DpiScaleX > 0.0) scale = dpi.DpiScaleX;
                }
            }
            catch
            {
                // 取不到就按 1:1，至少不会比现在更糟。
            }
            return (int)Math.Round(logicalWidth * scale);
        }

        private void UpdateMinimumSize()
        {
            var minimum = new Size(ToDevicePixels(400), ToDevicePixels(560));
            if (MinimumSize != minimum) MinimumSize = minimum;
            if (panel != null && panel.MinimumSize != minimum) panel.MinimumSize = minimum;
        }

        protected override void OnDpiChangedAfterParent(EventArgs e)
        {
            base.OnDpiChangedAfterParent(e);
            if (workspace != null) UpdateMinimumSize();
        }

        internal void SetStatus(string message, bool isError)
        {
            workspace.SetStatus(message, isError);
        }
        internal void SetBuildProgress(int percent,string stage,int seconds){workspace.SetBuildProgress(percent,stage,seconds);}

        protected override void Dispose(bool disposing)
        {
            if (disposing) ReleaseWorkspace();
            base.Dispose(disposing);
            if (disposing && ReferenceEquals(Current, this)) Current = null;
        }

        private void ReleaseWorkspace()
        {
            if (!workspaceDisposed && workspace != null)
            {
                workspace.OnWorkspaceClosing();
                workspaceDisposed = true;
                workspace.CloseRequested -= Close;
                if (panel != null) panel.ContentCloseQuery -= Panel_CloseQuery;
                elementHost.Child = null;
            }
        }

        [DllImport("user32.dll")]
        private static extern bool ReleaseCapture();
        [DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam);
    }
}
