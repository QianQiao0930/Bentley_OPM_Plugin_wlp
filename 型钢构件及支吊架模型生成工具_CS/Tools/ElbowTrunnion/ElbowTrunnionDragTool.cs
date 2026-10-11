using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Measures H or L from the AccuDraw constrained model point; dynamic frames draw only temporary lines.</summary>
    internal sealed class ElbowTrunnionDragTool : DgnPrimitiveTool
    {
        private static ElbowTrunnionDragTool active;
        private static bool oldSnap, oldLocate;
        private readonly ElbowTrunnionSelection selection;
        private ElbowTrunnionParameters parameters;
        private readonly int pickView;
        private readonly double pickX, pickY;
        private readonly Queue<List<Element>> frames=new Queue<List<Element>>();
        private bool pickReleased,acceptArmed,hasFrame;
        private DateTime lastUpdate=DateTime.MinValue;
        private string lastError;
        private bool compassActivated;
        private AccuDraw.RotationMode compassRotationMode;
        private bool compassWasActive;
        private AccuDraw.CompassMode oldCompassMode;
        private DPoint3d oldCompassOrigin;
        private DMatrix3d oldCompassRotation;

        [DllImport("user32.dll")]
        private static extern short GetAsyncKeyState(int key);

        internal static event Action<double> LengthChanged;
        internal static event Action<double> Accepted;
        internal static event Action Cancelled;
        internal static event Action<string> Failed;
        internal static bool IsActive { get { return active!=null; } }

        private ElbowTrunnionDragTool(ElbowTrunnionSelection selected,
            ElbowTrunnionParameters options,int view,double x,double y) : base(0,0)
        {
            selection=selected; parameters=options; pickView=view; pickX=x; pickY=y;
        }
        internal static void Begin(ElbowTrunnionSelection selected,
            ElbowTrunnionParameters options,int view,double x,double y)
        {
            End();
            var tool=new ElbowTrunnionDragTool(selected,options,view,x,y);
            oldSnap=AccuSnap.SnapEnabled;
            oldLocate=AccuSnap.LocateEnabled;
            active=tool;
            try
            {
                tool.InstallTool();
                AccuSnap.SnapEnabled=true;
                AccuSnap.LocateEnabled=true;
                tool.BeginDynamics();
                if (!tool.DynamicsStarted)
                    throw new InvalidOperationException("Bentley 拉伸动态绘制未启动。");
                // 与 A1 方向工具同序：动态起来之后再接管罗盘（原点固定在测量基准点，
                // X 轴=拉伸方向），罗盘键盘输入才接收焦点。
                tool.ActivateCompass();
            }
            catch
            {
                End();
                throw;
            }
        }
        internal static void UpdateParameters(ElbowTrunnionParameters options)
        {
            if (active!=null)
            {
                active.parameters=options;
                active.ConfigureCompass();
            }
        }
        internal static void End()
        {
            var tool=active;
            if (tool==null) return;
            active=null;
            try { tool.ExitTool(); }
            finally
            {
                AccuSnap.SnapEnabled=oldSnap;
                AccuSnap.LocateEnabled=oldLocate;
                tool.frames.Clear();
            }
        }
        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            NotificationManager.OutputPrompt(
                "松开左键，沿耳轴方向移动鼠标预览长度；再左键固定，右键取消。"
                +"罗盘已对齐拉伸方向：键盘输入距离回车后左键，即按该距离精确落位。");
        }
        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            try
            {
                double extent=ClampedExtent(ev);
                var plan=Plan(extent);
                int view=ev.ViewNumber;
                var vp=ev.ViewPoint;
                bool moved=Moved(view,vp.X,vp.Y);
                bool released=(GetAsyncKeyState(0x01)&0x8000)==0;
                if (released) pickReleased=true;
                if (pickReleased && (moved || HasDistanceInput())) acceptArmed=true;
                Draw(plan,ev.Viewport);
                hasFrame=true;
                if ((DateTime.UtcNow-lastUpdate).TotalMilliseconds>=60)
                {
                    lastUpdate=DateTime.UtcNow;
                    var handler=LengthChanged;
                    if (handler!=null) handler(extent);
                }
                lastError=null;
            }
            catch(Exception ex)
            {
                hasFrame=false;
                acceptArmed=false;
                if (lastError!=ex.Message)
                {
                    lastError=ex.Message;
                    var handler=Failed;
                    if (handler!=null) handler("拉伸预览失败："+ex.Message);
                }
            }
        }
        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            var vp=ev.ViewPoint;
            if (!hasFrame || !pickReleased || !acceptArmed ||
                (!Moved(ev.ViewNumber,vp.X,vp.Y) && !HasDistanceInput()))
            {
                var failed=Failed;
                if (failed!=null) failed("请先松开点选弯头的左键，移动鼠标预览长度，再左键固定。");
                return false;
            }
            try
            {
                double extent=ClampedExtent(ev);
                Plan(extent);
                End();
                var accepted=Accepted;
                if (accepted!=null) accepted(extent);
            }
            catch(Exception ex)
            {
                var failed=Failed;
                if (failed!=null) failed("无法读取拉伸长度："+ex.Message);
            }
            return true;
        }
        protected override bool OnResetButton(DgnButtonEvent ev)
        {
            End();
            var cancelled=Cancelled;
            if (cancelled!=null) cancelled();
            return true;
        }
        protected override void OnRestartTool() { End(); }
        protected override void OnCleanup()
        {
            RestoreCompass();
            if (ReferenceEquals(active,this))
            {
                active=null;
                AccuSnap.SnapEnabled=oldSnap;
                AccuSnap.LocateEnabled=oldLocate;
                frames.Clear();
                var cancelled=Cancelled;
                if (cancelled!=null) cancelled();
            }
            base.OnCleanup();
        }

        private static bool HasDistanceInput()
        {
            return (AccuDraw.Locked & (AccuDraw.LockedStates.X_BM|
                AccuDraw.LockedStates.DIST_BM))!=AccuDraw.LockedStates.None;
        }
        private bool Moved(int view,double x,double y)
        {
            if (view!=pickView) return true;
            double dx=x-pickX,dy=y-pickY;
            return dx*dx+dy*dy>25;
        }
        private double ClampedExtent(DgnButtonEvent ev)
        {
            double raw=ExtentFromEvent(ev);
            if (double.IsNaN(raw) || double.IsInfinity(raw))
                throw new InvalidOperationException("光标长度无效。");
            var size=ElbowTrunnionCatalog.ForMainDn(selection.MainDn);
            double plate=parameters.Trunnion==TrunnionOrientation.Vertical
                ? (parameters.Plate=='C' ? 0 : size.PlateThicknessMm)
                : ElbowTrunnionCatalog.EndPlateThickness(size.Dn,parameters.Plate);
            double minimum=parameters.Trunnion==TrunnionOrientation.Vertical
                ? Math.Max(50,selection.OutsideDiameterMm/2+plate+(parameters.Ptfe?3:0)+1)
                : selection.OutsideDiameterMm/2+size.OutsideMm+plate+21;
            return Math.Max(minimum,Math.Min(20000,raw));
        }
        private double ExtentFromEvent(DgnButtonEvent ev)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if (model==null) throw new InvalidOperationException("没有活动模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            if (scale<=0) throw new InvalidOperationException("模型单位无效。");
            VectorMm origin,direction;
            Axis(out origin,out direction);
            // ev.Point is the model point adjusted by Bentley snapping/AccuDraw.
            // Never infer a real height from a screen-space projection or RawPoint.
            var point=ev.Point;
            return ElbowTrunnionCalculator.ExtentFromModelPoint(origin,direction,
                new VectorMm(point.X/scale,point.Y/scale,point.Z/scale));
        }
        private void Axis(out VectorMm origin,out VectorMm direction)
        {
            var f=selection.Frame;
            if (parameters.Trunnion==TrunnionOrientation.Vertical)
            {
                origin=new VectorMm(f.VerticalPort.X,f.VerticalPort.Y,f.HorizontalPort.Z);
                direction=new VectorMm(0,0,-1);
            }
            else if (parameters.Elbow==ElbowOrientation.Vertical)
            {
                origin=new VectorMm(f.VerticalPort.X,f.VerticalPort.Y,f.HorizontalPort.Z);
                direction=f.HorizontalDirection;
            }
            else
            {
                origin=f.RunPort+f.AxisX*f.RunLengthMm;
                direction=parameters.OutletSide ? f.AxisZ*(-1) : f.AxisX;
            }
            if (parameters.Trunnion==TrunnionOrientation.Horizontal && parameters.BottomFlat)
            {
                var size=ElbowTrunnionCatalog.ForMainDn(selection.MainDn);
                origin=new VectorMm(origin.X,origin.Y,
                    origin.Z-(selection.OutsideDiameterMm-size.OutsideMm)/2);
            }
        }
        /// <summary>
        /// 激活精确绘图罗盘：原点固定在测量基准点，X 轴=拉伸方向（输入正距离即沿拉伸
        /// 方向），Y 取与拉伸方向夹角最小可控的水平横向参考，Z 补全右手系。标志序列
        /// 锁定横向 Y/Z，X 沿耳轴方向；定向失败中止拉伸。
        /// </summary>
        private void ActivateCompass()
        {
            try
            {
                compassWasActive=AccuDraw.Active;
                oldCompassMode=AccuDraw.ActiveCompassMode;
                oldCompassOrigin=AccuDraw.Origin;
                oldCompassRotation=AccuDraw.Rotation;
                compassRotationMode=AccuDraw.ActiveRotationMode;
                compassActivated=true;
                ConfigureCompass();
            }
            catch(Exception ex)
            {
                RestoreCompass();
                throw new InvalidOperationException("无法锁定 AccuDraw 耳轴方向："+ex.Message,ex);
            }
        }
        private void ConfigureCompass()
        {
            var model=Session.Instance.GetActiveDgnModel();
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            VectorMm origin,direction;
            Axis(out origin,out direction);
            var x=direction.Unit();
            var reference=Math.Abs(x.Y)>0.9 ? new VectorMm(1,0,0) : new VectorMm(0,1,0);
            var y=(reference-x*reference.Dot(x)).Unit();
            var z=new DVector3d(x.Y*y.Z-x.Z*y.Y,x.Z*y.X-x.X*y.Z,x.X*y.Y-x.Y*y.X);
            var rotation=DMatrix3d.FromColumns(new DVector3d(x.X,x.Y,x.Z),new DVector3d(y.X,y.Y,y.Z),z);
            var anchor=Point(origin,scale);
            AccuDraw.Active=true;
            AccuDraw.ActiveRotationMode=AccuDraw.RotationMode.Context;
            AccuDraw.ActiveCompassMode=AccuDraw.CompassMode.Rectangular;
            if (AccuDraw.SetContext(AccuDrawFlags.SetOrigin|AccuDrawFlags.FixedOrigin|
                AccuDrawFlags.SetRMatrix|AccuDrawFlags.Set3dMatrix,anchor,rotation)!=BentleyStatus.Success)
                throw new InvalidOperationException("AccuDraw 原点或方向设置失败。");
            AccuDraw.Rotation=rotation;
            // X is the ear axis. Lock the two transverse coordinates at zero.
            if (AccuDraw.SetContext(AccuDrawFlags.SetModeRect|AccuDrawFlags.Lock_Y|
                AccuDrawFlags.Lock_Z|AccuDrawFlags.SetFocus|AccuDrawFlags.RedrawCompass,
                anchor,new DVector3d(x.X,x.Y,x.Z),new DVector3d(0,0,0),0,0)!=BentleyStatus.Success)
                throw new InvalidOperationException("AccuDraw 轴向锁定失败。");
        }
        private void RestoreCompass()
        {
            if (!compassActivated) return;
            compassActivated=false;
            try
            {
                AccuDraw.Origin=oldCompassOrigin;
                AccuDraw.Rotation=oldCompassRotation;
                AccuDraw.ActiveCompassMode=oldCompassMode;
                AccuDraw.ActiveRotationMode=compassRotationMode;
                AccuDraw.Active=compassWasActive;
            }
            catch { }
        }
        private ElbowTrunnionPlan Plan(double extent)
        {
            parameters.ExtentMm=extent;
            return ElbowTrunnionCalculator.Calculate(selection,parameters);
        }
        private void Draw(ElbowTrunnionPlan plan,Viewport viewport)
        {
            var model=Session.Instance.GetActiveDgnModel();
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var lines=new List<Element>();
            var radius=plan.TrunnionOdMm/2;
            var direction=plan.Direction;
            VectorMm side=plan.Parameters.Trunnion==TrunnionOrientation.Vertical
                ? new VectorMm(-selection.Frame.HorizontalDirection.Y,
                    selection.Frame.HorizontalDirection.X,0)
                : new VectorMm(-direction.Y,direction.X,0);
            side=side.Unit();
            AddLine(lines,plan.TubeStartMm,plan.TubeEndMm,scale,model);
            AddLine(lines,plan.TubeStartMm+side*radius,plan.TubeEndMm+side*radius,scale,model);
            AddLine(lines,plan.TubeStartMm-side*radius,plan.TubeEndMm-side*radius,scale,model);
            if (plan.PlateThicknessMm>0)
            {
                double plateRadius=plan.Parameters.Trunnion==TrunnionOrientation.Vertical &&
                    plan.Parameters.Plate=='A' ? plan.PlateSizeMm/2 : (plan.TrunnionOdMm+25)/2;
                AddLine(lines,plan.PlateStartMm+side*plateRadius,
                    plan.PlateEndMm+side*plateRadius,scale,model);
                AddLine(lines,plan.PlateStartMm-side*plateRadius,
                    plan.PlateEndMm-side*plateRadius,scale,model);
                AddLine(lines,plan.PlateEndMm+side*plateRadius,
                    plan.PlateEndMm-side*plateRadius,scale,model);
            }
            var redraw=new RedrawElems();
            redraw.SetDynamicsViewsFromActiveViewSet(viewport);
            redraw.DrawMode=DgnDrawMode.TempDraw;
            redraw.DrawPurpose=DrawPurpose.Dynamics;
            foreach(var element in lines) redraw.DoRedraw(element);
            frames.Enqueue(lines);
            while(frames.Count>3) frames.Dequeue();
        }
        private static void AddLine(List<Element> lines,VectorMm start,VectorMm end,
            double scale,DgnModel model)
        {
            var segment=new DSegment3d(Point(start,scale),Point(end,scale));
            var element=DraftingElementSchema.ToElement(model,CurvePrimitive.CreateLine(segment),null);
            if (element==null) throw new InvalidOperationException("无法绘制耳轴动态轮廓。");
            lines.Add(element);
        }
        private static DPoint3d Point(VectorMm point,double scale)
        {
            return new DPoint3d(point.X*scale,point.Y*scale,point.Z*scale);
        }
    }
}

