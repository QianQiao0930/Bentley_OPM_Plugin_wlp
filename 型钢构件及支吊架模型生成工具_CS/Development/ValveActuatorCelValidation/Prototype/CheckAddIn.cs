using System;
using Bentley.MstnPlatformNET;

namespace ValveActuatorCelCheck
{
    [AddInAttribute(MdlTaskID = "ValveActuatorCelCheckV2")]
    public sealed class CheckAddIn : AddIn
    {
        private CheckAddIn(IntPtr descriptor) : base(descriptor)
        {
            UnloadingEvent += (sender, args) =>
            {
                if (!Commands.HasNativeLeases || (args.UnloadKind != AddIn.UnloadReasons.Command
                    && args.UnloadKind != AddIn.UnloadReasons.LibraryUnload)) return;
                args.ResponseCode = AddIn.UnloadingEventArgs.Response.UnloadAbort;
                Bentley.DgnPlatformNET.NotificationManager.OutputPrompt("执行机构试验已提交原生几何句柄；请退出 OPM 释放验证资源，不要单独卸载该验证 DLL。");
            };
        }
        protected override int Run(string[] args) { return 0; }
    }
}
