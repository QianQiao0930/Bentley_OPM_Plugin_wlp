using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 管夹类功能共用的点选工具：悬停定位管道 / 直线 / 多段线，左键上报元素 ID 与点击点。
    /// 五种管夹共用初始定位工具；A1 定位后另用工具调整开口方向。
    /// </summary>
    internal sealed class PipeClampLocateTool : DgnElementSetTool
    {
        private static PipeClampLocateTool active;
        private static bool oldSnap,oldLocate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        /// <summary>点取工具当前是否已安装（页面据此避免"重复安装"，那会白丢一次状态）。</summary>
        internal static bool IsActive { get { return active!=null; } }

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
            var tool=active;
            if(tool!=null)
            {
                // 已经在点取中：**只重新确保捕捉/定位可用，不要"结束再安装"**。
                // 结束再安装会在 Begin 内部先触发一次 Ended（页面据此清空选择并提示
                // "已结束点取"），而紧接着安装的新实例还可能被上一个实例的延迟清理
                // （OnCleanup）带掉并再次触发 Ended —— 表现就是"再点一次开始点取后，
                // 第一次点击被当成结束，得再点一次才真正进入点取"。
                // 另外这里**不能重新记录 oldSnap/oldLocate**，否则会把"被强制打开"的状态
                // 当成用户的原始状态保存，退出时恢复不回去。
                AccuSnap.SnapEnabled=true; AccuSnap.LocateEnabled=true;
                return;
            }
            var created=new PipeClampLocateTool();
            oldSnap=AccuSnap.SnapEnabled; oldLocate=AccuSnap.LocateEnabled;
            active=created;
            try
            {
                created.InstallTool();
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
        /// <summary>
        /// 交接给下一个工具（如 A1 方向工具）时"静默退役"：只清静态状态并恢复捕捉/定位，
        /// **不调 ExitTool、不发 Ended**。ExitTool 会向状态机挂起一个"退出当前工具"，
        /// 该退出在下一个原生输入事件才结算 —— 那时"当前工具"已经是紧随其后安装的新工具，
        /// 新工具会被误杀并触发一次伪 Ended（同 2906eca 竞态，A1 方向调整刚装上就被
        /// "已取消"即是此坑）。本实例的收尾由新工具 InstallTool 引发的工具切换完成，
        /// 其 OnCleanup 因 active!=this 而静默。
        /// </summary>
        internal static void RetireForHandoff()
        {
            var tool=active; if(tool==null) return;
            active=null;
            AccuSnap.SnapEnabled=oldSnap; AccuSnap.LocateEnabled=oldLocate;
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
