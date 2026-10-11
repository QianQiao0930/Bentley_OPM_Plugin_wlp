using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 耳轴与管夹共用的沿轴滑动工具：
    /// 点取预览后由页面"静默交接"装载。罗盘 X 轴沿定位轴，Y/Z 锁零，
    /// 移动光标把光标点向管线段投影，动态原型只做平移变换（不重建几何）；
    /// 左键把锁定位置（UOR）回传页面，页面折算成沿轴偏移 mm 并重建预览；右键取消。
    /// </summary>
    internal sealed class AxisSlideTool : DgnPrimitiveTool
    {
        private static AxisSlideTool active;
        private readonly DPoint3d lineStart, lineEnd, anchor;
        private readonly Func<DPoint3d, Element> build;
        private Element prototype;
        private DPoint3d shownCenter;
        private bool compassActivated;
        private AccuDraw.RotationMode compassRotationMode;
        private bool compassWasActive, oldSnap, oldLocate;
        private AccuDraw.CompassMode oldCompassMode;
        private DPoint3d oldCompassOrigin;
        private DMatrix3d oldCompassRotation;
        private AccuDraw.LockedStates oldCompassLocks;
        private DVector3d oldCompassDelta;
        private double oldCompassDistance, oldCompassAngle;
        private readonly System.Collections.Generic.Queue<System.Collections.Generic.List<Element>> frames =
            new System.Collections.Generic.Queue<System.Collections.Generic.List<Element>>();
        internal static event Action<DPoint3d> Moved;
        /// <summary>锁定事件：参数是鼠标左键点下时管线段上的投影点（UOR）。</summary>
        internal static event Action<DPoint3d> Locked;
        internal static event Action Ended;
        internal static bool IsActive
        {
            get
            {
                return active != null;
            }
        }

        private AxisSlideTool(DPoint3d anchor, DPoint3d lineStart, DPoint3d lineEnd,
            Func<DPoint3d, Element> build) : base(0, 0)
        {
            this.anchor = anchor;
            this.lineStart = lineStart;
            this.lineEnd = lineEnd;
            this.build = build;
        }

        internal static void Begin(DPoint3d anchor, DPoint3d lineStart, DPoint3d lineEnd,
            Func<DPoint3d, Element> build)
        {
            // 已有滑动工具时静默退役（不调 End）：ExitTool 挂起的"退出当前工具"会在下
            // 一个原生事件结算，误杀新装实例并触发一次伪 Ended（同 2906eca 竞态）。
            if (active != null)
                active = null;
            AxisPlacementCalculator.Unit(new[] { lineStart.X, lineStart.Y, lineStart.Z }, new[] { lineEnd.X, lineEnd.Y, lineEnd.Z });
            if (build == null)
                throw new ArgumentNullException("build");
            var tool = new AxisSlideTool(anchor, lineStart, lineEnd, build);
            active = tool;
            tool.oldSnap = AccuSnap.SnapEnabled;
            tool.oldLocate = AccuSnap.LocateEnabled;
            try
            {
                tool.InstallTool();
                AccuSnap.SnapEnabled = true;
                AccuSnap.LocateEnabled = true;
            }
            catch { active = null; tool.RestoreCompass(); AccuSnap.SnapEnabled = tool.oldSnap; AccuSnap.LocateEnabled = tool.oldLocate; throw; }
        }
        internal static void End()
        {
            var tool = active;
            if (tool == null)
                return;
            active = null;
            try
            {
                tool.ExitTool();
            }
            finally { var ended = Ended; if (ended != null) ended(); }
        }
        /// <summary>重置动态原型：下一次动态帧按新的参数在锚点重建（使用当前偏移）。</summary>
        internal static void InvalidatePrototype()
        {
            if (active != null)
            {
                active.prototype = null;
                active.shownCenter = active.anchor;
            }
        }

        /// <summary>光标点向管线段的投影（UOR），截断至两端。</summary>
        private DPoint3d Project(DPoint3d cursor)
        {
            var start = new[] { lineStart.X, lineStart.Y, lineStart.Z };
            var end = new[] { lineEnd.X, lineEnd.Y, lineEnd.Z };
            double offset = AxisPlacementCalculator.Offset(start, new[] { cursor.X, cursor.Y, cursor.Z }, start, end);
            var point = AxisPlacementCalculator.Shift(start, start, end, offset, false);
            return new DPoint3d(point[0], point[1], point[2]);
        }
        /// <summary>沿管轴方向单位向量（UOR），正分量取 +Z（竖管即向上）。</summary>
        private double[] UpUnit()
        {
            return AxisPlacementCalculator.Unit(new[] { lineStart.X, lineStart.Y, lineStart.Z },
                new[] { lineEnd.X, lineEnd.Y, lineEnd.Z });
        }
        /// <summary>
        /// 激活精确绘图罗盘并把罗盘平面定到过管轴的竖直面：X=沿管轴向上，Y=水平垂直
        /// 于管轴，Z=补全。这些标志序列复制自 A1ClampOrientationTool 的实测可用组合。
        /// </summary>
        private void ActivateCompass()
        {
            try
            {
                var u = UpUnit();
                double tx = 0, ty = 1, tz = 0;
                double dot = Math.Abs(u[0] * tx + u[1] * ty + u[2] * tz);
                if (dot > 0.9)
                {
                    tx = 1;
                    ty = 0;
                    tz = 0;
                }
                double proj = u[0] * tx + u[1] * ty + u[2] * tz;
                double vx = tx - proj * u[0], vy = ty - proj * u[1], vz = tz - proj * u[2];
                double vLen = Math.Sqrt(vx * vx + vy * vy + vz * vz);
                if (vLen <= 1.0e-12)
                    return;
                var yAxis = new DVector3d(vx / vLen, vy / vLen, vz / vLen);
                var xAxis = new DVector3d(u[0], u[1], u[2]);
                var zAxis = Cross(xAxis, yAxis);
                var rotation = DMatrix3d.FromColumns(xAxis, yAxis, zAxis);
                compassWasActive = AccuDraw.Active;
                oldCompassMode = AccuDraw.ActiveCompassMode;
                oldCompassOrigin = AccuDraw.Origin;
                oldCompassRotation = AccuDraw.Rotation;
                oldCompassLocks = AccuDraw.Locked;
                oldCompassDelta = AccuDraw.Delta;
                oldCompassDistance = AccuDraw.Distance;
                oldCompassAngle = AccuDraw.Angle;
                compassRotationMode = AccuDraw.ActiveRotationMode;
                compassActivated = true;
                AccuDraw.Active = true;
                AccuDraw.ActiveRotationMode = AccuDraw.RotationMode.Context;
                AccuDraw.ActiveCompassMode = AccuDraw.CompassMode.Rectangular;
                if (AccuDraw.SetContext(AccuDrawFlags.SetOrigin | AccuDrawFlags.FixedOrigin |
                    AccuDrawFlags.SetRMatrix | AccuDrawFlags.Set3dMatrix, anchor, rotation) != BentleyStatus.Success)
                    throw new InvalidOperationException("AccuDraw 原点或方向设置失败。");
                AccuDraw.Rotation = rotation;
                if (AccuDraw.SetContext(AccuDrawFlags.SetModeRect | AccuDrawFlags.Lock_Y |
                    AccuDrawFlags.Lock_Z | AccuDrawFlags.SetFocus | AccuDrawFlags.RedrawCompass,
                    anchor, xAxis, new DVector3d(0, 0, 0), 0, 0) != BentleyStatus.Success)
                    throw new InvalidOperationException("AccuDraw 沿轴锁定失败。");
            }
            catch (Exception ex)
            {
                RestoreCompass();
                throw new InvalidOperationException("无法启动精确沿轴定位：" + ex.Message, ex);
            }
        }
        private static DVector3d Cross(DVector3d a, DVector3d b)
        {
            return new DVector3d(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);
        }
        private void RestoreCompass()
        {
            if (!compassActivated)
                return;
            compassActivated = false;
            try
            {
                AccuDraw.SetContext(AccuDrawFlags.Disable);
                AccuDraw.Origin = oldCompassOrigin;
                AccuDraw.Rotation = oldCompassRotation;
                AccuDraw.ActiveCompassMode = oldCompassMode;
                AccuDraw.ActiveRotationMode = compassRotationMode;
                AccuDraw.Active = compassWasActive;
                if (compassWasActive)
                {
                    AccuDrawFlags locks = (AccuDrawFlags)0;
                    if ((oldCompassLocks & AccuDraw.LockedStates.X_BM) != 0)
                        locks |= AccuDrawFlags.Lock_X;
                    if ((oldCompassLocks & AccuDraw.LockedStates.Y_BM) != 0)
                        locks |= AccuDrawFlags.Lock_Y;
                    if ((oldCompassLocks & AccuDraw.LockedStates.DIST_BM) != 0)
                        locks |= AccuDrawFlags.LockDistance;
                    if ((oldCompassLocks & AccuDraw.LockedStates.ANGLE_BM) != 0)
                        locks |= AccuDrawFlags.LockAngle;
                    AccuDraw.SetContext(locks, oldCompassOrigin, new DVector3d(1, 0, 0), oldCompassDelta, oldCompassDistance, oldCompassAngle);
                }
            }
            catch { }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt("沿轴滑动：黄色十字为当前位置，蓝色十字为移动起点；X 输入位移，左键锁定，右键恢复。");
            BeginDynamics();
            // 与 A1ClampOrientationTool 同序：动态绘图起来之后再接管罗盘，否则罗盘灰色、
            // 键盘焦点也不在罗盘上，回车会被 MicroStation 当成打开 Key-in 对话框。
            ActivateCompass();
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            try
            {
                if (prototype == null)
                {
                    prototype = build(anchor);
                    shownCenter = anchor;
                }
                var target = Project(ev.Point);
                double dx = target.X - shownCenter.X, dy = target.Y - shownCenter.Y, dz = target.Z - shownCenter.Z;
                if (Math.Abs(dx) > 1.0e-9 || Math.Abs(dy) > 1.0e-9 || Math.Abs(dz) > 1.0e-9)
                {
                    // 每帧只平移动态原型，不重建几何（A1 方向工具同一性能模式）。
                    prototype.ApplyTransform(new TransformInfo(DTransform3d.FromTranslation(dx, dy, dz)));
                    shownCenter = target;
                }
                var redraw = new RedrawElems();
                redraw.SetDynamicsViewsFromActiveViewSet(Session.GetActiveViewport());
                redraw.DrawMode = DgnDrawMode.TempDraw;
                redraw.DrawPurpose = DrawPurpose.Dynamics;
                redraw.DoRedraw(prototype);
                DrawMarkers(redraw, target, ev.Point);
                var moved = Moved;
                if (moved != null)
                    moved(target);
            }
            catch (Exception ex)
            {
                prototype = null;
                NotificationManager.OutputPrompt("沿轴滑动预览失败：" + ex.Message);
            }
        }
        /// <summary>只在动态帧绘制基点、轴线和投影连线，不向模型写入辅助元素。</summary>
        private void DrawMarkers(RedrawElems redraw, DPoint3d target, DPoint3d cursor)
        {
            var model = Session.Instance.GetActiveDgnModel();
            double size = 12 * model.GetModelInfo().UorPerMeter / 1000.0;
            var lines = new System.Collections.Generic.List<Element>();
            AddLine(lines, model, lineStart, lineEnd, 1);
            CrossMarker(lines, model, anchor, size, 1);
            CrossMarker(lines, model, target, size, 4);
            if (Math.Abs(cursor.X - target.X) + Math.Abs(cursor.Y - target.Y) + Math.Abs(cursor.Z - target.Z) > 1e-6)
                AddLine(lines, model, cursor, target, 6);
            foreach (var line in lines)
                redraw.DoRedraw(line);
            frames.Enqueue(lines);
            while (frames.Count > 3)
                frames.Dequeue();
        }
        private static void CrossMarker(System.Collections.Generic.List<Element> lines, DgnModel model, DPoint3d p, double size, uint color)
        {
            AddLine(lines, model, new DPoint3d(p.X - size, p.Y, p.Z), new DPoint3d(p.X + size, p.Y, p.Z), color);
            AddLine(lines, model, new DPoint3d(p.X, p.Y - size, p.Z), new DPoint3d(p.X, p.Y + size, p.Z), color);
            AddLine(lines, model, new DPoint3d(p.X, p.Y, p.Z - size), new DPoint3d(p.X, p.Y, p.Z + size), color);
        }
        private static void AddLine(System.Collections.Generic.List<Element> lines, DgnModel model, DPoint3d a, DPoint3d b, uint color)
        {
            var line = DraftingElementSchema.ToElement(model, CurvePrimitive.CreateLine(new DSegment3d(a, b)), null);
            if (line == null)
                throw new InvalidOperationException("沿轴定位标记创建失败。");
            var style = new ElementPropertiesSetter();
            style.SetColor(color);
            style.SetWeight(2);
            style.Apply(line);
            lines.Add(line);
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var locked = Locked;
            if (locked != null)
                locked(Project(ev.Point));
            End();
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev)
        {
            End();
            return true;
        }
        protected override void OnRestartTool()
        {
            End();
        }
        protected override void OnCleanup()
        {
            RestoreCompass();
            AccuSnap.SnapEnabled = oldSnap;
            AccuSnap.LocateEnabled = oldLocate;
            frames.Clear();
            if (ReferenceEquals(active, this))
            {
                active = null;
                var ended = Ended;
                if (ended != null)
                    ended();
            }
            prototype = null;
            base.OnCleanup();
        }
    }
}
