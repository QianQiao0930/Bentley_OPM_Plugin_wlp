using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class NozzlePage : UserControl,IWorkspacePage
    {
        private readonly NozzlePreviewSession preview=new NozzlePreviewSession();
        private DPoint3d? origin;
        private bool ready,active,updatingCatalog;
        public string PageId { get { return "solid-nozzle"; } }
        public string PageTitle { get { return "实体管口"; } }
        public string PageSubtitle { get { return "选法兰、钢管和方向，点取基点生成三维实体"; } }
        public FrameworkElement View { get { return this; } }
        internal NozzlePage()
        {
            InitializeComponent();
            NozzlePlacementTool.Picked+=OnPicked;
            NozzlePlacementTool.Ended+=OnEnded;
            RatingCombo.ItemsSource=NozzleCatalog.Ratings;
            ScheduleCombo.ItemsSource=NozzleCatalog.Schedules;
            RatingCombo.SelectedItem="CL150";
            ScheduleCombo.SelectedItem="Ia_Sch10";
            AxisCombo.SelectedIndex=4;
            ready=true;
            RefreshDns(100);
            PageLastInput.Restore(this,PageId,"RatingCombo","ScheduleCombo","DnCombo",
                "WallText","LengthText","BoltHolesCheck","AxisCombo");
            UpdateSpecification();
        }
        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            PageLastInput.Save(this,PageId,"RatingCombo","ScheduleCombo","DnCombo",
                "WallText","LengthText","BoltHolesCheck","AxisCombo");
            active=false;NozzlePlacementTool.End();
            try { preview.Cancel(); } catch(Exception ex) { SetStatus(ex.Message,true); }
            origin=null;ConfirmButton.IsEnabled=false;PreviewText.Text="尚未点取基点。";
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            NozzlePlacementTool.Picked-=OnPicked;
            NozzlePlacementTool.Ended-=OnEnded;
        }
        private void RefreshDns(int preferred)
        {
            updatingCatalog=true;
            try
            {
                var dns=NozzleCatalog.AvailableDns(RatingCombo.SelectedItem as string,ScheduleCombo.SelectedItem as string);
                DnCombo.ItemsSource=dns.Select(x=>"DN"+x).ToArray();
                int selected=dns.Contains(preferred)?preferred:dns.Length>0?dns[0]:0;
                DnCombo.SelectedItem=selected>0?"DN"+selected:null;
                WallText.Text="";
            }
            finally { updatingCatalog=false; }
        }
        private int SelectedDn()
        {
            string value=DnCombo.SelectedItem as string;
            int dn;
            if(value==null || !value.StartsWith("DN") || !int.TryParse(value.Substring(2),out dn))
                throw new InvalidOperationException("当前系列没有可用的 DN 规格。");
            return dn;
        }
        private static double Number(string value,string label)
        {
            double number;
            if(!double.TryParse(value,NumberStyles.Float,CultureInfo.CurrentCulture,out number) &&
                !double.TryParse(value,NumberStyles.Float,CultureInfo.InvariantCulture,out number))
                throw new InvalidOperationException(label+"必须是数字。");
            return number;
        }
        private NozzleParameters Parameters()
        {
            string wall=WallText.Text.Trim();
            return new NozzleParameters {
                Rating=RatingCombo.SelectedItem as string,
                PipeSchedule=ScheduleCombo.SelectedItem as string,
                NominalDn=SelectedDn(),
                WallOverrideMm=wall.Length==0?(double?)null:Number(wall,"钢管壁厚"),
                TotalLengthMm=Number(LengthText.Text,"管口总长度"),
                Axis=((ComboBoxItem)AxisCombo.SelectedItem).Content.ToString(),
                DrawBoltHoles=BoltHolesCheck.IsChecked==true
            };
        }
        private void Catalog_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready || updatingCatalog)return;
            int preferred=100;
            string current=DnCombo.SelectedItem as string;
            if(current!=null)int.TryParse(current.Substring(2),out preferred);
            RefreshDns(preferred);UpdateSpecification();
            if(origin.HasValue && preview.HasPreview)Regenerate();
        }
        private void Dn_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready || updatingCatalog)return;
            WallText.Text="";
            UpdateSpecification();
            if(origin.HasValue && preview.HasPreview)Regenerate();
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;
            UpdateSpecification();
            if(origin.HasValue && preview.HasPreview)Regenerate();
        }
        private void UpdateSpecification()
        {
            try
            {
                var p=NozzleCalculator.Calculate(Parameters());
                SpecificationText.Text=p.Size.Rating+" / "+p.Size.PipeSchedule+" / DN"+p.Size.NominalDn+
                    " · 管外径 "+p.Size.PipeOutsideMm.ToString("G")+" mm，壁厚 "+p.WallMm.ToString("G")+
                    " mm · 法兰外径 "+p.Size.FlangeOutsideMm.ToString("G")+" mm，厚 "+
                    p.Size.FlangeThicknessMm.ToString("G")+" mm · 钢管名义长度 "+
                    p.PipeLengthMm.ToString("G")+" mm · "+p.Size.BoltCount+" × Ø"+
                    p.Size.BoltHoleMm.ToString("G")+" 螺栓孔"+(p.Parameters.DrawBoltHoles?"（绘制）":"（不绘制）");
            }
            catch(Exception ex) { SpecificationText.Text=ex.Message; }
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                NozzleCalculator.Calculate(Parameters());
                if(NozzlePlacementTool.IsActive)
                {
                    // 工具还装着（例如刚「确认生成」过、或上一次点取还没结束）：只恢复页面提示，
                    // **不要重新安装** —— 重装会先"结束再安装"，白丢一次基线状态、也容易踩到
                    // 延迟清理的竞态，表现就是"点两次才进得去"。
                    SetStatus("已在点取中：直接在模型里点取下一处即可；要停止请点「结束点取」。",false);
                    PreviewText.Text=origin.HasValue
                        ? "点取进行中：可直接在模型里点取下一处基点。"
                        : "点取进行中：在模型里左键点取管口基点。";
                    return;
                }
                NozzlePlacementTool.Begin();
                SetStatus("左键点取管口基点；右键结束并取消未确认预览。",false);
            }
            catch(Exception ex) { SetStatus("无法开始点取："+ex.Message,true); }
        }
        private void OnPicked(DPoint3d point)
        { if(!active)return;origin=point;Regenerate(); }
        private void Regenerate()
        {
            if(!origin.HasValue)return;
            try
            {
                var plan=NozzleCalculator.Calculate(Parameters());
                preview.Regenerate(plan,origin.Value);
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="预览已生成：DN"+plan.Size.NominalDn+"，"+plan.Parameters.Axis+" 轴，"+
                    plan.Parameters.TotalLengthMm.ToString("G")+" mm。";
                SetStatus("实体管口预览已更新；确认后保留在模型中。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                PreviewText.Text="参数或预览生成失败，请修正后更新；旧预览仍可取消。";
                SetStatus("管口预览失败："+ex.Message,true);
            }
        }
        private void OnEnded()
        {
            if(!active)return;
            try { preview.Cancel(); }
            catch(Exception ex) { SetStatus(ex.Message,true);return; }
            origin=null;ConfirmButton.IsEnabled=false;PreviewText.Text="已结束点取。";
            SetStatus("已结束点取并取消未确认预览。",false);
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {
            // 结束点取：工具 End() 时已经会触发 Ended → OnEnded 清理页面状态；
            // 工具已经结束（例如刚右键过）时事件不会再发，这里补调一次做兜底，
            // 保证按一下「结束点取」就能清掉未确认预览，而且不会连发两条提示。
            if(NozzlePlacementTool.IsActive) NozzlePlacementTool.End();
            else OnEnded();
        }
        private void Update_Click(object sender,RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try { preview.Cancel();origin=null;ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览已取消。";SetStatus("已取消管口预览。",false); }
            catch(Exception ex) { SetStatus(ex.Message,true); }
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try { preview.Confirm();origin=null;ConfirmButton.IsEnabled=false;
                PreviewText.Text="已确认生成管口。点取仍在进行中，可直接点取下一处（无需再点「开始点取」）；要停止请点「结束点取」。";
                SetStatus("实体管口已确认生成。",false); }
            catch(Exception ex) { SetStatus(ex.Message,true); }
        }
        private static void SetStatus(string text,bool error)
        { if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error); }
    }
}
