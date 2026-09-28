using System;
using System.Runtime.InteropServices;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.Interop.MicroStationDGN;
using App = Bentley.Interop.MicroStationDGN.Application;
using Pt = Bentley.Interop.MicroStationDGN.Point3d;
using View = Bentley.Interop.MicroStationDGN.View;
using ComElement = Bentley.Interop.MicroStationDGN.Element;

namespace SteelSectionProbe
{
    internal static class SweepPlacement
    {
        private static App app;
        private static ComElement path;
        private static SmartSolidElement preview;
        internal static bool HasPreview { get { return preview!=null; } }
        internal static void SelectPath(App application)
        {
            if(!Session.Instance.GetActiveDgnModel().Is3d)
                throw new InvalidOperationException("沿路径扫掠需要三维模型");
            Placement.End();
            Cancel();
            app=application;
            PathLocator.Begin(app);
        }
        internal static void SetPath(ComElement selected)
        {
            path=selected;
            Regenerate();
        }
        internal static void Regenerate()
        {
            if(path==null || SteelSectionPage.Current==null) return;
            var chain=path.AsChainableElement();
            if(chain==null) throw new InvalidOperationException("请选择一条开放直线、圆弧、链或样条曲线");
            Pt start=chain.StartPoint;
            double distance=Math.Min(chain.Length*0.001,Math.Max(chain.Length*0.00001,0.001));
            Pt near=chain.PointAtDistance(distance);
            if(Distance(start,near)<1e-10) throw new InvalidOperationException("路径起点切向量为零，无法生成截面");
            var dialog=SteelSectionPage.Current;
            SmartSolidElement newSolid=SteelMemberFactory.SweepAlongPath(app,dialog.Mode,start,near,dialog.Rotation,path);
            if(newSolid==null) throw new InvalidOperationException("扫掠未生成实体");
            app.ActiveModelReference.AddElement(newSolid);
            if(preview!=null && preview.IsValid) app.ActiveModelReference.RemoveElement(preview);
            preview=newSolid;
            dialog.SetStatus("扫掠预览已生成。可调整规格、基准或旋转角实时重建；确认后保留实体。",false);
            dialog.NotifyPreviewState();
        }
        private static double Distance(Pt a,Pt b)
        {
            double x=a.X-b.X,y=a.Y-b.Y,z=a.Z-b.Z;
            return Math.Sqrt(x*x+y*y+z*z);
        }
        internal static void Confirm(bool removePath)
        {
            if(preview==null) return;
            var dialog=SteelSectionPage.Current;
            ulong id=checked((ulong)preview.ID64);
            var elementId=new ElementId(ref id);
            var native=Session.Instance.GetActiveDgnModel().FindElementById(elementId);
            if(native==null) throw new InvalidOperationException("找不到扫掠实体，无法写入统计信息");
            var info=Session.Instance.GetActiveDgnModel().GetModelInfo();
            double lengthMm=path.AsChainableElement().Length*info.UorPerMaster/(info.UorPerMeter/1000.0);
            Statistics.Attach(native,dialog.Family,dialog.Profile,lengthMm);
            preview=null;
            if(removePath && path!=null && path.IsValid) app.ActiveModelReference.RemoveElement(path);
            path=null;
            if(dialog!=null) dialog.NotifyPreviewState();
        }
        internal static void Cancel()
        {
            PathLocator.End();
            if(preview!=null && preview.IsValid && app!=null) app.ActiveModelReference.RemoveElement(preview);
            preview=null; path=null;
            if(SteelSectionPage.Current!=null) SteelSectionPage.Current.NotifyPreviewState();
        }
        internal static bool IsOpenPath(ComElement element)
        {
            if(element==null) return false;
            switch(element.Type)
            {
                case MsdElementType.Line:
                case MsdElementType.LineString:
                case MsdElementType.Arc:
                case MsdElementType.Curve:
                case MsdElementType.ComplexString:
                case MsdElementType.BsplineCurve:
                    try
                    {
                        var chain=element.AsChainableElement();
                        return chain!=null && chain.Length>1e-9 && Distance(chain.StartPoint,chain.EndPoint)>1e-9;
                    }
                    catch { return false; }
                default: return false;
            }
        }
    }
    [ComVisible(true)]
    [ClassInterface(ClassInterfaceType.None)]
    public sealed class PathLocator : ILocateCommandEvents
    {
        private static PathLocator active;
        private readonly App app;
        private PathLocator(App app) { this.app=app; }
        internal static void Begin(App app)
        {
            active=new PathLocator(app);
            app.CommandState.StartLocate(active);
            app.CommandState.CommandName="选取型钢扫掠路径";
        }
        internal static void End()
        {
            if(active==null) return;
            App app=active.app; active=null; app.CommandState.StartDefaultCommand();
        }
        public void Start() { app.ShowPrompt("请在模型中选取一条开放路径用于型钢扫掠；右键重置取消"); app.CommandState.EnableAccuSnap(); }
        public void LocateFilter(ComElement element,ref Pt point,ref bool accept) { accept=SweepPlacement.IsOpenPath(element); }
        public void Accept(ComElement element,ref Pt point,View view)
        {
            if(!SweepPlacement.IsOpenPath(element)) { app.ShowPrompt("请选择一条开放路径"); return; }
            try { SweepPlacement.SetPath(element); }
            catch(Exception ex) { if(SteelSectionPage.Current!=null) SteelSectionPage.Current.SetStatus("扫掠失败："+ex.Message,true); app.ShowPrompt("扫掠失败："+ex.Message); }
            app.CommandState.StartDefaultCommand();
        }
        public void LocateFailed() { app.ShowPrompt("请选择一条开放直线、圆弧、链或样条曲线"); }
        public void LocateReset() { app.CommandState.StartDefaultCommand(); }
        public void Cleanup() { if(ReferenceEquals(active,this)) active=null; }
        public void Dynamics(ref Pt point,View view,MsdDrawingMode mode) { }
    }
}
