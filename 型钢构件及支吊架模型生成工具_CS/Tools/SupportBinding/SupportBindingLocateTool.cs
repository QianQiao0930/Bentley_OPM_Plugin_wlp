using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class SupportBindingLocateTool : ProbeLocateTool
    {
        private static SupportBindingLocateTool active;
        private static bool oldSnap, oldLocate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive { get { return active != null; } }
        private SupportBindingLocateTool() : base(0, 0) { }
        internal static void Begin()
        {
            if (active != null) { active.PrepareForPicking("重复开始点取"); Enable(); Prompt(); return; }
            var tool = new SupportBindingLocateTool();
            oldSnap = AccuSnap.SnapEnabled; oldLocate = AccuSnap.LocateEnabled;
            active = tool;
            try { tool.InstallTool(); Enable(); }
            catch { active = null; Restore(); throw; }
        }
        internal static void End()
        {
            var tool = active; if (tool == null) return;
            active = null;
            try { tool.ExitTool(); }
            finally { Restore(); Ended?.Invoke(); }
        }
        protected override bool OnPostLocate(HitPath path, out string cantAcceptReason)
        {
            if (!base.OnPostLocate(path, out cantAcceptReason)) return false;
            var element = path == null ? null : path.GetHeadElement();
            if (element == null || element.IsComplexComponent || element.ParentElement != null ||
                element.DgnModelRef.IsDgnAttachment || LocatedElement.IsReference(element))
            {
                cantAcceptReason = "请选择活动模型中的支架整组，不支持参考文件或块内子构件。";
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
            // 回调只上报模型和ID；EC读取延后到页面Dispatcher。
            Picked?.Invoke(LocatedElement.From(element));
            return true;
        }
        public override StatusInt OnElementModify(Element element) { return StatusInt.Error; }
        protected override void OnPostInstall() { base.OnPostInstall(); Prompt(); }
        protected override bool OnResetButton(DgnButtonEvent ev) { if (ReferenceEquals(active, this)) End(); return true; }
        protected override void OnRestartTool() { if (ReferenceEquals(active, this)) End(); }
        protected override void OnCleanup()
        {
            if (ReferenceEquals(active, this)) { active = null; Restore(); Ended?.Invoke(); }
            base.OnCleanup();
        }
        private static void Enable() { AccuSnap.SnapEnabled = true; AccuSnap.LocateEnabled = true; }
        private static void Restore() { AccuSnap.SnapEnabled = oldSnap; AccuSnap.LocateEnabled = oldLocate; }
        private static void Prompt() { NotificationManager.OutputPrompt("按页面当前步骤点取管夹或承重支架整组；右键结束点取。"); }
    }
}
