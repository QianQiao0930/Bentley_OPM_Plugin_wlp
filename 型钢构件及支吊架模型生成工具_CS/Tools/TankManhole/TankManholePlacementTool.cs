using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>两段式放置工具：
    /// ① 移动光标整套人孔跟随（AccuDraw 激活，可键入距离），左键定原点；
    /// ② 再移动光标调整朝向（人孔始终朝向光标方向），再次左键写入模型完成放置；
    /// 右键任意时刻取消。参数变化时页面调用 <see cref="InvalidatePrototype"/>，下一帧按新参数重建。</summary>
    internal sealed class TankManholePlacementTool : DgnPrimitiveTool
    {
        private enum Stage { PickPoint, PickAngle }
        private static TankManholePlacementTool active;
        private TankManholePlacementTool() : base(0,0) { }

        internal static event Action<DPoint3d,double> Placed;   // (原点, 朝向角度°)
        internal static event Action Ended;

        private Func<DPoint3d,double,Element> buildPrototype;
        private Stage stage;
        private DPoint3d origin;
        private double heading;          // 当前朝向（弧度，世界 xy 平面，0 为 +X）
        private Element prototype;       // 缓存的动态单元（随帧增量变换）
        private DPoint3d prototypeAt;    // 单元当前的平移位置
        private double prototypeHeading; // 单元当前的朝向

        internal static void Begin(Func<DPoint3d,double,Element> buildPrototype,double initialHeadingRadians)
        {
            End(); var tool=new TankManholePlacementTool(); active=tool;
            tool.buildPrototype=buildPrototype;
            tool.heading=initialHeadingRadians;
            try { tool.InstallTool(); }
            catch { active=null; throw; }
        }
        internal static void End()
        {
            var tool=active; if(tool==null) return; active=null;
            try { tool.ExitTool(); }
            finally { var ended=Ended; if(ended!=null) ended(); }
        }
        internal static void InvalidatePrototype()
        {
            var tool=active; if(tool==null) return;
            tool.prototype=null; tool.prototypeAt=DPoint3d.Zero;
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            // 显式打开精确绘图（本工具没有让框架自动弹罗盘的环节，且用户会话里可能被关掉）。
            try { Session.Instance.Keyin("accudraw activate"); } catch { }
            // 打开 AccuSnap：捕捉点（端点/中点/圆心等关键点标记）由它负责，与 AccuDraw 是两套机制。
            AccuSnap.SnapEnabled=true;
            AccuSnap.LocateEnabled=true;
            NotificationManager.OutputPrompt("移动光标预览人孔位置，左键定原点；再移动调整朝向，再次左键放置；右键取消。");
            BeginDynamics();
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            if(buildPrototype==null) return;
            if(prototype==null)
            {
                try
                {
                    prototype = stage==Stage.PickPoint
                        ? buildPrototype(DPoint3d.Zero,heading)
                        : buildPrototype(origin,heading);
                }
                catch { prototype=null; return; }
                prototypeAt = stage==Stage.PickPoint ? DPoint3d.Zero : origin;
                prototypeHeading = heading;
            }
            if(stage==Stage.PickPoint)
            {
                var step=new DVector3d(ev.Point.X-prototypeAt.X,ev.Point.Y-prototypeAt.Y,
                    ev.Point.Z-prototypeAt.Z);
                prototype.ApplyTransform(new TransformInfo(DTransform3d.FromTranslation(step)));
                prototypeAt=ev.Point;
            }
            else
            {
                double target=Math.Atan2(ev.Point.Y-origin.Y,ev.Point.X-origin.X);
                double delta=target-prototypeHeading;
                var toOrigin=DTransform3d.FromTranslation(origin);
                var back=DTransform3d.FromTranslation(new DPoint3d(-origin.X,-origin.Y,-origin.Z));
                var rotation=DTransform3d.Rotation(2,Angle.FromRadians(delta));
                var transform=DTransform3d.Multiply(toOrigin,DTransform3d.Multiply(rotation,back));
                prototype.ApplyTransform(new TransformInfo(transform));
                prototypeHeading=target; heading=target;
            }
            var redraw=new RedrawElems();
            redraw.SetDynamicsViewsFromActiveViewSet(Session.GetActiveViewport());
            redraw.DrawMode=DgnDrawMode.TempDraw;
            redraw.DrawPurpose=DrawPurpose.Dynamics;
            redraw.DoRedraw(prototype);
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if(stage==Stage.PickPoint)
            {
                origin=ev.Point; stage=Stage.PickAngle;
                NotificationManager.OutputPrompt("原点已定：移动光标调整朝向，再次左键放置；右键取消。");
                return true;
            }
            // 第二次左键：按当前预览原样写入模型，完成放置并结束。
            try
            {
                var status=prototype.AddToModel();
                if(status!=StatusInt.Success)
                { NotificationManager.OutputPrompt("写入人孔失败："+status); return true; }
            }
            catch(Exception ex)
            { NotificationManager.OutputPrompt("写入人孔失败："+ex.Message); return true; }
            var placed=Placed;
            if(placed!=null) placed(origin,heading*180.0/Math.PI);
            End();
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev) { End(); return true; }
        protected override void OnRestartTool() { End(); }
        protected override void OnCleanup()
        {
            if(ReferenceEquals(active,this))
            { active=null; var ended=Ended; if(ended!=null) ended(); }
            prototype=null; buildPrototype=null;
            base.OnCleanup();
        }
    }
}
