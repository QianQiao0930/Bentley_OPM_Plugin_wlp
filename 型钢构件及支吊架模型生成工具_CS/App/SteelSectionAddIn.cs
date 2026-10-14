using System;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    [AddInAttribute(MdlTaskID = "SteelSectionProbe")]
    public sealed class SteelSectionAddIn : AddIn
    {
        internal static SteelSectionAddIn Instance;

        private SteelSectionAddIn(IntPtr descriptor) : base(descriptor)
        {
            Instance = this;
            UnloadingEvent += OnUnloading;
        }

        protected override int Run(string[] args) { return 0; }

        private void OnUnloading(AddIn sender, AddIn.UnloadingEventArgs eventArgs)
        {
            try { MainWindow.UnloadWindow(); }
            catch (Exception ex)
            {
                eventArgs.ResponseCode = AddIn.UnloadingEventArgs.Response.UnloadAbort;
                MainWindow.Current?.SetStatus("卸载前清理失败，请重试：" + ex.Message, true);
            }
        }
    }
}
