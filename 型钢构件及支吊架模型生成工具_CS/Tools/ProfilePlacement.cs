using System;
using System.Runtime.InteropServices;
using Bentley.DgnPlatformNET.Elements;
using Bentley.Interop.MicroStationDGN;
using Bentley.MstnPlatformNET;
using App = Bentley.Interop.MicroStationDGN.Application;
using DgnElement = Bentley.DgnPlatformNET.Elements.Element;
using Pt = Bentley.Interop.MicroStationDGN.Point3d;
using View = Bentley.Interop.MicroStationDGN.View;

namespace SteelSectionProbe
{
    [ComVisible(true)]
    [ClassInterface(ClassInterfaceType.None)]
    public sealed class Placement : IPrimitiveCommandEvents
    {
        private static Placement active;
        private readonly App app;
        private readonly FamilyData family;
        private readonly ProfileData profile;
        private readonly ModeData mode;

        private Placement(App app, FamilyData family, ProfileData profile, ModeData mode)
        {
            this.app = app;
            this.family = family;
            this.profile = profile;
            this.mode = mode;
        }

        internal static bool IsActive { get { return active != null; } }

        internal static void Begin(App app, FamilyData family, ProfileData profile, ModeData mode)
        {
            End();
            active = new Placement(app, family, profile, mode);
            app.CommandState.StartPrimitive(active, false);
            app.CommandState.CommandName = "放置 " + family.Label + " " + profile.Name;
        }

        internal static void End()
        {
            if (active == null) return;
            App currentApp = active.app;
            active = null;
            currentApp.CommandState.StartDefaultCommand();
        }

        public void Start()
        {
            app.ShowPrompt("指定 " + family.Label + " " + profile.Name + " 的插入点；左键确定预览，右键重置结束");
            app.CommandState.EnableAccuSnap();
            app.CommandState.StartDynamics();
        }

        public void DataPoint(ref Pt point, View view)
        {
            try
            {
                var info = Session.Instance.GetActiveDgnModel().GetModelInfo();
                DgnElement shape = GenericProfile.Native(
                    mode,
                    point.X * info.UorPerMaster,
                    point.Y * info.UorPerMaster,
                    point.Z * info.UorPerMaster,
                    info.UorPerMeter / 1000.0);
                if (shape == null) throw new InvalidOperationException("截面元素创建失败");
                shape.AddToModel();
                app.ShowPrompt(profile.Name + " 已放置；继续点取或右键重置结束");
                if (SteelSectionPage.Current != null)
                    SteelSectionPage.Current.SetStatus("已放置 " + profile.Name + "。可继续点取，右键重置结束。", false);
            }
            catch (Exception ex)
            {
                app.ShowPrompt("型钢生成：" + ex.Message);
                if (SteelSectionPage.Current != null)
                    SteelSectionPage.Current.SetStatus(ex.Message, true);
            }
        }

        public void Dynamics(ref Pt point, View view, MsdDrawingMode drawMode)
        {
            try
            {
                GenericProfile.Preview(app, mode, point).Redraw(drawMode);
            }
            catch (Exception ex)
            {
                if (SteelSectionPage.Current != null)
                    SteelSectionPage.Current.SetStatus("预览失败：" + ex.Message, true);
            }
        }

        public void Reset() { End(); }
        public void Cleanup() { if (ReferenceEquals(active, this)) active = null; }
        public void Keyin(string keyin) { }
    }
}
