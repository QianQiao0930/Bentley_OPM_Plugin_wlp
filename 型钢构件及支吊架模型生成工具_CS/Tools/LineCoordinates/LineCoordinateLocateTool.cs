using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class LineCoordinateLocateTool : ProbeLocateTool
    {
        private static LineCoordinateLocateTool active;
        private static bool oldSnap, oldLocate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive { get { return active != null; } }
        private LineCoordinateLocateTool() : base(0, 0) { }

        internal static void Begin()
        {
            if (active != null) { active.PrepareForPicking("重复开始点取"); Enable(); Prompt(); return; }
            var created = new LineCoordinateLocateTool();
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
            if (element == null || !(element is LineElement) || element.IsComplexComponent ||
                element.ParentElement != null || element.DgnModelRef.IsDgnAttachment || LocatedElement.IsReference(element))
            {
                cantAcceptReason = "请选择活动模型中的独立直线段，不支持折线、参考文件或块内子线段。";
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
            // 先结束工具并恢复捕捉，再交给页面排队读取；不在点取回调中改几何。
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
        private static void Prompt() { NotificationManager.OutputPrompt("请选择一条独立直线段，左键读取两端坐标；右键结束点取。"); }
        private static void NotifyEnded() { var ended = Ended; if (ended != null) ended(); }
    }
}
