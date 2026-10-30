using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class BracketLocateTool:ProbeLocateTool
    {
        private static BracketLocateTool active;
        private static bool snap,locate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        private readonly string prompt;
        private BracketLocateTool(string instruction):base(0,0){prompt=instruction;}
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
        {Begin("请选择一条水平辅助线，左键生成三角架预览；右键退出。");}
        internal static void Begin(string instruction)
        {
            if(active!=null){active.PrepareForPicking("重复开始点取");AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;return;}
            var created=new BracketLocateTool(instruction);
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
            NotificationManager.OutputPrompt(prompt);
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
