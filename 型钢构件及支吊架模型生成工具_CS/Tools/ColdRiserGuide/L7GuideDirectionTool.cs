using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class L7GuideDirectionTool:DgnPrimitiveTool
    {
        private static L7GuideDirectionTool active;
        private readonly DPoint3d center;
        private readonly DVector3d axis;
        private readonly bool handoffToLength;
        private bool compassActivated,oldActive;
        private AccuDraw.RotationMode oldMode;
        internal static event Action<double,int,double,double> Oriented;
        internal static event Action Cancelled;
        internal static bool IsActive {get{return active!=null;}}
        private L7GuideDirectionTool(DPoint3d center,DVector3d axis,bool handoff):base(0,0)
        {this.center=center;this.axis=axis;handoffToLength=handoff;}
        internal static void Begin(DPoint3d center,DVector3d axis,bool handoffToLength)
        {
            if(active!=null)active=null;
            var tool=new L7GuideDirectionTool(center,axis,handoffToLength);active=tool;
            try {tool.InstallTool();} catch {active=null;throw;}
        }
        internal static void RetireForHandoff() {active=null;}
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try {tool.ExitTool();} finally {var h=Cancelled;if(h!=null)h();}
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("L7：在垂直于管轴的罗盘平面内转动，左键锁定安装方向；右键取消。");
            BeginDynamics();
            try
            {
                double[] x,y,z;
                // X/Y 落在立管的径向平面，Z 沿管轴；竖直立管显示为模型 XY 罗盘。
                A1ClampCalculator.RadialFrame(new[]{axis.X,axis.Y,axis.Z},out x,out y,out z);
                var rotation=DMatrix3d.FromColumns(new DVector3d(x[0],x[1],x[2]),
                    new DVector3d(y[0],y[1],y[2]),new DVector3d(z[0],z[1],z[2]));
                oldActive=AccuDraw.Active;oldMode=AccuDraw.ActiveRotationMode;
                compassActivated=true;AccuDraw.Active=true;
                AccuDraw.ActiveRotationMode=AccuDraw.RotationMode.Context;
                AccuDraw.SetContext(AccuDrawFlags.SetOrigin|AccuDrawFlags.FixedOrigin|
                    AccuDrawFlags.SetRMatrix,center,rotation);
                AccuDraw.Rotation=rotation;
                AccuDraw.SetContext(AccuDrawFlags.SetFocus);
            }
            catch(Exception ex)
            {NotificationManager.OutputPrompt("罗盘定向失败，可用光标选方向："+ex.Message);}
        }
        private double Angle(DPoint3d point)
        {return A1ClampCalculator.AngleFromCursor(new[]{axis.X,axis.Y,axis.Z},
            new[]{point.X-center.X,point.Y-center.Y,point.Z-center.Z});}
        private DPoint3d Tip(double angle)
        {
            double[] zero,turn,along;
            A1ClampCalculator.RadialFrame(new[]{axis.X,axis.Y,axis.Z},
                out zero,out turn,out along);
            double a=angle*Math.PI/180,c=Math.Cos(a),s=Math.Sin(a);
            var model=Session.Instance.GetActiveDgnModel();
            double reach=300*model.GetModelInfo().UorPerMeter/1000;
            return new DPoint3d(center.X+reach*(c*zero[0]+s*turn[0]),
                center.Y+reach*(c*zero[1]+s*turn[1]),
                center.Z+reach*(c*zero[2]+s*turn[2]));
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            var model=Session.Instance.GetActiveDgnModel();
            var line=DraftingElementSchema.ToElement(model,
                CurvePrimitive.CreateLine(new DSegment3d(center,Tip(Angle(ev.Point)))),null);
            if(line==null)return;
            var redraw=new RedrawElems();
            redraw.SetDynamicsViewsFromActiveViewSet(ev.Viewport);
            redraw.DrawMode=DgnDrawMode.TempDraw;redraw.DrawPurpose=DrawPurpose.Dynamics;
            redraw.DoRedraw(line);
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            double angle=Angle(ev.Point);
            var h=Oriented;
            if(handoffToLength)RetireForHandoff();
            else {active=null;RestoreCompass();ExitTool();}
            if(h!=null)h(angle,ev.ViewNumber,ev.ViewPoint.X,ev.ViewPoint.Y);
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){End();return true;}
        protected override void OnRestartTool(){End();}
        protected override void OnCleanup()
        {
            RestoreCompass();
            if(ReferenceEquals(active,this))
            {active=null;var h=Cancelled;if(h!=null)h();}
            base.OnCleanup();
        }
        private void RestoreCompass()
        {
            if(!compassActivated)return;
            try{AccuDraw.ActiveRotationMode=oldMode;AccuDraw.Active=oldActive;}catch{}
            compassActivated=false;
        }
    }
}
