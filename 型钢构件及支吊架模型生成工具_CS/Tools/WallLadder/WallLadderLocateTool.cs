using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    /// <summary>墙面爬梯只读定位；沿用共用工具的参考定位与捕捉恢复约定。</summary>
    internal sealed class WallLadderLocateTool : ProbeLocateTool
    {
        private static WallLadderLocateTool active;
        private static bool oldSnap,oldLocate;
        internal static event Action<LocatedElement> Picked;
        internal static event Action Ended;
        internal static bool IsActive {get{return active!=null;}}
        private WallLadderLocateTool():base(0,0){}
        protected override RefLocateOption GetReferenceLocateOptions(){return RefLocateOption.TreatAsElement;}
        protected override bool OnPostLocate(HitPath path,out string cantAcceptReason)
        {
            if(base.OnPostLocate(path,out cantAcceptReason))return true;
            if(path!=null&&LocatedElement.IsReference(path.GetHeadElement())){cantAcceptReason="";return true;}
            return false;
        }
        internal static void Begin()
        {
            if(active!=null){AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;Prompt();return;}
            var created=new WallLadderLocateTool();oldSnap=AccuSnap.SnapEnabled;oldLocate=AccuSnap.LocateEnabled;active=created;
            try{created.InstallTool();AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;}
            catch{active=null;Restore();throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try{tool.ExitTool();}finally{Restore();var ended=Ended;if(ended!=null)ended();}
        }
        private static void Restore(){AccuSnap.SnapEnabled=oldSnap;AccuSnap.LocateEnabled=oldLocate;}
        private static void Prompt(){NotificationManager.OutputPrompt("请选择代表墙面和爬梯中心投影的竖直线，左键预览；右键退出。");}
        protected override void OnPostInstall(){base.OnPostInstall();Prompt();}
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if(!ReferenceEquals(active,this))return true;
            var hit=DoLocate(ev,true,(int)ComponentMode.None);var element=hit==null?null:hit.GetHeadElement();
            if(element==null||!element.IsValid){NotificationManager.OutputPrompt("未找到竖直辅助线，请重新点取。");return true;}
            var picked=Picked;if(picked!=null)picked(LocatedElement.From(element));return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){if(ReferenceEquals(active,this))End();return true;}
        protected override void OnRestartTool(){if(ReferenceEquals(active,this))End();}
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this)){active=null;Restore();var ended=Ended;if(ended!=null)ended();}
            base.OnCleanup();
        }
        public override StatusInt OnElementModify(Bentley.DgnPlatformNET.Elements.Element e){return StatusInt.Error;}
    }
}
