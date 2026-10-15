using System;
using System.Collections.Generic;
using Size = System.Drawing.Size;
using System.Windows;
using System.Windows.Controls;
using Forms = System.Windows.Forms;

namespace Bentley.MstnPlatformNET.WinForms
{
    internal class Adapter : Forms.Form { public bool UseHostSize { get; set; } }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class AddInAttribute : Attribute { public string MdlTaskID { get; set; } }
    public class AddIn
    {
        public sealed class UnloadingEventArgs : EventArgs
        {
            public enum Response { UnloadProceed, UnloadAbort }
            public Response ResponseCode;
        }
        public delegate void UnloadingEventHandler(AddIn sender, UnloadingEventArgs args);
        public event UnloadingEventHandler UnloadingEvent;
        protected AddIn(IntPtr descriptor) { }
        protected virtual int Run(string[] args) { return 0; }
        internal UnloadingEventArgs.Response TryUnload()
        { var args = new UnloadingEventArgs(); UnloadingEvent?.Invoke(this, args); return args.ResponseCode; }
    }
}
namespace Bentley.Windowing
{
    internal enum DockLocation { Left, Right }
    internal enum ContentCloseAction { Disabled, Hide, Dispose }
    internal sealed class ContentCloseEventArgs : EventArgs
    { public bool UserAction = true; public ContentCloseAction CloseAction = ContentCloseAction.Dispose; }
    internal sealed class FakeZone { internal int FocusCount; public void SetFocus() { FocusCount++; } }
    internal sealed class WindowContent
    {
        internal Forms.Control Content;
        internal bool Visible;
        internal int Expands;
        public bool CanDockVertically, CanDockHorizontally, CanDockInCenter, CanAutoHide, Closeable;
        public Forms.FormBorderStyle FormBorderStyle;
        public Forms.Form FloatingHostForm { get; set; }
        public Size MinimumSize;
        public bool Unpinned;
        public FakeZone Zone = new FakeZone();
        public event EventHandler<ContentCloseEventArgs> ContentCloseQuery;
        public void Show() { Visible = true; }
        public void Hide() { Visible = false; }
        public void AutoHideExpand() { Expands++; }
        public void AutoHideUnpin() { Unpinned = true; }
        internal ContentCloseAction NativeClose(bool user = true)
        {
            var args = new ContentCloseEventArgs { UserAction = user };
            ContentCloseQuery?.Invoke(this, args);
            if (args.CloseAction == ContentCloseAction.Hide) Hide();
            if (args.CloseAction == ContentCloseAction.Dispose) Content.Dispose();
            return args.CloseAction;
        }
    }
    internal sealed class WindowManager
    {
        internal static readonly WindowManager Instance = new WindowManager();
        internal int Registrations;
        internal int Removals;
        internal WindowContent Panel;
        internal object Id;
        internal DockLocation Location;
        public static WindowManager GetForMicroStation() { return Instance; }
        public void RemoveContent(WindowContent content) { Removals++; content.Hide(); content.Content.Dispose(); }
        public WindowContent DockPanel(Forms.Control control, object id, string title, DockLocation location, Size horizontal, Size vertical)
        {
            if (((Forms.Form)control).TopLevel) throw new Exception("不能把独立顶层窗口交给停靠宿主");
            Registrations++; Id = id; Location = location;
            return Panel = new WindowContent { Content = control };
        }
    }
}
namespace SteelSectionProbe
{
    internal static class LicenseService
    {
        internal static bool IsLicensingEnabled = true, IsActivated = true;
        internal static bool IsTrial { get { return false; } }
        internal static string StatusMessage { get { return "测试授权已到期"; } }
    }
    internal static class HomePreferences
    { internal static int Saves; internal static void Save() { Saves++; } internal static void RecordUsage(string id) { } }
    internal sealed class HomePage : UserControl
    {
        internal event Action<string> FeatureRequested;
        internal event Action<string, bool> StatusRequested;
        internal event Action<bool> SelectionChanged;
        internal void Refresh() { }
        internal void RefreshLicenseStatus() { }
        internal double MeasureRowWidth() { return 0; }
        internal double MeasureChromeWidth() { return 0; }
        internal void EnterSelected() { FeatureRequested?.Invoke("steel-sections"); StatusRequested?.Invoke("测试进入", false); SelectionChanged?.Invoke(true); }
    }
    internal class TestPage : UserControl, IWorkspacePage
    {
        internal static readonly Dictionary<string, TestPage> All = new Dictionary<string, TestPage>();
        internal int Activated, Deactivated, Closed;
        internal bool FailCleanup;
        internal bool FailClose;
        internal TestPage(string id) { PageId = id; All[id] = this; }
        public string PageId { get; private set; }
        public string PageTitle { get { return PageId; } }
        public string PageSubtitle { get { return "测试"; } }
        public FrameworkElement View { get { return this; } }
        public void OnActivated() { Activated++; }
        public void OnDeactivated() { if (FailCleanup) throw new Exception("预览清理失败"); Deactivated++; }
        public void OnWorkspaceClosing() { if (FailClose) throw new Exception("清理失败"); Closed++; }
    }
}
