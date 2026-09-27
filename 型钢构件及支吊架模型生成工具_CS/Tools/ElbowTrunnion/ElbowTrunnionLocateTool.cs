using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class ElbowTrunnionLocateTool : DgnElementSetTool
    {
        private static ElbowTrunnionLocateTool active;
        private static bool oldSnap,oldLocate;
        private ElbowTrunnionLocateTool() : base(0,0) { }

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
        internal static event Action<LocatedElement,int,double,double> Picked;
        internal static event Action Ended;
        internal static void Begin()
        {
            End();
            var tool=new ElbowTrunnionLocateTool();
            oldSnap=AccuSnap.SnapEnabled;
            oldLocate=AccuSnap.LocateEnabled;
            active=tool;
            try
            {
                tool.InstallTool();
                AccuSnap.SnapEnabled=true;
                AccuSnap.LocateEnabled=true;
            }
            catch
            {
                active=null;
                AccuSnap.SnapEnabled=oldSnap;
                AccuSnap.LocateEnabled=oldLocate;
                throw;
            }
        }
        internal static void End()
        {
            var tool=active;
            if (tool==null) return;
            active=null;
            try { tool.ExitTool(); }
            finally
            {
                AccuSnap.SnapEnabled=oldSnap;
                AccuSnap.LocateEnabled=oldLocate;
                var ended=Ended; if (ended!=null) ended();
            }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("悬停定位 90° 弯头，左键点选；右键结束。");
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var hit=DoLocate(ev,true,(int)ComponentMode.None);
            var element=hit==null ? null : hit.GetHeadElement();
            if (element==null || !element.IsValid)
            {
                NotificationManager.OutputPrompt("未定位到弯头，请重新点选。");
                return true;
            }
            var located=LocatedElement.From(element);
            int view=ev.ViewNumber;
            var point=ev.ViewPoint;
            End();
            var picked=Picked; if (picked!=null) picked(located,view,point.X,point.Y);
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev) { End(); return true; }
        protected override void OnRestartTool() { End(); }
        protected override void OnCleanup()
        {
            if (ReferenceEquals(active,this))
            {
                active=null;
                AccuSnap.SnapEnabled=oldSnap;
                AccuSnap.LocateEnabled=oldLocate;
                var ended=Ended; if (ended!=null) ended();
            }
            base.OnCleanup();
        }
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        {
            return StatusInt.Error;
        }
    }
}



