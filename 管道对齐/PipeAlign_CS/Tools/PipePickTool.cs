using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace PipeAlign
{
    /// <summary>
    /// 管道点取工具（开发指南 §13、§14、§15）。
    /// <para>
    /// 铁律：**工具回调里只报元素 ID，绝不读 EC**。实测在 <c>OnDataButton</c> 回调内部
    /// 访问 EC 实例会让 OPM 崩溃，而同样的调用在正常脚本上下文里完全正常。
    /// 因此读取由窗口在回调返回之后（<c>BeginInvoke</c> 排到消息队列）再做。
    /// </para>
    /// <para>
    /// 基准管与目标管共用本工具，靠 <see cref="PickPurpose"/> 区分：
    /// 基准管要求单选并立即进入下一阶段，目标管允许多选（连续左键 / Ctrl+Click / 框选）。
    /// </para>
    /// </summary>
    internal sealed class PipePickTool : DgnElementSetTool
    {
        internal enum PickPurpose
        {
            /// <summary>选基准管（开发指南 §14）。</summary>
            Reference = 0,

            /// <summary>选目标管（开发指南 §15）。</summary>
            Target = 1
        }

        private static PipePickTool _active;
        private static bool _savedSnapEnabled;
        private static bool _savedLocateEnabled;
        private static bool _hasSavedState;

        private readonly PickPurpose _purpose;
        private readonly Action<LocatedElement> _onPicked;
        private readonly Action _onEnded;

        private PipePickTool(PickPurpose purpose, Action<LocatedElement> onPicked, Action onEnded)
            : base(0, 0)
        {
            _purpose = purpose;
            _onPicked = onPicked;
            _onEnded = onEnded;
        }

        internal static bool IsActive { get { return _active != null; } }

        internal static PickPurpose? ActivePurpose
        {
            get { return _active == null ? (PickPurpose?)null : _active._purpose; }
        }

        /// <summary>
        /// 开始点取。<para>
        /// **幂等**：已经在点取中时只重新提示并沿用原回调，**不要"先结束再安装"** ——
        /// 那会先假发一次"已结束"（界面据此清空刚攒下的目标管），新装的实例还可能被上一个
        /// 实例的延迟清理带掉，表现就是"再点一次按钮后第一次点击被当成结束"。
        /// </para>
        /// </summary>
        internal static void Begin(PickPurpose purpose, Action<LocatedElement> onPicked, Action onEnded)
        {
            if (_active != null)
            {
                EnableLocate();
                Prompt(_active._purpose);
                return;
            }

            var tool = new PipePickTool(purpose, onPicked, onEnded);
            _savedSnapEnabled = AccuSnap.SnapEnabled;
            _savedLocateEnabled = AccuSnap.LocateEnabled;
            _hasSavedState = true;
            try
            {
                _active = tool;
                tool.InstallTool();
                EnableLocate();
            }
            catch
            {
                _active = null;
                RestoreSnapState();
                throw;
            }
        }

        internal static void End()
        {
            var tool = _active;
            if (tool == null) return;
            _active = null;
            try { tool.ExitTool(); }
            finally
            {
                RestoreSnapState();
                tool.NotifyEnded();
            }
        }

        /// <summary>
        /// 允许定位参考文件里的元素。参考元素在 MicroStation 里默认不可定位
        /// （点上去报"元素位于只读参考文件之中"），而本插件在基准/目标选择阶段都需要
        /// **读到并明确告诉用户**"该管道在参考文件里，不能改"，而不是让点击毫无反应。
        /// </summary>
        protected override RefLocateOption GetReferenceLocateOptions()
        {
            return RefLocateOption.TreatAsElement;
        }

        /// <summary>兜底：基类若仍以"只读参考文件"为由拒绝，这里只对参考元素放行。</summary>
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

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            Prompt(_purpose);
        }

        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            // DoLocate 用悬停的 AccuSnap 候选定位，并消耗这一次数据点。
            HitPath hit = DoLocate(ev, true, (int)ComponentMode.Innermost);
            var element = hit == null ? null : hit.GetHeadElement();
            if (element == null || !element.IsValid)
            {
                NotificationManager.OutputPrompt("没有定位到管道，请把光标悬停在管道上再单击左键。");
                return true;
            }

            // ⚠️ 只上报元素身份；EC 读取一律留到回调返回之后（见类注释）。
            var handler = _onPicked;
            if (handler != null) handler(LocatedElement.From(element));

            if (_purpose == PickPurpose.Reference)
            {
                // 基准管是单选，点中即结束本阶段。
                End();
            }
            return true;
        }

        /// <summary>点取工具永远不修改被定位的元素。</summary>
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        {
            return StatusInt.Error;
        }

        protected override bool OnResetButton(DgnButtonEvent ev)
        {
            End();
            return true;
        }

        protected override void OnRestartTool()
        {
            var replacement = new PipePickTool(_purpose, _onPicked, _onEnded);
            _active = replacement;
            replacement.InstallTool();
            EnableLocate();
        }

        protected override void OnCleanup()
        {
            if (ReferenceEquals(_active, this))
            {
                _active = null;
                RestoreSnapState();
                NotifyEnded();
            }
            base.OnCleanup();
        }

        private void NotifyEnded()
        {
            var handler = _onEnded;
            if (handler == null) return;
            try { handler(); }
            catch { }
        }

        private static void Prompt(PickPurpose purpose)
        {
            NotificationManager.OutputPrompt(purpose == PickPurpose.Reference
                ? "请点取一根水平直管作为基准管（左键点取，右键结束）。"
                : "请点取要移动的目标管，可连续左键多选；右键结束点取。");
        }

        private static void EnableLocate()
        {
            AccuSnap.SnapEnabled = true;
            AccuSnap.LocateEnabled = true;
        }

        private static void RestoreSnapState()
        {
            if (!_hasSavedState) return;
            _hasSavedState = false;
            AccuSnap.SnapEnabled = _savedSnapEnabled;
            AccuSnap.LocateEnabled = _savedLocateEnabled;
        }
    }
}
