using System;
using System.Drawing;
using System.Windows.Forms;
using System.Windows.Forms.Integration;
using Bentley.MstnPlatformNET.WinForms;

namespace SteelSectionProbe
{
    /// <summary>
    /// Thin Bentley/WinForms host.  All visible application UI lives in the
    /// WPF WorkspaceView; this class only owns the native top-level lifetime.
    /// </summary>
    internal sealed class MainWindow : Adapter
    {
        private readonly ElementHost elementHost = new ElementHost();
        private readonly WorkspaceView workspace;

        private bool homeShell;
        private int moduleHeightLogical=720;
        internal static MainWindow Current;
        internal SteelSectionPage SteelSections { get { return workspace.SteelSections; } }

        internal static void ShowWindow()
        {
            if (Current == null || Current.IsDisposed) Current = new MainWindow();
            if (!Current.Visible) Current.Show();
            Current.Activate();
        }

        private MainWindow()
        {
            Text = "型钢构件及支吊架模型生成工具";
            ClientSize = new Size(840, 720);
            MinimumSize = new Size(560, 560);
            FormBorderStyle = FormBorderStyle.Sizable;
            MaximizeBox = false;
            AutoScaleMode = AutoScaleMode.Dpi;
            BackColor = Color.FromArgb(245, 246, 248);
            DoubleBuffered = true;

            AttachAsTopLevelForm(SteelSectionAddIn.Instance, true);
            NETDockable = false;

            workspace = new WorkspaceView();
            workspace.CloseRequested += Close;
            elementHost.Dock = DockStyle.Fill;
            elementHost.BackColor = BackColor;
            elementHost.Child = workspace;
            Controls.Add(elementHost);

            // 构造期还拿不到 WPF 的 DPI 缩放（ElementHost 尚未连上 PresentationSource），
            // 所以"设计尺寸 → 设备像素"这一步挪到窗口真正显示之后再做一次；
            // 否则 150% 缩放下首次打开会把首页按 1:1 布局成窄版（卡片只剩一列）。
            Shown += delegate
            {
                int min = ToDevicePixels(400);
                MinimumSize = new Size(min, min);
                SetHomeLayout(true);
                // 首次显示后再按真实可视树校准首页宽度（构造期拿不到 DPI，也还没布局）。
                workspace.ScheduleHomeWidthCheck();
            };

            FormClosed += OnFormClosed;
        }

        internal void BeginTitleDrag()
        {
            Capture=false;
            var message=Message.Create(Handle,0xA1,new IntPtr(2),IntPtr.Zero);
            WndProc(ref message);
        }
        internal void MinimizeFromHome(){WindowState=FormWindowState.Minimized;}

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

        /// <summary>首页和已改造的模块/工具页使用400×880 DIP窗口壳；其余模块保留原560 DIP宽与用户调整的高度。</summary>
        internal void SetHomeLayout(bool home, bool prototypeModule = false)
        {
            if(home || prototypeModule)
            {
                if(!homeShell){moduleHeightLogical=Math.Max(560,(int)Math.Round(ClientSize.Height/(double)ToDevicePixels(100)*100));}
                homeShell=true;
                FormBorderStyle=FormBorderStyle.None;
                MinimumSize=new Size(ToDevicePixels(400),ToDevicePixels(880));
                MaximumSize=MinimumSize;
                ClientSize=MinimumSize;
                var path=new System.Drawing.Drawing2D.GraphicsPath();
                int radius=ToDevicePixels(8)*2;
                path.AddArc(0,0,radius,radius,180,90);path.AddArc(ClientSize.Width-radius,0,radius,radius,270,90);
                path.AddArc(ClientSize.Width-radius,ClientSize.Height-radius,radius,radius,0,90);path.AddArc(0,ClientSize.Height-radius,radius,radius,90,90);path.CloseFigure();
                var previous=Region;Region=new Region(path);path.Dispose();previous?.Dispose();
            }
            else
            {
                homeShell=false;
                var previous=Region;Region=null;previous?.Dispose();
                FormBorderStyle=FormBorderStyle.Sizable;
                MaximumSize=Size.Empty;
                MinimumSize=new Size(ToDevicePixels(560),ToDevicePixels(560));
                ClientSize=new Size(ToDevicePixels(560),ToDevicePixels(moduleHeightLogical));
            }
        }

        /// <summary>保留现有校准调用接口；固定尺寸首页不再随卡片扩大。</summary>
        internal bool ApplyHomeWidth(double measuredLogicalWidth)
        {
            return false; // 原型首页固定400 DIP，不再由卡片测量自动扩大窗口。
        }

        /// <summary>逻辑宽度（96 dpi 基准）→ 当前 DPI 的设备像素。取不到 DPI 时按 1:1 处理。</summary>
        private int ToDevicePixels(int logicalWidth)
        {
            double scale = 1.0;
            try
            {
                if (elementHost.Child != null)
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

        internal void SetStatus(string message, bool isError)
        {
            workspace.SetStatus(message, isError);
        }
        internal void SetBuildProgress(int percent,string stage,int seconds){workspace.SetBuildProgress(percent,stage,seconds);}

        private void OnFormClosed(object sender, FormClosedEventArgs e)
        {
            workspace.OnWorkspaceClosing();
            elementHost.Child = null;
            Current = null;
        }
    }
}
