using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 「对齐到管道」的点取工具：只读取一根活动模型管道及其点取位置，
    /// 不改任何几何与属性；读取走 <see cref="LineCoordinatePipeReader"/>，改动走应用修改流程。
    /// </summary>
    internal sealed class LineCoordinatePipeTool : DgnElementSetTool
    {
        private static LineCoordinatePipeTool active;
        private static bool oldSnap, oldLocate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive { get { return active != null; } }
        private LineCoordinatePipeTool() : base(0, 0) { }

        internal static void Begin()
        {
            if (active != null) { Enable(); Prompt(); return; }
            var created = new LineCoordinatePipeTool();
            oldSnap = AccuSnap.SnapEnabled; oldLocate = AccuSnap.LocateEnabled;
            active = created;
            try { created.InstallTool(); Enable(); }
            catch { active = null; Restore(); throw; }
        }

        internal static void End()
        {
            var tool = active; if (tool == null) return;
            active = null;
            try { tool.ExitTool(); }
            finally { Restore(); NotifyEnded(); }
        }

        protected override bool OnPostLocate(HitPath path, out string cantAcceptReason)
        {
            if (!base.OnPostLocate(path, out cantAcceptReason)) return false;
            var element = path == null ? null : path.GetHeadElement();
            if (element == null || element.DgnModelRef == null || element.DgnModelRef.IsDgnAttachment ||
                LocatedElement.IsReference(element))
            {
                cantAcceptReason = "请选择活动模型中的管道，不支持参考文件元素。";
                return false;
            }
            return true;
        }

        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if (!ReferenceEquals(active, this)) return true;
            var hit = DoLocate(ev, true, (int)ComponentMode.None);
            var element = hit == null ? null : hit.GetHeadElement();
            if (element == null || !element.IsValid) { Prompt(); return true; }
            var located = LocatedElement.From(element);
            located.ClickX = ev.Point.X; located.ClickY = ev.Point.Y; located.ClickZ = ev.Point.Z;
            // 先结束工具并恢复捕捉，再交给页面排队读取；不在点取回调中读 EC 或改几何。
            End();
            var picked = Picked; if (picked != null) picked(located);
            return true;
        }

        protected override void OnPostInstall() { base.OnPostInstall(); Prompt(); }
        protected override bool OnResetButton(DgnButtonEvent ev) { if (ReferenceEquals(active, this)) End(); return true; }
        protected override void OnRestartTool() { if (ReferenceEquals(active, this)) End(); }
        protected override void OnCleanup()
        {
            if (ReferenceEquals(active, this)) { active = null; Restore(); NotifyEnded(); }
            base.OnCleanup();
        }
        public override StatusInt OnElementModify(Element element) { return StatusInt.Error; }
        private static void Enable() { AccuSnap.SnapEnabled = true; AccuSnap.LocateEnabled = true; }
        private static void Restore() { AccuSnap.SnapEnabled = oldSnap; AccuSnap.LocateEnabled = oldLocate; }
        private static void Prompt() { NotificationManager.OutputPrompt("请选择一根 OpenPlant 管道，左键读取管底标高；右键结束点取。"); }
        private static void NotifyEnded() { var ended = Ended; if (ended != null) ended(); }
    }
}
