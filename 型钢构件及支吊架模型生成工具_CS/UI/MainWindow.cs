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
            ClientSize = new Size(360, 720);
            MinimumSize = new Size(320, 560);
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
