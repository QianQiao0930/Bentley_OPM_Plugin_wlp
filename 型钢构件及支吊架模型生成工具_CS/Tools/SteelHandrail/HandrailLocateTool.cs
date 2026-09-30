using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class HandrailLocateTool:DgnElementSetTool
    {
        private static HandrailLocateTool active;
        private static bool snap,locate;
        internal static bool IsActive {get{return active!=null;}}
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        private HandrailLocateTool():base(0,0){}
        protected override RefLocateOption GetReferenceLocateOptions()
        {return RefLocateOption.TreatAsElement;}
        protected override bool OnPostLocate(HitPath path,out string reason)
        {
            var element=path==null?null:path.GetHeadElement();
            if(LocatedElement.IsReference(element)){reason="请选择活动模型中的围栏辅助线。";return false;}
            return base.OnPostLocate(path,out reason);
        }
        internal static void Begin()
        {
            if(active!=null){AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;return;}
            var created=new HandrailLocateTool();
            snap=AccuSnap.SnapEnabled;locate=AccuSnap.LocateEnabled;active=created;
            try {created.InstallTool();AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;}
            catch {active=null;AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try {tool.ExitTool();}
            finally {AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;
                var ended=Ended;if(ended!=null)ended();}
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("请选择水平或带坡度的围栏辅助线；左键生成预览，右键取消并退出。");
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var hit=DoLocate(ev,true,(int)ComponentMode.None);
            var element=hit==null?null:hit.GetHeadElement();
            if(element==null||!element.IsValid)return true;
            var located=LocatedElement.From(element);
            located.ClickX=ev.Point.X;located.ClickY=ev.Point.Y;located.ClickZ=ev.Point.Z;
            var picked=Picked;if(picked!=null)picked(located);
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){End();return true;}
        protected override void OnRestartTool(){End();}
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this))
            {active=null;AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;
                var ended=Ended;if(ended!=null)ended();}
            base.OnCleanup();
        }
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        {return StatusInt.Error;}
    }
}
