using System;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 工程绘图类功能共用的单点定位工具：左键回调模型坐标，右键结束。
    /// 同一时刻只允许一个实例；重复开始只刷新提示，不重复安装。
    /// </summary>
    internal sealed class EngineeringPlacementTool : DgnPrimitiveTool
    {
        private static EngineeringPlacementTool active;
        private static string prompt = "左键点取放置基点。";
        private bool oldSnap;
        private bool oldLocate;

        private EngineeringPlacementTool()
            : base(0, 0)
        {
        }

        internal static event Action<DPoint3d> Picked;

        internal static event Action Ended;

        internal static bool IsActive
        {
            get { return active != null; }
        }

        internal static void Begin(string text)
        {
            prompt = string.IsNullOrEmpty(text) ? "左键点取放置基点。" : text;
            if (active != null)
            {
                AccuSnap.SnapEnabled = true;
                AccuSnap.LocateEnabled = true;
                OutputPrompt();
                return;
            }

            var tool = new EngineeringPlacementTool
            {
                oldSnap = AccuSnap.SnapEnabled,
                oldLocate = AccuSnap.LocateEnabled
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
            var tool = active;
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
                var ended = Ended;
                if (ended != null)
                {
                    ended();
                }
            }
        }

        private void RestoreSnap()
        {
            AccuSnap.SnapEnabled = oldSnap;
            AccuSnap.LocateEnabled = oldLocate;
        }

        private static void OutputPrompt()
        {
            NotificationManager.OutputPrompt(prompt + "右键取消未确认预览。");
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            OutputPrompt();
        }

        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if (!ReferenceEquals(active, this))
            {
                return true;
            }

            var picked = Picked;
            if (picked != null)
            {
                picked(ev.Point);
            }

            return true;
        }

        protected override bool OnResetButton(DgnButtonEvent ev)
        {
            if (ReferenceEquals(active, this))
            {
                End();
            }

            return true;
        }

        protected override void OnRestartTool()
        {
            if (ReferenceEquals(active, this))
            {
                End();
            }
        }

        protected override void OnCleanup()
        {
            if (ReferenceEquals(active, this))
            {
                active = null;
                RestoreSnap();
                var ended = Ended;
                if (ended != null)
                {
                    ended();
                }
            }

            base.OnCleanup();
        }
    }
}
