using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class ElbowTrunnionPage : UserControl, IWorkspacePage
    {
        private readonly ElbowTrunnionPreviewSession preview=new ElbowTrunnionPreviewSession();
        private ElbowTrunnionSelection selection;
        private bool ready,active;
        private int pickVersion;
        public string PageId { get { return "elbow-trunnion"; } }
        public string PageTitle { get { return "弯头耳轴"; } }
        public string PageSubtitle { get { return "选择方向，点选弯头，拉伸取长并确认生成"; } }
        public FrameworkElement View { get { return this; } }

        internal ElbowTrunnionPage()
        {
            InitializeComponent();
            ElbowTrunnionLocateTool.Picked+=OnPicked;
            ElbowTrunnionLocateTool.Ended+=OnPickEnded;
            ElbowTrunnionDragTool.LengthChanged+=OnDragLengthChanged;
            ElbowTrunnionDragTool.Accepted+=OnDragAccepted;
            ElbowTrunnionDragTool.Cancelled+=OnDragCancelled;
            ElbowTrunnionDragTool.Failed+=OnDragFailed;
            ElbowCombo.SelectedIndex=0;
            TrunnionCombo.SelectedIndex=0;
            PlateCombo.SelectedIndex=0;
            MaterialCombo.SelectedIndex=0;
            NamingUnitCombo.SelectedIndex=0;
            ready=true;
            UpdateVariant();
        }
        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            active=false;
            pickVersion++;
            ElbowTrunnionLocateTool.End();
            ElbowTrunnionDragTool.End();
            try { preview.Cancel(); }
            catch(Exception ex) { SetStatus(ex.Message,true); }
            selection=null;
            SelectionText.Text="尚未选择弯头。";
            LiveLengthText.Text="";
            PlanText.Text="";
            ConfirmButton.IsEnabled=false;
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            ElbowTrunnionLocateTool.Picked-=OnPicked;
            ElbowTrunnionLocateTool.Ended-=OnPickEnded;
            ElbowTrunnionDragTool.LengthChanged-=OnDragLengthChanged;
            ElbowTrunnionDragTool.Accepted-=OnDragAccepted;
            ElbowTrunnionDragTool.Cancelled-=OnDragCancelled;
            ElbowTrunnionDragTool.Failed-=OnDragFailed;
        }
        private void Variant_Changed(object sender,SelectionChangedEventArgs e)
        {
            if (!ready) return;
            pickVersion++;
            ElbowTrunnionLocateTool.End();
            ElbowTrunnionDragTool.End();
            try { preview.Cancel(); }
            catch(Exception ex) { SetStatus(ex.Message,true); }
            selection=null;
            SelectionText.Text="尚未选择弯头。";
            LiveLengthText.Text="";
            PlanText.Text="";
            ConfirmButton.IsEnabled=false;
            UpdateVariant();
        }
        private void UpdateVariant()
        {
            bool vertical=TrunnionCombo.SelectedIndex==0;
            bool horizontalElbow=ElbowCombo.SelectedIndex==1;
            VariantText.Text=(horizontalElbow?"水平弯头":"竖直弯头")+" · "+
                (vertical?"竖直耳轴（F2）":horizontalElbow?"水平耳轴（F5）":"水平耳轴（F4）");
            ExtentLabel.Text=vertical?"高度 H（mm）":"长度 L（mm）";
            PlateLabel.Text=vertical?"底板类型":"端板类型";
            ((ComboBoxItem)PlateCombo.Items[0]).Content=vertical?"A 方形底板":"A 6 mm 端板";
            ((ComboBoxItem)PlateCombo.Items[1]).Content=vertical?"B 圆形底板":"B 表 2 端板";
            ((ComboBoxItem)PlateCombo.Items[2]).Content=vertical?"C 无底板":"C 无端板";
            PtfeCheck.Visibility=vertical?Visibility.Visible:Visibility.Collapsed;
            FlatCheck.Visibility=vertical?Visibility.Collapsed:Visibility.Visible;
            OutletCheck.Visibility=horizontalElbow && !vertical?Visibility.Visible:Visibility.Collapsed;
        }
        private ElbowTrunnionParameters Parameters()
        {
            double extent,wall;
            if (!double.TryParse(ExtentText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out extent) &&
                !double.TryParse(ExtentText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out extent))
                throw new InvalidOperationException("请输入有效的高度 H 或长度 L。");
            double? overrideWall=null;
            if (!string.IsNullOrWhiteSpace(WallText.Text))
            {
                if (!double.TryParse(WallText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out wall) &&
                    !double.TryParse(WallText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out wall))
                    throw new InvalidOperationException("自定义耳轴壁厚不是有效数字。");
                overrideWall=wall;
            }
            return new ElbowTrunnionParameters {
                Elbow=ElbowCombo.SelectedIndex==0?ElbowOrientation.Vertical:ElbowOrientation.Horizontal,
                Trunnion=TrunnionCombo.SelectedIndex==0?TrunnionOrientation.Vertical:TrunnionOrientation.Horizontal,
                ExtentMm=extent,Plate=(char)('A'+PlateCombo.SelectedIndex),
                Hollow=HollowCheck.IsChecked==true,Ptfe=PtfeCheck.IsChecked==true &&
                    TrunnionCombo.SelectedIndex==0,
                BottomFlat=FlatCheck.IsChecked==true && TrunnionCombo.SelectedIndex==1,
                OutletSide=OutletCheck.IsChecked==true && ElbowCombo.SelectedIndex==1 &&
                    TrunnionCombo.SelectedIndex==1,
                Material=((ComboBoxItem)MaterialCombo.SelectedItem).Content.ToString(),
                NamingUnit=NamingUnitCombo.SelectedIndex==1 ? PipeNamingUnit.Imperial : PipeNamingUnit.Metric,
                WallOverrideMm=overrideWall
            };
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                if (Session.Instance.GetActiveDgnModel()==null ||
                    !Session.Instance.GetActiveDgnModel().Is3d)
                    throw new InvalidOperationException("请先打开三维 DGN 模型。");
                ElbowTrunnionDragTool.End();
                preview.Cancel();
                selection=null;
                ConfirmButton.IsEnabled=false;
                SelectionText.Text="等待点选 90° 弯头…";
                LiveLengthText.Text="";
                PlanText.Text="";
                ElbowTrunnionLocateTool.Begin();
                SetStatus("悬停在弯头主单元上，左键点选；右键结束点选。",false);
            }
            catch(Exception ex) { SetStatus("无法开始点选："+ex.Message,true); }
        }
        private void Stop_Click(object sender,RoutedEventArgs e)
        {
            ElbowTrunnionLocateTool.End();
            if (ElbowTrunnionDragTool.IsActive)
            {
                ElbowTrunnionDragTool.End();
                selection=null;
                LiveLengthText.Text="";
                SelectionText.Text="已结束拉伸，未生成耳轴。";
            }
            SetStatus("已结束点选与拉伸命令。",false);
        }
        private void OnPickEnded()
        {
            if (active) SetStatus("已结束点选命令。",false);
        }
        private void OnPicked(ulong id,int view,double x,double y)
        {
            int version=++pickVersion;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || version!=pickVersion) return;
                try
                {
                    var options=Parameters();
                    var candidate=ElbowTrunnionReader.Read(id,options.Elbow,options.Trunnion);
                    selection=candidate;
                    SelectionText.Text="元素 "+id+" · "+candidate.ClassName+" · DN"+candidate.MainDn;
                    LiveLengthText.Text="移动鼠标拉伸取长；松开首击后，再左键固定长度。";
                    ConfirmButton.IsEnabled=false;
                    ElbowTrunnionDragTool.Begin(candidate,options,view,x,y);
                    SetStatus("已进入拉伸取长：移动鼠标预览 H/L，下一次左键固定；右键取消。",false);
                }
                catch(Exception ex)
                {
                    selection=null;
                    SelectionText.Text="弯头读取或拉伸启动失败。";
                    LiveLengthText.Text="";
                    SetStatus(ex.Message,true);
                }
            }));
        }
        private void OnDragLengthChanged(double length)
        {
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || !ElbowTrunnionDragTool.IsActive) return;
                LiveLengthText.Text=(TrunnionCombo.SelectedIndex==0?"当前 H：":"当前 L：")+
                    length.ToString("F1",CultureInfo.InvariantCulture)+" mm · 左键固定，右键取消";
            }));
        }
        private void OnDragAccepted(double length)
        {
            int version=pickVersion;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || version!=pickVersion || selection==null) return;
                try
                {
                    ExtentText.Text=length.ToString("F1",CultureInfo.CurrentCulture);
                    var plan=ElbowTrunnionCalculator.Calculate(selection,Parameters());
                    preview.Regenerate(plan);
                    ShowPlan(plan);
                    LiveLengthText.Text=(plan.Parameters.Trunnion==TrunnionOrientation.Vertical?"高度 H":"长度 L")+
                        " 已固定为 "+length.ToString("F1",CultureInfo.InvariantCulture)+" mm。";
                    ConfirmButton.IsEnabled=true;
                    SetStatus("已固定拉伸长度并生成可撤销预览；可调整参数或确认生成。",false);
                }
                catch(Exception ex)
                {
                    ConfirmButton.IsEnabled=false;
                    SetStatus("拉伸预览生成失败："+ex.Message,true);
                }
            }));
        }
        private void OnDragCancelled()
        {
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active) return;
                selection=null;
                ConfirmButton.IsEnabled=false;
                SelectionText.Text="已取消拉伸，未生成耳轴。";
                LiveLengthText.Text="";
                SetStatus("已取消耳轴拉伸。",false);
            }));
        }
        private void OnDragFailed(string message)
        {
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (active && ElbowTrunnionDragTool.IsActive) SetStatus(message,true);
            }));
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if (!ready || selection==null) return;
            if (ElbowTrunnionDragTool.IsActive)
            {
                try { ElbowTrunnionDragTool.UpdateParameters(Parameters()); }
                catch(Exception ex) { SetStatus(ex.Message,true); }
                return;
            }
            Regenerate();
        }
        private void Refresh_Click(object sender,RoutedEventArgs e)
        {
            if (ElbowTrunnionDragTool.IsActive)
            {
                SetStatus("请先在模型视图中移动鼠标并左键固定拉伸长度。",true);
                return;
            }
            Regenerate();
        }
        private void Regenerate()
        {
            if (selection==null) { SetStatus("请先点选弯头并完成拉伸。",true); return; }
            try
            {
                var plan=ElbowTrunnionCalculator.Calculate(selection,Parameters());
                preview.Regenerate(plan);
                ShowPlan(plan);
                ConfirmButton.IsEnabled=true;
                SetStatus("耳轴预览已更新。",false);
            }
            catch(Exception ex) { SetStatus("预览更新失败："+ex.Message,true); }
        }
        private void ShowPlan(ElbowTrunnionPlan plan)
        {
            PlanText.Text=plan.AssemblyTag+"\n耳轴 DN"+plan.TrunnionDn+
                " · 外径 "+plan.TrunnionOdMm.ToString("G",CultureInfo.InvariantCulture)+
                " mm · 壁厚 "+plan.WallMm.ToString("G",CultureInfo.InvariantCulture)+
                " mm · 管长 "+plan.TubeLengthMm.ToString("F1",CultureInfo.InvariantCulture)+" mm";
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                if (ElbowTrunnionDragTool.IsActive)
                    throw new InvalidOperationException("请先左键固定拉伸长度。");
                if (!preview.HasPreview || preview.CurrentPlan==null)
                    throw new InvalidOperationException("当前没有待确认的预览。");
                string number=preview.CurrentPlan.AssemblyTag;
                preview.Confirm();
                selection=null;
                ConfirmButton.IsEnabled=false;
                SelectionText.Text="已生成 "+number;
                LiveLengthText.Text="";
                PlanText.Text="";
                SetStatus("已确认生成 "+number+"，并写入支吊架清单属性。",false);
            }
            catch(Exception ex) { SetStatus("确认失败："+ex.Message,true); }
        }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            ElbowTrunnionLocateTool.End();
            ElbowTrunnionDragTool.End();
            try { preview.Cancel(); }
            catch(Exception ex) { SetStatus(ex.Message,true); return; }
            selection=null;
            ConfirmButton.IsEnabled=false;
            SelectionText.Text="尚未选择弯头。";
            LiveLengthText.Text="";
            PlanText.Text="";
            SetStatus("已取消耳轴预览。",false);
        }
        private static void SetStatus(string message,bool error)
        {
            if (MainWindow.Current!=null) MainWindow.Current.SetStatus(message,error);
        }
    }
}
