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
            if(path==null || SectionDialog.Current==null) return;
            var chain=path.AsChainableElement();
            if(chain==null) throw new InvalidOperationException("Select an open line, arc, chain, or spline");
            Pt start=chain.StartPoint;
            double distance=Math.Min(chain.Length*0.001,Math.Max(chain.Length*0.00001,0.001));
            Pt near=chain.PointAtDistance(distance);
            if(Distance(start,near)<1e-10) throw new InvalidOperationException("Path start tangent is zero");
            var dialog=SectionDialog.Current;
            var section=GenericProfile.SweepProfile(app,dialog.Mode,start,near,dialog.Rotation);
            SmartSolidElement newSolid=app.SmartSolid.SweepProfileAlongPath(section,path);
            if(newSolid==null) throw new InvalidOperationException("SweepProfileAlongPath returned null");
            app.ActiveModelReference.AddElement(newSolid);
            if(preview!=null && preview.IsValid) app.ActiveModelReference.RemoveElement(preview);
            preview=newSolid;
            dialog.SetStatus("扫掠预览已生成。修改参数可重建。\r\n点击“确定”保留，或“取消”删除。");
        }
        private static double Distance(Pt a,Pt b)
        {
            double x=a.X-b.X,y=a.Y-b.Y,z=a.Z-b.Z;
            return Math.Sqrt(x*x+y*y+z*z);
        }
        internal static void Confirm(bool removePath)
        {
            if(preview==null) return;
            var dialog=SectionDialog.Current;
            ulong id=checked((ulong)preview.ID64);
            var elementId=new ElementId(ref id);
            var native=Session.Instance.GetActiveDgnModel().FindElementById(elementId);
            if(native==null) throw new InvalidOperationException("Cannot find swept element for statistics");
            var info=Session.Instance.GetActiveDgnModel().GetModelInfo();
            double lengthMm=path.AsChainableElement().Length*info.UorPerMaster/(info.UorPerMeter/1000.0);
            Statistics.Attach(native,dialog.Family,dialog.Profile,lengthMm);
            preview=null;
            if(removePath && path!=null && path.IsValid) app.ActiveModelReference.RemoveElement(path);
            path=null;
        }
        internal static void Cancel()
        {
            PathLocator.End();
            if(preview!=null && preview.IsValid && app!=null) app.ActiveModelReference.RemoveElement(preview);
            preview=null; path=null;
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
            app.CommandState.CommandName="Select steel sweep path";
        }
        internal static void End()
        {
            if(active==null) return;
            App app=active.app; active=null; app.CommandState.StartDefaultCommand();
        }
        public void Start() { app.ShowPrompt("Select one open path for steel sweep; Reset to cancel"); app.CommandState.EnableAccuSnap(); }
        public void LocateFilter(ComElement element,ref Pt point,ref bool accept) { accept=SweepPlacement.IsOpenPath(element); }
        public void Accept(ComElement element,ref Pt point,View view)
        {
            if(!SweepPlacement.IsOpenPath(element)) { app.ShowPrompt("Select an open path"); return; }
            try { SweepPlacement.SetPath(element); }
            catch(Exception ex) { if(SectionDialog.Current!=null) SectionDialog.Current.SetStatus("扫掠失败: "+ex.Message); app.ShowPrompt("Sweep failed: "+ex.Message); }
            app.CommandState.StartDefaultCommand();
        }
        public void LocateFailed() { app.ShowPrompt("Select an open line, arc, chain, or spline"); }
        public void LocateReset() { app.CommandState.StartDefaultCommand(); }
        public void Cleanup() { if(ReferenceEquals(active,this)) active=null; }
        public void Dynamics(ref Pt point,View view,MsdDrawingMode mode) { }
    }
}
