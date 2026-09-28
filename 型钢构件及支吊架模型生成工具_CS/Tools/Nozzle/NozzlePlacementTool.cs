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
        /// <summary>点取工具当前是否已安装（页面据此避免"重复安装"，那会白丢一次状态）。</summary>
        internal static bool IsActive { get { return active!=null; } }
        internal static void Begin()
        {
            if(active!=null)
            {
                // 已经在点取中：**只重新提示一次，不要"结束再安装"**。
                // 结束再安装会在 Begin 内部先触发一次 Ended（页面据此清掉基点与预览、提示
                // "已结束点取"），而紧接着安装的新实例还可能被上一个实例的延迟清理
                // （OnCleanup）带掉 —— 表现就是"再次点「开始点取」后第一次点击被当成结束，
                // 得点两次才真正进入点取"。管夹类（PipeClampLocateTool）与构件特性查询
                // （ComponentLocateTool）用的是同一套幂等写法。
                ShowPrompt();
                return;
            }
            var tool=new NozzlePlacementTool();active=tool;
            try { tool.InstallTool(); }
            catch { active=null;throw; }
        }
        private static void ShowPrompt()
        { NotificationManager.OutputPrompt("左键点取管口基点并生成预览；右键结束并取消未确认预览。"); }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try { tool.ExitTool(); }
            finally { var ended=Ended;if(ended!=null)ended(); }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            ShowPrompt();
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
