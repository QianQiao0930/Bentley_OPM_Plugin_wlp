using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class TFrameLocateTool:ProbeLocateTool
    {
        private static TFrameLocateTool active;
        private static bool snap,locate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        private TFrameLocateTool():base(0,0){}
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
            ProbeLocateLog.Write("TFrame Begin：已有点取工具="+(active!=null));
            if(active!=null){active.PrepareForPicking("重复开始点取");AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;active.Prompt();return;}
            var created=new TFrameLocateTool();
            snap=AccuSnap.SnapEnabled;locate=AccuSnap.LocateEnabled;active=created;
            try{created.InstallTool();AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;}
            catch{active=null;AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;throw;}
        }
        internal static void End()
        {
            var tool=active;ProbeLocateLog.Write("TFrame End：工具存在="+(tool!=null));
            if(tool==null)return;active=null;
            try{tool.ExitTool();}
            finally{AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;
                var ended=Ended;if(ended!=null)ended();}
        }
        protected override void OnPostInstall()
        {base.OnPostInstall();Prompt();}
        private void Prompt()
        {
            NotificationManager.OutputPrompt("请选择当前 T 型架类别对应的辅助直线，左键预览；右键退出。"+
                (IgnoredSelectionSet?"（已清空原选择集，请重新点选）":""));
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var hit=DoLocate(ev,true,(int)ComponentMode.None);
            var element=hit==null?null:hit.GetHeadElement();
            ProbeLocateLog.Write("TFrame OnDataButton：定位结果="+
                (element==null?"null":element.ElementId.ToString())+"；议程="+AgendaCount());
            if(element==null||!element.IsValid)
            {NotificationManager.OutputPrompt("未定位到辅助直线，请把光标悬停在直线上再单击左键。");return true;}
            var located=LocatedElement.From(element);
            located.ClickX=ev.Point.X;located.ClickY=ev.Point.Y;located.ClickZ=ev.Point.Z;
            var picked=Picked;if(picked!=null)picked(located);
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){ProbeLocateLog.Write("TFrame OnResetButton");End();return true;}
        protected override void OnRestartTool(){ProbeLocateLog.Write("TFrame OnRestartTool");End();}
        private uint AgendaCount()
        {try{var agenda=ElementAgenda;return agenda==null?0:agenda.GetCount();}catch{return 0;}}
        protected override void OnCleanup()
        {
            ProbeLocateLog.Write("TFrame OnCleanup：是否当前工具="+ReferenceEquals(active,this));
            if(ReferenceEquals(active,this))
            {active=null;AccuSnap.SnapEnabled=snap;AccuSnap.LocateEnabled=locate;
                var ended=Ended;if(ended!=null)ended();}
            base.OnCleanup();
        }
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element element)
        {return StatusInt.Error;}
    }
}
