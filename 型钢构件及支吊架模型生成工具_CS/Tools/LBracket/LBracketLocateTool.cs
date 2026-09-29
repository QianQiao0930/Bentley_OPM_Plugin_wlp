using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class LBracketLocateTool:DgnElementSetTool
    {
        private static LBracketLocateTool active;
        private static bool snap,locate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        private LBracketLocateTool():base(0,0){}
        protected override RefLocateOption GetReferenceLocateOptions()
        {return RefLocateOption.TreatAsElement;}
        protected override bool OnPostLocate(HitPath path,out string reason)
        {
            if(base.OnPostLocate(path,out reason))return true;
            var element=path==null?null:path.GetHeadElement();
            if(LocatedElement.IsReference(element)){reason="";return true;}
            return false;
        }
        internal static void Begin()
        {
            if(active!=null){AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;return;}
            var created=new LBracketLocateTool();
            snap=AccuSnap.SnapEnabled;locate=AccuSnap.LocateEnabled;active=created;
            try{created.InstallTool();AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;}
            catch{active=null;AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try{tool.ExitTool();}
            finally{AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;
                var ended=Ended;if(ended!=null)ended();}
        }
        protected override void OnPostInstall()
        {base.OnPostInstall();NotificationManager.OutputPrompt("请选择两段组成的 L 形辅助折线，左键预览；右键退出。");}
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
