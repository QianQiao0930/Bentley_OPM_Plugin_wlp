using System;
using System.Runtime.InteropServices;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class L7GuideLengthTool:DgnPrimitiveTool
    {
        private static L7GuideLengthTool active;
        private readonly DPoint3d center;
        private readonly DVector3d direction;
        private readonly int startView;
        private readonly double startX,startY;
        private bool released,armed;
        internal static event Action<double> LengthChanged;
        internal static event Action<double> Accepted;
        internal static event Action Cancelled;
        internal static event Action<string> Failed;
        internal static bool IsActive {get{return active!=null;}}
        [DllImport("user32.dll")]
        private static extern short GetAsyncKeyState(int key);
        private L7GuideLengthTool(DPoint3d center,DVector3d direction,int view,
            double x,double y):base(0,0)
        {this.center=center;this.direction=direction;startView=view;startX=x;startY=y;}
        internal static void Begin(DPoint3d center,DVector3d direction,int view,double x,double y)
        {
            var tool=new L7GuideLengthTool(center,direction,view,x,y);active=tool;
            try {tool.InstallTool();tool.BeginDynamics();}
            catch {active=null;throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try {tool.ExitTool();} finally {var h=Cancelled;if(h!=null)h();}
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("L7：松开左键，沿构件 A 方向拉伸 L（300～1000 mm），再左键固定；右键取消。");
        }
        private bool Moved(DgnButtonEvent ev)
        {
            double dx=ev.ViewPoint.X-startX,dy=ev.ViewPoint.Y-startY;
            return ev.ViewNumber!=startView||dx*dx+dy*dy>25;
        }
        private double Length(DgnButtonEvent ev)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null)throw new InvalidOperationException("没有活动模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            if(scale<=0)throw new InvalidOperationException("模型单位无效。");
            double raw;
            string source=ev.Source.ToString();
            if(source.IndexOf("Precision",StringComparison.OrdinalIgnoreCase)>=0||
                source.IndexOf("ElemSnap",StringComparison.OrdinalIgnoreCase)>=0||
                source.IndexOf("Tentative",StringComparison.OrdinalIgnoreCase)>=0)
            {
                var point=ev.Point;
                raw=((point.X-center.X)*direction.X+(point.Y-center.Y)*direction.Y+
                    (point.Z-center.Z)*direction.Z)/scale;
            }
            else
            {
                var end=new DPoint3d(center.X+1000*scale*direction.X,
                    center.Y+1000*scale*direction.Y,center.Z+1000*scale*direction.Z);
                DPoint3d[] projected=ev.Viewport.ActiveToView(new[]{center,end,ev.RawPoint});
                if(projected==null||projected.Length<3)
                    throw new InvalidOperationException("无法投影当前光标位置。");
                double dx=projected[1].X-projected[0].X,dy=projected[1].Y-projected[0].Y;
                double denominator=dx*dx+dy*dy;
                if(denominator<=1e-6)
                    throw new InvalidOperationException("当前视图看不到构件 A 的拉伸方向，请切换视图。");
                raw=1000*((projected[2].X-projected[0].X)*dx+
                    (projected[2].Y-projected[0].Y)*dy)/denominator;
            }
            if(double.IsNaN(raw)||double.IsInfinity(raw))
                throw new InvalidOperationException("拉伸长度无效。");
            return Math.Max(L7GuideCatalog.MinLengthMm,
                Math.Min(L7GuideCatalog.MaxLengthMm,raw));
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            try
            {
                if((GetAsyncKeyState(0x01)&0x8000)==0)released=true;
                if(released&&Moved(ev))armed=true;
                double length=Length(ev);
                var model=Session.Instance.GetActiveDgnModel();
                double scale=model.GetModelInfo().UorPerMeter/1000.0;
                var end=new DPoint3d(center.X+length*scale*direction.X,
                    center.Y+length*scale*direction.Y,center.Z+length*scale*direction.Z);
                var line=DraftingElementSchema.ToElement(model,
                    CurvePrimitive.CreateLine(new DSegment3d(center,end)),null);
                if(line!=null)
                {
                    var redraw=new RedrawElems();
                    redraw.SetDynamicsViewsFromActiveViewSet(ev.Viewport);
                    redraw.DrawMode=DgnDrawMode.TempDraw;redraw.DrawPurpose=DrawPurpose.Dynamics;
                    redraw.DoRedraw(line);
                }
                var changed=LengthChanged;if(changed!=null)changed(length);
            }
            catch(Exception ex) {var h=Failed;if(h!=null)h(ex.Message);}
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if(!released||!armed||!Moved(ev))
            {var error=Failed;if(error!=null)error("请先松开确定方向的左键，移动光标拉伸，再左键固定。");return false;}
            try
            {
                double length=Length(ev);
                active=null;
                ExitTool();
                var h=Accepted;if(h!=null)h(length);
            }
            catch(Exception ex) {var h=Failed;if(h!=null)h(ex.Message);}
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){End();return true;}
        protected override void OnRestartTool(){End();}
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this))
            {active=null;var h=Cancelled;if(h!=null)h();}
            base.OnCleanup();
        }
    }
}
