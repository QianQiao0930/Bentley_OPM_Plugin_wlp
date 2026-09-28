using System;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 点取混凝土表面上锚板背面中心点的交互工具。只上报点取坐标，
    /// 预览元素由 <see cref="G2AnchorPreviewSession"/> 持有，因此右键退出不会残留元素。
    /// </summary>
    internal sealed class G2AnchorLocateTool : DgnPrimitiveTool
    {
        private static G2AnchorLocateTool active;
        private static bool oldSnap,oldLocate;
        private G2AnchorLocateTool() : base(0,0) { }

        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;

        internal static void Begin()
        {
            End();
            var tool=new G2AnchorLocateTool();
            oldSnap=AccuSnap.SnapEnabled; oldLocate=AccuSnap.LocateEnabled;
            active=tool;
            try
            {
                tool.InstallTool();
                AccuSnap.SnapEnabled=true; AccuSnap.LocateEnabled=true;
            }
            catch { active=null; AccuSnap.SnapEnabled=oldSnap; AccuSnap.LocateEnabled=oldLocate; throw; }
        }
        internal static void End()
        {
            var tool=active; if(tool==null) return; active=null;
            try { tool.ExitTool(); }
            finally
            {
                AccuSnap.SnapEnabled=oldSnap; AccuSnap.LocateEnabled=oldLocate;
                var ended=Ended; if(ended!=null) ended();
            }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt(
                "点取混凝土表面上锚板背面的中心点：锚栓沿安装面外法向伸入。"+
                "点取后可改子项 / 间距 S / 安装面 / 朝向，预览会自动重建；点【确定生成】保留，右键放弃。");
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var picked=Picked; if(picked!=null) picked(ev.Point);
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev) { End(); return true; }
        protected override void OnRestartTool() { End(); }
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this))
            {
                active=null;
                AccuSnap.SnapEnabled=oldSnap; AccuSnap.LocateEnabled=oldLocate;
                var ended=Ended; if(ended!=null) ended();
            }
            base.OnCleanup();
        }
    }
}
