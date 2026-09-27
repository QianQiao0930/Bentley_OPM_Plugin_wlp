using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Read-only one-click element picker. Bentley objects never leave its callbacks.</summary>
    internal sealed class ComponentLocateTool : DgnElementSetTool
    {
        private static ComponentLocateTool active;
        private static bool savedSnapEnabled;
        private static bool savedLocateEnabled;
        private static bool hasSavedSnapState;

        private ComponentLocateTool() : base(0, 0) { }

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

        internal static event Action<LocatedElement> ElementPicked;
        internal static event Action SelectionEnded;
        internal static bool IsActive { get { return active != null; } }

        internal static void Begin()
        {
            End();
            var tool = new ComponentLocateTool();
            savedSnapEnabled = AccuSnap.SnapEnabled;
            savedLocateEnabled = AccuSnap.LocateEnabled;
            hasSavedSnapState = true;
            try
            {
                active = tool;
                tool.InstallTool();
                EnableLocate();
            }
            catch
            {
                active = null;
                RestoreSnapState();
                throw;
            }
        }

        internal static void End()
        {
            var tool = active;
            if (tool == null) return;
            active = null;
            try { tool.ExitTool(); }
            finally
            {
                RestoreSnapState();
                NotifyEnded();
            }
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("将光标悬停在构件上，左键读取特性；右键结束点取。");
        }

        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            // DoLocate uses the hovered AccuSnap candidate and consumes this data point.
            HitPath hit = DoLocate(ev, true, (int)ComponentMode.Innermost);
            var element = hit == null ? null : hit.GetHeadElement();
            if (element == null || !element.IsValid)
            {
                NotificationManager.OutputPrompt("没有定位到构件，请将光标悬停在构件上后单击左键。");
                return true;
            }
            var handler = ElementPicked;
            if (handler != null) handler(LocatedElement.From(element));
            return true;
        }

        public override Bentley.DgnPlatformNET.StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        {
            // The query tool never modifies a located element.
            return Bentley.DgnPlatformNET.StatusInt.Error;
        }

        protected override bool OnResetButton(DgnButtonEvent ev)
        {
            End();
            return true;
        }

        protected override void OnRestartTool()
        {
            var replacement = new ComponentLocateTool();
            active = replacement;
            replacement.InstallTool();
            EnableLocate();
        }

        protected override void OnCleanup()
        {
            if (ReferenceEquals(active, this))
            {
                active = null;
                RestoreSnapState();
                NotifyEnded();
            }
            base.OnCleanup();
        }

        private static void EnableLocate()
        {
            AccuSnap.SnapEnabled = true;
            AccuSnap.LocateEnabled = true;
        }

        private static void RestoreSnapState()
        {
            if (!hasSavedSnapState) return;
            hasSavedSnapState = false;
            AccuSnap.SnapEnabled = savedSnapEnabled;
            AccuSnap.LocateEnabled = savedLocateEnabled;
        }

        private static void NotifyEnded()
        {
            var handler = SelectionEnded;
            if (handler != null) handler();
        }
    }
}


