using System;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class NozzlePlacementTool : DgnPrimitiveTool
    {
        private static NozzlePlacementTool active;
        private NozzlePlacementTool() : base(0,0) { }
        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;
        internal static void Begin()
        {
            End();var tool=new NozzlePlacementTool();active=tool;
            try { tool.InstallTool(); }
            catch { active=null;throw; }
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try { tool.ExitTool(); }
            finally { var ended=Ended;if(ended!=null)ended(); }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("左键点取管口基点并生成预览；右键结束并取消未确认预览。");
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        { var picked=Picked;if(picked!=null)picked(ev.Point);return true; }
        protected override bool OnResetButton(DgnButtonEvent ev) { End();return true; }
        protected override void OnRestartTool() { End(); }
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this))
            { active=null;var ended=Ended;if(ended!=null)ended(); }
            base.OnCleanup();
        }
    }
}
