using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 管夹类功能共用的点选工具：悬停定位管道 / 直线 / 多段线，左键上报元素 ID 与点击点。
    /// 四种管夹（A2 / E1 / K1 / T4）操作方式一致，因此共用同一个工具。
    /// </summary>
    internal sealed class PipeClampLocateTool : DgnElementSetTool
    {
        private static PipeClampLocateTool active;
        private static bool oldSnap,oldLocate;
        internal static event Action<ulong,double,double,double> Picked;
        internal static event Action Ended;

        private PipeClampLocateTool() : base(0,0) { }

        internal static void Begin()
        {
            End();
            var tool=new PipeClampLocateTool();
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
            var tool=active; if(tool==null) return;
            active=null;
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
                "悬停选择管道、直线或多段线，左键在点击处生成管夹预览；右键退出。");
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var hit=DoLocate(ev,true,(int)ComponentMode.None);
            var element=hit==null?null:hit.GetHeadElement();
            if(element==null || !element.IsValid)
            { NotificationManager.OutputPrompt("未找到管道或直线，请重新点取。"); return true; }
            var picked=Picked;
            if(picked!=null) picked((ulong)element.ElementId,ev.Point.X,ev.Point.Y,ev.Point.Z);
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
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        { return StatusInt.Error; }
    }
}
