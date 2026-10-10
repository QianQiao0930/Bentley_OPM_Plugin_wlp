using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 立管耳轴沿管轴滑动工具（交互复制 A1ClampOrientationTool 的两段式先例）：
    /// 点取预览后由页面"静默交接"装载。罗盘平面取过管轴的竖直面（X 轴=沿管轴向上），
    /// 移动光标把光标点向管线段投影，动态原型只做平移变换（不重建几何）；
    /// 左键把锁定位置（UOR）回传页面，页面折算成沿轴偏移 mm 并重建预览；右键取消。
    /// </summary>
    internal sealed class TrunnionSlideTool:DgnPrimitiveTool
    {
        private static TrunnionSlideTool active;
        private readonly DPoint3d lineStart,lineEnd,anchor;
        private readonly Func<DPoint3d,Element> build;
        private Element prototype;
        private DPoint3d shownCenter;
        private bool compassActivated;
        private AccuDraw.RotationMode compassRotationMode;
        private bool compassWasActive;
        /// <summary>锁定事件：参数是鼠标左键点下时管线段上的投影点（UOR）。</summary>
        internal static event Action<DPoint3d> Locked;
        internal static event Action Ended;
        internal static bool IsActive { get { return active!=null; } }

        private TrunnionSlideTool(DPoint3d anchor,DPoint3d lineStart,DPoint3d lineEnd,
            Func<DPoint3d,Element> build):base(0,0)
        {this.anchor=anchor;this.lineStart=lineStart;this.lineEnd=lineEnd;this.build=build;}

        internal static void Begin(DPoint3d anchor,DPoint3d lineStart,DPoint3d lineEnd,
            Func<DPoint3d,Element> build)
        {
            // 已有滑动工具时静默退役（不调 End）：ExitTool 挂起的"退出当前工具"会在下
            // 一个原生事件结算，误杀新装实例并触发一次伪 Ended（同 2906eca 竞态）。
            if(active!=null)active=null;
            var tool=new TrunnionSlideTool(anchor,lineStart,lineEnd,build);
            active=tool;
            try{tool.InstallTool();}
            catch{active=null;throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try{tool.ExitTool();}finally{var ended=Ended;if(ended!=null)ended();}
        }
        /// <summary>重置动态原型：下一次动态帧按新的参数在锚点重建（载人用当前偏移）。</summary>
        internal static void InvalidatePrototype()
        {if(active!=null){active.prototype=null;active.shownCenter=active.anchor;}}

        /// <summary>光标点向管线段的投影（UOR），截断至两端。</summary>
        private DPoint3d Project(DPoint3d cursor)
        {
            double dx=lineEnd.X-lineStart.X,dy=lineEnd.Y-lineStart.Y,dz=lineEnd.Z-lineStart.Z;
            double lengthSquared=dx*dx+dy*dy+dz*dz;
            if(lengthSquared<=1.0e-12)return lineStart;
            double t=((cursor.X-lineStart.X)*dx+(cursor.Y-lineStart.Y)*dy+
                (cursor.Z-lineStart.Z)*dz)/lengthSquared;
            if(t<0.0)t=0.0;else if(t>1.0)t=1.0;
            return new DPoint3d(lineStart.X+t*dx,lineStart.Y+t*dy,lineStart.Z+t*dz);
        }
        /// <summary>沿管轴方向单位向量（UOR），正分量取 +Z（竖管即向上）。</summary>
        private double[] UpUnit()
        {
            double dx=lineEnd.X-lineStart.X,dy=lineEnd.Y-lineStart.Y,dz=lineEnd.Z-lineStart.Z;
            double length=Math.Sqrt(dx*dx+dy*dy+dz*dz);
            if(length<=1.0e-12)return new[]{0.0,0.0,1.0};
            double unitX=dx/length,unitY=dy/length,unitZ=dz/length;
            if(unitZ<0){unitX=-unitX;unitY=-unitY;unitZ=-unitZ;}
            return new[]{unitX,unitY,unitZ};
        }
        /// <summary>
        /// 激活精确绘图罗盘并把罗盘平面定到过管轴的竖直面：X=沿管轴向上，Y=水平垂直
        /// 于管轴，Z=补全。这些标志序列复制自 A1ClampOrientationTool 的实测可用组合。
        /// </summary>
        private void ActivateCompass()
        {
            try
            {
                var u=UpUnit();
                double tx=0,ty=1,tz=0;
                double dot=Math.Abs(u[0]*tx+u[1]*ty+u[2]*tz);
                if(dot>0.9){tx=1;ty=0;tz=0;}
                double proj=u[0]*tx+u[1]*ty+u[2]*tz;
                double vx=tx-proj*u[0],vy=ty-proj*u[1],vz=tz-proj*u[2];
                double vLen=Math.Sqrt(vx*vx+vy*vy+vz*vz);
                if(vLen<=1.0e-12)return;
                var yAxis=new DVector3d(vx/vLen,vy/vLen,vz/vLen);
                var xAxis=new DVector3d(u[0],u[1],u[2]);
                var zAxis=Cross(xAxis,yAxis);
                var rotation=DMatrix3d.FromColumns(xAxis,yAxis,zAxis);
                compassWasActive=AccuDraw.Active;
                compassRotationMode=AccuDraw.ActiveRotationMode;
                compassActivated=true;
                AccuDraw.Active=true;
                AccuDraw.ActiveRotationMode=AccuDraw.RotationMode.Context;
                AccuDraw.SetContext(AccuDrawFlags.SetOrigin|AccuDrawFlags.FixedOrigin|
                    AccuDrawFlags.SetRMatrix,anchor,rotation);
                AccuDraw.Rotation=rotation;
                AccuDraw.SetContext(AccuDrawFlags.SetFocus);
            }
            catch(Exception ex)
            {
                compassActivated=false;
                NotificationManager.OutputPrompt("精确绘图罗盘定向失败，仍可移动光标滑动位置："+ex.Message);
            }
        }
        private static DVector3d Cross(DVector3d a,DVector3d b)
        {return new DVector3d(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);}
        private void RestoreCompass()
        {
            if(!compassActivated)return;
            compassActivated=false;
            try
            {
                AccuDraw.ActiveRotationMode=compassRotationMode;
                AccuDraw.Active=compassWasActive;
            }
            catch { }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("移动光标沿管轴滑动耳轴位置，左键锁定并生成预览；右键取消。");
            BeginDynamics();
            // 与 A1ClampOrientationTool 同序：动态绘图起来之后再接管罗盘，否则罗盘灰色、
            // 键盘焦点也不在罗盘上，回车会被 MicroStation 当成打开 Key-in 对话框。
            ActivateCompass();
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            try
            {
                if(prototype==null)
                {
                    prototype=build(anchor);
                    shownCenter=anchor;
                }
                var target=Project(ev.Point);
                double dx=target.X-shownCenter.X,dy=target.Y-shownCenter.Y,dz=target.Z-shownCenter.Z;
                if(Math.Abs(dx)>1.0e-9||Math.Abs(dy)>1.0e-9||Math.Abs(dz)>1.0e-9)
                {
                    // 每帧只平移动态原型，不重建几何（A1 方向工具同一性能模式）。
                    prototype.ApplyTransform(new TransformInfo(DTransform3d.FromTranslation(dx,dy,dz)));
                    shownCenter=target;
                }
                var redraw=new RedrawElems();
                redraw.SetDynamicsViewsFromActiveViewSet(Session.GetActiveViewport());
                redraw.DrawMode=DgnDrawMode.TempDraw;redraw.DrawPurpose=DrawPurpose.Dynamics;
                redraw.DoRedraw(prototype);
            }
            catch(Exception ex)
            {
                prototype=null;
                NotificationManager.OutputPrompt("耳轴滑动预览失败："+ex.Message);
            }
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var locked=Locked;
            if(locked!=null)locked(Project(ev.Point));
            End();return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev){End();return true;}
        protected override void OnRestartTool(){End();}
        protected override void OnCleanup()
        {
            RestoreCompass();
            if(ReferenceEquals(active,this))
            {active=null;var ended=Ended;if(ended!=null)ended();}
            prototype=null;base.OnCleanup();
        }
    }
}
