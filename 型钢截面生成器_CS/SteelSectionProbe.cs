using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.Interop.MicroStationDGN;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.WinForms;
using App = Bentley.Interop.MicroStationDGN.Application;
using Pt = Bentley.Interop.MicroStationDGN.Point3d;
using DgnElement = Bentley.DgnPlatformNET.Elements.Element;
using View = Bentley.Interop.MicroStationDGN.View;
using ComplexShapeElement = Bentley.Interop.MicroStationDGN.ComplexShapeElement;

namespace SteelSectionProbe
{
    [AddInAttribute(MdlTaskID = "SteelSectionProbe")]
    public sealed class SteelSectionProbe : AddIn
    {
        internal static SteelSectionProbe Instance;
        private SteelSectionProbe(IntPtr descriptor) : base(descriptor) { Instance = this; }
        protected override int Run(string[] args) { return 0; }
    }
    public static class Keyins
    {
        public static void Show(string args) { SectionDialog.ShowWindow(); }
        public static void Place(string args) { SectionDialog.ShowWindow(); SectionDialog.Current.Place(); }
    }
    internal sealed class SectionDialog : Adapter
    {
        internal static SectionDialog Current;
        private readonly ComboBox families = new ComboBox();
        private readonly ComboBox sizes = new ComboBox();
        private readonly ComboBox anchors = new ComboBox();
        private readonly NumericUpDown rotation = new NumericUpDown();
        private readonly CheckBox deletePath = new CheckBox();
        private readonly TextBox dimensions = new TextBox();
        private readonly Label status = new Label();
        internal ModeData Mode { get { return (ModeData)anchors.SelectedItem; } }
        internal FamilyData Family { get { return (FamilyData)families.SelectedItem; } }
        internal ProfileData Profile { get { return (ProfileData)sizes.SelectedItem; } }
        internal double Rotation { get { return (double)rotation.Value; } }
        internal static void ShowWindow()
        {
            if (Current == null || Current.IsDisposed) Current = new SectionDialog();
            if (!Current.Visible) Current.Show();
            Current.Activate();
        }
        private SectionDialog()
        {
            Text="型钢截面生成器"; Width=340; Height=475;
            FormBorderStyle=FormBorderStyle.FixedToolWindow; MaximizeBox=false;
            this.AttachAsTopLevelForm(SteelSectionProbe.Instance,true);
            this.NETDockable=false;
            var familyLabel=new Label { Text="型钢类型",Left=16,Top=18,Width=62 };
            families.Left=82; families.Top=15; families.Width=210; families.DropDownStyle=ComboBoxStyle.DropDownList;
            families.Items.AddRange(RuntimeData.Families);
            var sizeLabel=new Label { Text="规格",Left=16,Top=54,Width=62 };
            sizes.Left=82; sizes.Top=51; sizes.Width=210; sizes.DropDownStyle=ComboBoxStyle.DropDownList;
            var anchorLabel=new Label { Text="插入基准",Left=16,Top=90,Width=64 };
            anchors.Left=82; anchors.Top=87; anchors.Width=210; anchors.DropDownStyle=ComboBoxStyle.DropDownList;
            var button=new Button { Text="在视图中放置截面",Left=82,Top=125,Width=210 };
            button.Click+=(s,e)=>Place();
            var sweep=new Button { Text="选取路径并扫掠",Left=82,Top=158,Width=210 };
            sweep.Click+=(s,e)=>SelectSweepPath();
            var rotationLabel=new Label { Text="旋转角度",Left=16,Top=197,Width=64 };
            rotation.Left=82; rotation.Top=194; rotation.Width=75; rotation.Minimum=-360; rotation.Maximum=360;
            rotation.ValueChanged+=(s,e)=>Restart();
            deletePath.Text="确认后删除源路径"; deletePath.Left=165; deletePath.Top=195; deletePath.Width=145;
            var confirm=new Button { Text="确定扫掠",Left=82,Top=225,Width=100 };
            var cancel=new Button { Text="取消预览",Left=192,Top=225,Width=100 };
            confirm.Click+=(s,e)=>ConfirmSweep(); cancel.Click+=(s,e)=>CancelSweep();
            var detailLabel=new Label { Text="截面参数（mm；面积和重量见规格表）",Left=16,Top=265,Width=310 };
            dimensions.Left=16; dimensions.Top=285; dimensions.Width=296; dimensions.Height=105;
            dimensions.Multiline=true; dimensions.ReadOnly=true; dimensions.ScrollBars=ScrollBars.Vertical;
            status.Left=16; status.Top=401; status.Width=300; status.Height=42;
            status.Text="选择规格和基准，点击放置。\r\n右键 Reset 退出点取。";
            Controls.AddRange(new Control[]{familyLabel,families,sizeLabel,sizes,anchorLabel,anchors,
                button,sweep,rotationLabel,rotation,deletePath,confirm,cancel,detailLabel,dimensions,status});
            families.SelectedIndexChanged+=(s,e)=>SelectFamily();
            sizes.SelectedIndexChanged+=(s,e)=>SelectProfile();
            anchors.SelectedIndexChanged+=(s,e)=>Restart();
            FormClosed+=(s,e)=>{ Placement.End(); SweepPlacement.Cancel(); Current=null; };
            families.SelectedIndex=0;
        }
        private void SelectFamily()
        {
            FamilyData family=(FamilyData)families.SelectedItem;
            sizes.Items.Clear();
            sizes.Items.AddRange(family.Profiles);
            int defaultIndex=0;
            for(int i=0;i<family.Profiles.Length;i++)
                if(family.Profiles[i].Name=="20a" || (family.Id=="equal_angle" && family.Profiles[i].Name=="L50x50x5") ||
                   (family.Id=="unequal_angle" && family.Profiles[i].Name=="L63x40x5") ||
                   (family.Id=="hot_rolled_h" && family.Profiles[i].Name=="H200x200x8x12xr13") ||
                   (family.Id=="hk_section" && family.Profiles[i].Name.StartsWith("HK100x100"))) { defaultIndex=i; break; }
            sizes.SelectedIndex=defaultIndex;
        }
        private void SelectProfile()
        {
            ProfileData profile=(ProfileData)sizes.SelectedItem;
            anchors.Items.Clear();
            if(profile==null) return;
            anchors.Items.AddRange(profile.Modes);
            anchors.SelectedIndex=0;
            var detail=new StringBuilder();
            foreach(var pair in profile.Dimensions)
                detail.Append(pair.Key).Append(" = ").Append(pair.Value.ToString("G",System.Globalization.CultureInfo.InvariantCulture))
                    .AppendLine(pair.Key=="mass" ? " kg/m" : (pair.Key=="area" || pair.Key=="A" ? " cm²" : (pair.Key.EndsWith("_cm") ? " cm" : " mm")));
            dimensions.Text=detail.ToString();
        }
        private void Restart()
        {
            if(sizes.SelectedItem==null || anchors.SelectedItem==null) return;
            if (Placement.IsActive) Place();
            else if(SweepPlacement.HasPreview)
                try { SweepPlacement.Regenerate(); } catch(Exception ex) { SetStatus("重建预览失败: "+ex.Message); }
        }
        private void SelectSweepPath()
        {
            App app=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if(app==null || !app.HasActiveModelReference) { SetStatus("请先打开 DGN 模型。"); return; }
            try { SweepPlacement.SelectPath(app); SetStatus("请在模型中选择一条开放路径。"); }
            catch(Exception ex) { SetStatus(ex.Message); }
        }
        private void ConfirmSweep()
        {
            if(!SweepPlacement.HasPreview) { SetStatus("尚无扫掠预览。"); return; }
            try { SweepPlacement.Confirm(deletePath.Checked); SetStatus("扫掠实体已保留。"); }
            catch(Exception ex) { SetStatus(ex.Message); }
        }
        private void CancelSweep() { SweepPlacement.Cancel(); SetStatus("已取消扫掠预览。"); }
        internal void Place()
        {
            App app=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if (app==null || !app.HasActiveModelReference) { SetStatus("请先打开 DGN 模型。"); return; }
            try
            {
                SweepPlacement.Cancel();
                ProfileData profile=(ProfileData)sizes.SelectedItem;
                Placement.Begin(app,(FamilyData)families.SelectedItem,profile,(ModeData)anchors.SelectedItem);
                SetStatus("在视图中指定位置。\r\n支持 AccuSnap 与 AccuDraw。");
            }
            catch (Exception ex) { SetStatus(ex.Message); }
        }
        internal void SetStatus(string message) { if (!IsDisposed) status.Text=message; }
    }
    [ComVisible(true)]
    [ClassInterface(ClassInterfaceType.None)]
    public sealed class Placement : IPrimitiveCommandEvents
    {
        private static Placement active;
        private readonly App app;
        private readonly FamilyData family;
        private readonly ProfileData profile;
        private readonly ModeData mode;
        private Placement(App app,FamilyData family,ProfileData profile,ModeData mode)
        { this.app=app; this.family=family; this.profile=profile; this.mode=mode; }
        internal static bool IsActive { get { return active!=null; } }
        internal static void Begin(App app,FamilyData family,ProfileData profile,ModeData mode)
        {
            End(); active=new Placement(app,family,profile,mode);
            app.CommandState.StartPrimitive(active,false);
            app.CommandState.CommandName="Place "+family.Label+" "+profile.Name;
        }
        internal static void End()
        {
            if (active==null) return;
            App app=active.app; active=null; app.CommandState.StartDefaultCommand();
        }
        public void Start()
        {
            app.ShowPrompt("Pick insertion point for "+family.Label+" "+profile.Name+"; Reset to finish");
            app.CommandState.EnableAccuSnap();
            app.CommandState.StartDynamics();
        }
        public void DataPoint(ref Pt point,View view)
        {
            try
            {
                var info=Session.Instance.GetActiveDgnModel().GetModelInfo();
                double uorPerMaster=info.UorPerMaster;
                DgnElement shape=GenericProfile.Native(mode,
                    point.X*uorPerMaster,point.Y*uorPerMaster,point.Z*uorPerMaster,
                    info.UorPerMeter/1000.0);
                if (shape==null) throw new InvalidOperationException("截面元素创建失败");
                shape.AddToModel();
                app.ShowPrompt(profile.Name+" placed; pick another point or Reset");
                if (SectionDialog.Current!=null) SectionDialog.Current.SetStatus("已放置 "+profile.Name+"。\r\n继续点取或右键 Reset。");
            }
            catch (Exception ex) { app.ShowPrompt("SteelSectionProbe: "+ex.Message); if (SectionDialog.Current!=null) SectionDialog.Current.SetStatus(ex.Message); }
        }
        public void Dynamics(ref Pt point,View view,MsdDrawingMode drawMode)
        {
            try { GenericProfile.Preview(app,mode,point).Redraw(drawMode); }
            catch (Exception ex) { if (SectionDialog.Current!=null) SectionDialog.Current.SetStatus("预览失败: "+ex.Message); }
        }
        public void Reset() { End(); }
        public void Cleanup() { if (ReferenceEquals(active,this)) active=null; }
        public void Keyin(string keyin) { }
    }
}
