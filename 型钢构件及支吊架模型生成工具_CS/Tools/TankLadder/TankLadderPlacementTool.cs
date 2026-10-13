using System;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal sealed class TankLadderPlacementTool:DgnPrimitiveTool
    {
        private static TankLadderPlacementTool active;
        private bool oldSnap,oldLocate;
        private TankLadderPlacementTool():base(0,0){}
        internal static event Action<DPoint3d> Picked;
        internal static event Action Ended;
        internal static bool IsActive {get{return active!=null;}}
        internal static void Begin()
        {
            if(active!=null){Prompt();return;}
            var tool=new TankLadderPlacementTool {oldSnap=AccuSnap.SnapEnabled,oldLocate=AccuSnap.LocateEnabled};active=tool;
            try{tool.InstallTool();AccuSnap.SnapEnabled=true;AccuSnap.LocateEnabled=true;}
            catch{active=null;tool.RestoreSnap();throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try{tool.ExitTool();}finally{tool.RestoreSnap();var ended=Ended;if(ended!=null)ended();}
        }
        private void RestoreSnap(){AccuSnap.SnapEnabled=oldSnap;AccuSnap.LocateEnabled=oldLocate;}
        private static void Prompt(){NotificationManager.OutputPrompt("左键点取箱顶基准点（顶部横向角钢中点）；右键取消未确认预览。");}
        protected override void OnPostInstall(){base.OnPostInstall();Prompt();}
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if(!ReferenceEquals(active,this))return true;
            var picked=Picked;if(picked!=null)picked(ev.Point);return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){if(ReferenceEquals(active,this))End();return true;}
        protected override void OnRestartTool(){if(ReferenceEquals(active,this))End();}
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this)){active=null;RestoreSnap();var ended=Ended;if(ended!=null)ended();}
            base.OnCleanup();
        }
    }
}
