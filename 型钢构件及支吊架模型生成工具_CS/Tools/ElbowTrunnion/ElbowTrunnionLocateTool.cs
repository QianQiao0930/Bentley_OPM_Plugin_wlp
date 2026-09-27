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
        internal static event Action<ulong,int,double,double> Picked;
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
            ulong id=(ulong)element.ElementId;
            int view=ev.ViewNumber;
            var point=ev.ViewPoint;
            End();
            var picked=Picked; if (picked!=null) picked(id,view,point.X,point.Y);
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



