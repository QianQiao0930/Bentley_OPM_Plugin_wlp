using System;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 点取箱体底部前侧中心，管理捕捉状态和右键取消。
    /// </summary>
    internal sealed class FireCabinetPlacementTool : DgnPrimitiveTool
    {
        private static FireCabinetPlacementTool active;
        private bool previousSnapEnabled;
        private bool previousLocateEnabled;

        private FireCabinetPlacementTool() : base(0, 0) { }
        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;
        internal static bool IsActive
        {
            get
            {
                return active != null;
            }
        }

        internal static void Begin()
        {
            if (active != null)
            {
                Prompt();
                return;
            }

            var tool = new FireCabinetPlacementTool
            {
                previousSnapEnabled = AccuSnap.SnapEnabled,
                previousLocateEnabled = AccuSnap.LocateEnabled
            };
            active = tool;
            try
            {
                tool.InstallTool();
                AccuSnap.SnapEnabled = true;
                AccuSnap.LocateEnabled = true;
            }
            catch
            {
                active = null;
                tool.RestoreSnap();
                throw;
            }
        }

        internal static void End()
        {
            FireCabinetPlacementTool tool = active;
            if (tool == null)
            {
                return;
            }
            active = null;
            try
            {
                tool.ExitTool();
            }
            finally
            {
                tool.RestoreSnap();
                Ended?.Invoke();
            }
        }

        private void RestoreSnap()
        {
            AccuSnap.SnapEnabled = previousSnapEnabled;
            AccuSnap.LocateEnabled = previousLocateEnabled;
        }

        private static void Prompt()
        {
            NotificationManager.OutputPrompt("左键点取箱体底部前侧中心；右键取消未确认预览。");
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            Prompt();
        }

        protected override bool OnDataButton(DgnButtonEvent buttonEvent)
        {
            Picked?.Invoke(buttonEvent.Point);
            return true;
        }

        protected override bool OnResetButton(DgnButtonEvent buttonEvent)
        {
            End();
            return true;
        }

        protected override void OnRestartTool()
        {
            End();
        }

        protected override void OnCleanup()
        {
            if (ReferenceEquals(active, this))
            {
                active = null;
                RestoreSnap();
                Ended?.Invoke();
            }

            base.OnCleanup();
        }
    }
}
