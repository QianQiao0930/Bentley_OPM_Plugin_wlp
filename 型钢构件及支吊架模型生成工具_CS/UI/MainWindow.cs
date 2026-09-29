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
                int min = ToDevicePixels(560);
                MinimumSize = new Size(min, min);
                SetHomeLayout(true);
                // 首次显示后再按真实可视树校准首页宽度（构造期拿不到 DPI，也还没布局）。
                workspace.ScheduleHomeWidthCheck();
            };

            FormClosed += OnFormClosed;
        }

        internal void ShowSteelSectionsPage()
        {
            workspace.ShowSteelSectionsPage();
        }

        internal void ShowHome()
        {
            workspace.ShowHome();
        }

        /// <summary>
        /// 首页与功能页**同为 560 逻辑宽**（2026-09-28 起：卡片收窄到 240 后两列放得下，
        /// 首页不再需要比功能页宽）。数字是 <b>96 dpi 下的逻辑宽度</b>，会按实际 DPI 换算成设备像素。
        /// <para>
        /// 兜底值之外还有一层保险：<see cref="WorkspaceView.ScheduleHomeWidthCheck"/> 会按真实可视树
        /// 实测"两列卡片 + 页边距 + 滚动条"需要的宽度，再回调 <see cref="ApplyHomeWidth"/> 校准
        /// （实测 552 → 被下限夹到 560）。万一以后卡片改宽，窗口会自动跟着加宽而不是掉成单列。
        /// </para>
        /// <para>
        /// ⚠️ 设计尺寸不能直接写进 <see cref="ClientSize"/> —— 那是以<b>设备像素</b>为单位的，
        /// 而本窗体的 <c>AutoScaleMode = Dpi</c> 会在高 DPI 下把窗体尺寸再乘一次缩放系数，
        /// 两者打架就会出现"返回首页后卡片宽度时宽时窄、和刚打开时不一样"。
        /// 因此统一按 WPF 子控件的真实 DPI 换算（<see cref="ToDevicePixels"/>）。
        /// </para>
        /// </summary>
        internal void SetHomeLayout(bool home)
        {
            homeLayout = home;
            int width = ToDevicePixels(home ? homeWidthLogical : 560);
            if(ClientSize.Width!=width)ClientSize=new Size(width,ClientSize.Height);
        }

        /// <summary>
        /// 首页宽度兜底值（逻辑宽）。**与功能页同宽 = 560**：卡片改成 240 宽后两列只需
        /// 24 页边距 + 2×(240+12) + 16 滚动条开销 + 8 余量 = 552 ≤ 560，正好放得下，
        /// 所以首页不再比功能页宽，首帧也不会出现"先宽后窄"的跳动。
        /// </summary>
        private const int HomeWidthFallback = 560;

        /// <summary>当前首页宽度（逻辑宽），首帧用兜底值，之后由实测校准。</summary>
        private int homeWidthLogical = HomeWidthFallback;

        /// <summary>当前是否处于首页布局（校准回调只在首页生效，避免影响功能页）。</summary>
        private bool homeLayout = true;

        /// <summary>
        /// 由 WPF 侧实测得出的首页宽度（逻辑宽）回调过来。宽度没变或不在首页时返回 false（表示已收敛）。
        /// 只做"恰好容纳两列"的校准，不做任何会影响功能页的改动。
        /// </summary>
        internal bool ApplyHomeWidth(double measuredLogicalWidth)
        {
            if (!homeLayout) return false;
            int width = (int)Math.Ceiling(measuredLogicalWidth);
            if (width < 560) width = 560;
            if (Math.Abs(width - homeWidthLogical) < 2) return false;   // 已收敛，别再动窗口
            homeWidthLogical = width;
            int device = ToDevicePixels(width);
            if (ClientSize.Width != device) ClientSize = new Size(device, ClientSize.Height);
            return true;
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

        private void OnFormClosed(object sender, FormClosedEventArgs e)
        {
            workspace.OnWorkspaceClosing();
            elementHost.Child = null;
            Current = null;
        }
    }
}
