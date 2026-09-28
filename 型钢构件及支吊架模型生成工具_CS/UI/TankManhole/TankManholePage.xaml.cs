using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class TankManholePage : UserControl,IWorkspacePage
    {
        private bool ready,active;
        public string PageId { get { return "tank-manhole"; } }
        public string PageTitle { get { return "罐壁人孔"; } }
        public string PageSubtitle { get { return "选择规格与开盖形式，点取原点、拖动定朝向后放置"; } }
        public FrameworkElement View { get { return this; } }
        internal TankManholePage()
        {
            InitializeComponent();
            TankManholePlacementTool.Placed+=OnPlaced;
            TankManholePlacementTool.Ended+=OnEnded;
            // 记住上次选择：跨会话存 %LOCALAPPDATA%，默认 DN600 / ASA150 / 吊杆式。
            var last=TankManholeLastChoice.Load();
            DnCombo.SelectedIndex=Math.Max(0,Math.Min(2,last.DnIndex));
            PressureCombo.SelectedIndex=Math.Max(0,Math.Min(2,last.PressureIndex));
            ModeCombo.SelectedIndex=Math.Max(0,Math.Min(1,last.ModeIndex));
            NeckText.Text=last.Neck; HeadingText.Text=last.Heading;
            MirrorCheck.IsChecked=last.Mirrored; BoltsCheck.IsChecked=last.Bolts;
            LiftingCheck.IsChecked=last.Lifting;
            ready=true; UpdateSpecification();
        }
        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            active=false; TankManholePlacementTool.End();
            PreviewText.Text="尚未点取位置。";
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            TankManholePlacementTool.Placed-=OnPlaced;
            TankManholePlacementTool.Ended-=OnEnded;
        }
        private static double Number(string value,string label)
        {
            double v;
            if(!double.TryParse(value,NumberStyles.Float,CultureInfo.CurrentCulture,out v) &&
                !double.TryParse(value,NumberStyles.Float,CultureInfo.InvariantCulture,out v))
                throw new InvalidOperationException(label+"必须是有效数字。");
            return v;
        }
        private TankManholeParameters Parameters()
        {
            return new TankManholeParameters {
                NominalDn=DnCombo.SelectedIndex==0?450:DnCombo.SelectedIndex==2?600:500,
                PressureLbs=PressureCombo.SelectedIndex==1?300:PressureCombo.SelectedIndex==2?600:150,
                CoverMode=ModeCombo.SelectedIndex==1?TankCoverMode.Hinge:TankCoverMode.Davit,
                NeckLengthMm=Number(NeckText.Text,"筒节长度"),
                HeadingDegrees=Number(HeadingText.Text,"水平朝向角度"),
                Mirrored=MirrorCheck.IsChecked==true,
                IncludeBolts=BoltsCheck.IsChecked==true,
                IncludeLifting=LiftingCheck.IsChecked==true
            };
        }
        private void UpdateSpecification()
        {
            try
            {
                var p=TankManholeCalculator.Calculate(Parameters());
                SpecificationText.Text="DN"+p.Size.NominalDn+" · ASA "+p.Parameters.PressureLbs+
                    " lbs · 法兰外径 "+p.Size.FlangeOutsideMm.ToString("G")+" mm · "+
                    p.Size.BoltCount+" 孔 · "+(p.Parameters.CoverMode==TankCoverMode.Davit?"吊杆式":"铰链式");
            }
            catch(Exception ex) { SpecificationText.Text=ex.Message; }
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            SaveLastChoice();
            UpdateSpecification();
            TankManholePlacementTool.InvalidatePrototype();
        }
        private void SaveLastChoice()
        {
            TankManholeLastChoice.Save(new TankManholeLastChoice.Data {
                DnIndex=DnCombo.SelectedIndex,PressureIndex=PressureCombo.SelectedIndex,
                ModeIndex=ModeCombo.SelectedIndex,Neck=NeckText.Text,Heading=HeadingText.Text,
                Mirrored=MirrorCheck.IsChecked==true,Bolts=BoltsCheck.IsChecked==true,
                Lifting=LiftingCheck.IsChecked==true });
        }
        /// <summary>构建动态预览单元：origin 为放置原点、headingRadians 为当前朝向（不入模）。</summary>
        private Element BuildPrototypeCell(DPoint3d origin,double headingRadians)
        {
            var parameters=Parameters();
            parameters.HeadingDegrees=headingRadians*180.0/Math.PI;
            var model=Session.Instance.GetActiveDgnModel();
            var parts=TankManholeBuilder.Build(TankManholeCalculator.Calculate(parameters),origin);
            return new CellHeaderElement(model,"TANK_WALL_MANHOLE",origin,DMatrix3d.Identity,parts);
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                TankManholeCalculator.Calculate(Parameters());
                double headingRadians=Number(HeadingText.Text,"水平朝向角度")*Math.PI/180.0;
                TankManholePlacementTool.Begin(BuildPrototypeCell,headingRadians);
                PreviewText.Text="① 移动光标预览位置，左键定原点；② 再移动调整朝向，再次左键放置。右键取消。";
                SetStatus("点取中：可配合精确绘图键入距离与角度。",false);
            }
            catch(Exception ex) { SetStatus("无法开始点取："+ex.Message,true); }
        }
        private void OnPlaced(DPoint3d origin,double headingDegrees)
        {
            if(!active) return;
            HeadingText.Text=headingDegrees.ToString("0.#");
            SaveLastChoice();
            PreviewText.Text="已放置人孔（朝向 "+headingDegrees.ToString("0.#")+"°）。可再次点取位置放置下一处。";
            SetStatus("罐壁人孔已放置。",false);
        }
        private void OnEnded()
        {
            if(!active) return;
            PreviewText.Text="已结束点取。";
            SetStatus("已结束点取。",false);
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {
            TankManholePlacementTool.End();
        }
        private static void SetStatus(string message,bool error)
        { if(MainWindow.Current!=null) MainWindow.Current.SetStatus(message,error); }
    }
}
