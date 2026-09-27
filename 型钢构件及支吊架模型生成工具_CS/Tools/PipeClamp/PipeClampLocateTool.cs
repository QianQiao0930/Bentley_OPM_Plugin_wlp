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
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;

        private PipeClampLocateTool() : base(0,0) { }

        /// <summary>
        /// 允许定位参考文件（reference）里的元素。MicroStation 默认不把参考元素交给元素集合工具，
        /// 点上去会报"元素位于只读参考文件之中"；本工具只读取几何与 EC 属性、从不修改，
        /// 因此按"把参考元素当成普通元素"来定位。
        /// </summary>
        protected override RefLocateOption GetReferenceLocateOptions()
        {
            return RefLocateOption.TreatAsElement;
        }

        /// <summary>
        /// 兜底：若基类仍以"只读参考文件"为由拒绝，这里只对参考元素放行，其余情况维持基类判断。
        /// </summary>
        protected override bool OnPostLocate(HitPath path, out string cantAcceptReason)
        {
            if (base.OnPostLocate(path, out cantAcceptReason)) return true;
            var located = path == null ? null : path.GetHeadElement();
            if (LocatedElement.IsReference(located))
            {
                cantAcceptReason = "";
                return true;
            }
            return false;
        }

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
            if(picked!=null)
            {
                var located=LocatedElement.From(element);
                located.ClickX=ev.Point.X;
                located.ClickY=ev.Point.Y;
                located.ClickZ=ev.Point.Z;
                picked(located);
            }
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
