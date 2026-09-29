using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>定位管轴后，光标在管道径向平面内决定 U 型管卡开口方向。</summary>
    internal sealed class A1ClampOrientationTool:DgnPrimitiveTool
    {
        private static A1ClampOrientationTool active;
        private readonly DPoint3d center;
        private readonly double[] axis;
        private readonly Func<double,Element> build;
        private Element prototype;
        private double shownAngle;
        private bool compassActivated;
        private AccuDraw.RotationMode compassRotationMode;
        private bool compassWasActive;
        private A1ClampOrientationTool(DPoint3d center,DVector3d axis,Func<double,Element> build)
            :base(0,0)
        {this.center=center;this.axis=new[]{axis.X,axis.Y,axis.Z};this.build=build;}
        internal static event Action<double> Oriented;
        internal static event Action Ended;
        internal static bool IsActive{get{return active!=null;}}
        internal static void Begin(DPoint3d center,DVector3d axis,Func<double,Element> build)
        {
            // 已有方向工具时**静默退役**（只清 active，不调 End/ExitTool）：ExitTool 挂起的
            // "退出当前工具"会在下一个原生事件结算，那时当前工具已经是新装的实例，
            // 会被误杀并触发一次伪 Ended（同 2906eca 竞态）。旧实例由随后的
            // InstallTool 工具切换收尾，其 OnCleanup 因 active!=this 而静默。
            if(active!=null)active=null;
            var tool=new A1ClampOrientationTool(center,axis,build);active=tool;
            try{tool.InstallTool();}catch{active=null;throw;}
        }
        internal static void End()
        {
            var tool=active;if(tool==null)return;active=null;
            try{tool.ExitTool();}finally{var ended=Ended;if(ended!=null)ended();}
        }
        internal static void InvalidatePrototype()
        {if(active!=null){active.prototype=null;active.shownAngle=0;}}
        private double CursorAngle(DPoint3d cursor)
        {return A1ClampCalculator.AngleFromCursor(axis,new[]{cursor.X-center.X,
            cursor.Y-center.Y,cursor.Z-center.Z});}
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("精确绘图罗盘已顺着管轴定向：X 沿管道走向、Y 为开口 0°（朝上），"
                +"回车锁轴、Tab 切换字段；移动光标调整 A1 开口方向，左键锁定方向并生成预览；右键取消。");
            BeginDynamics();
            // 动态绘图起来之后再接管罗盘（与 Python 端 F2 弯头耳轴的 _start_drag 同序）：
            // 不显式激活时罗盘是灰的、键盘焦点也不在罗盘上，回车会被 MicroStation 当成
            // 打开 Key-in 对话框。
            ActivateCompass();
        }
        /// <summary>
        /// 激活精确绘图罗盘并把罗盘平面转到**顺着管轴**的平面（管轴 + 开口 0° 方向）：
        /// 1) <see cref="AccuDraw.Active"/>=true —— 未激活时罗盘灰色、不接收键盘；
        /// 2) SetOrigin|FixedOrigin —— 原点固定在管心，调方向时罗盘不跟着光标跑；
        /// 3) SetRMatrix —— 罗盘三轴取 <see cref="A1ClampCalculator.CompassFrame"/>：
        ///    X=管轴（罗盘顺着管道走向，与 Python 端"本地 X 沿管轴"一致），Y=开口角 0° 方向，
        ///    Z=平面法向。（矩阵按列存三轴：已用元数据探针实测 FromColumns 的 ColumnX 即传入的 X 轴。）
        /// 4) 旋转模式改 Context 并记住原值，退出时连同激活状态一起还原 —— 不影响别的命令。
        /// </summary>
        private void ActivateCompass()
        {
            try
            {
                double[] xAxis,yAxis,zAxis;
                A1ClampCalculator.CompassFrame(axis,out xAxis,out yAxis,out zAxis);
                var rotation=DMatrix3d.FromColumns(
                    new DVector3d(xAxis[0],xAxis[1],xAxis[2]),
                    new DVector3d(yAxis[0],yAxis[1],yAxis[2]),
                    new DVector3d(zAxis[0],zAxis[1],zAxis[2]));
                compassWasActive=AccuDraw.Active;
                compassRotationMode=AccuDraw.ActiveRotationMode;
                compassActivated=true;
                AccuDraw.Active=true;
                // 先切到"按上下文定向"，再写原点与旋转矩阵 —— 顺序反了新矩阵会被模式切换冲掉。
                AccuDraw.ActiveRotationMode=AccuDraw.RotationMode.Context;
                AccuDraw.SetContext(AccuDrawFlags.SetOrigin|AccuDrawFlags.FixedOrigin|
                    AccuDrawFlags.SetRMatrix,center,rotation);
                AccuDraw.Rotation=rotation;   // 托管接口两条通路并存，兜底再写一次
                AccuDraw.SetContext(AccuDrawFlags.SetFocus);
            }
            catch(Exception ex)
            {
                compassActivated=false;
                NotificationManager.OutputPrompt("精确绘图罗盘定向失败，仍可移动光标调整方向："+ex.Message);
            }
        }
        /// <summary>还原罗盘的激活状态与旋转模式，避免影响后续命令的罗盘行为。</summary>
        private void RestoreCompass()
        {
            if(!compassActivated) return;
            compassActivated=false;
            try
            {
                AccuDraw.ActiveRotationMode=compassRotationMode;
                AccuDraw.Active=compassWasActive;
            }
            catch { }
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            double angle=CursorAngle(ev.Point);
            if(prototype==null)
            {
                try{prototype=build(0);shownAngle=0;}
                catch{prototype=null;return;}
            }
            double delta=angle-shownAngle;
            if(Math.Abs(delta)>1e-6)
            {
                var rotation=DTransform3d.FromRotationAroundLine(center,
                    new DVector3d(axis[0],axis[1],axis[2]),Angle.FromRadians(delta*Math.PI/180));
                prototype.ApplyTransform(new TransformInfo(rotation));
                shownAngle=angle;
            }
            var redraw=new RedrawElems();
            redraw.SetDynamicsViewsFromActiveViewSet(Session.GetActiveViewport());
            redraw.DrawMode=DgnDrawMode.TempDraw;redraw.DrawPurpose=DrawPurpose.Dynamics;
            redraw.DoRedraw(prototype);
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            double angle=CursorAngle(ev.Point);
            var oriented=Oriented;
            if(oriented!=null)oriented(angle);
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
