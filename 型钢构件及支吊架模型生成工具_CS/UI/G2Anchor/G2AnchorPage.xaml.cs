using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// G2 混凝土锚板功能页。点取混凝土表面上锚板背面的中心点后生成可撤销预览，
    /// 参数变化自动重建；确认时才写入 <c>PipeSupportComponents</c> 公共 ItemType。
    /// </summary>
    internal partial class G2AnchorPage : UserControl,IWorkspacePage
    {
        private readonly G2AnchorPreviewSession preview=new G2AnchorPreviewSession();
        private DPoint3d? placement;
        private bool active,ready,locating;

        public string PageId { get { return "g2-anchor-plate"; } }
        public string PageTitle { get { return "混凝土锚板"; } }
        public string PageSubtitle { get { return "G2 · 点取混凝土表面，生成锚板与 4 根膨胀锚栓"; } }
        public FrameworkElement View { get { return this; } }

        internal G2AnchorPage()
        {
            InitializeComponent();
            G2AnchorLocateTool.Picked+=OnPicked;
            G2AnchorLocateTool.Ended+=OnEnded;
            SubtypeCombo.ItemsSource=G2AnchorCatalog.All
                .Select(item=>G2AnchorCalculator.DescribeItem(item)).ToArray();
            var last=G2AnchorLastChoice.Load();
            SubtypeCombo.SelectedIndex=Math.Max(0,
                Math.Min(G2AnchorCatalog.All.Count-1,last.SubtypeIndex));
            MountCombo.SelectedIndex=Math.Max(0,Math.Min(2,last.MountIndex));
            HeadingText.Text=string.IsNullOrEmpty(last.Heading)?"0":last.Heading;
            SpacingText.Text=string.IsNullOrEmpty(last.Spacing)
                ? CurrentItem().MinSpacingMm.ToString("0",CultureInfo.InvariantCulture)
                : last.Spacing;
            ready=true;
            RefreshReadings();
        }

        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            active=false; locating=false; G2AnchorLocateTool.End();
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            placement=null; ConfirmButton.IsEnabled=false;
            PreviewText.Text="尚未点取位置。";
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            G2AnchorLocateTool.Picked-=OnPicked;
            G2AnchorLocateTool.Ended-=OnEnded;
        }

        private G2AnchorItem CurrentItem()
        {
            int index=SubtypeCombo.SelectedIndex;
            if(index<0 || index>=G2AnchorCatalog.All.Count) index=0;
            return G2AnchorCatalog.All[index];
        }
        private static double Number(string value,string label)
        {
            string text=(value??"").Trim();
            if(text.Length==0) throw new InvalidOperationException(label+"不能为空。");
            double parsed;
            if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out parsed) &&
                !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out parsed))
                throw new InvalidOperationException(label+"必须是有效数字。");
            return parsed;
        }
        private G2AnchorParameters Parameters()
        {
            string text=(SpacingText.Text??"").Trim();
            double? spacing=null;
            if(text.Length>0) spacing=Number(text,"间距 S");
            return new G2AnchorParameters {
                SubtypeKey=CurrentItem().Key,
                SpacingMm=spacing,
                HeadingDegrees=Number(HeadingText.Text,"朝向"),
                MountFace=(G2MountFace)Math.Max(0,Math.Min(2,MountCombo.SelectedIndex))
            };
        }
        private void RefreshReadings()
        {
            var item=CurrentItem();
            PlateText.Text=G2AnchorCalculator.DescribePlate(item);
            BoltText.Text=G2AnchorCalculator.DescribeBolt(item);
            try
            {
                SpecificationText.Text=G2AnchorCalculator.Describe(
                    G2AnchorCalculator.Calculate(Parameters()));
            }
            catch(Exception ex) { SpecificationText.Text="参数有误："+ex.Message; }
        }
        private void SaveLastChoice()
        {
            try
            {
                G2AnchorLastChoice.Save(new G2AnchorLastChoice.Data {
                    SubtypeIndex=Math.Max(0,SubtypeCombo.SelectedIndex),
                    MountIndex=Math.Max(0,MountCombo.SelectedIndex),
                    Spacing=SpacingText.Text??"", Heading=HeadingText.Text??"0" });
            }
            catch { }
        }
        /// <summary>切换子项时把间距 S 重置为该子项 MIN.S，保证默认参数合法。</summary>
        private void Subtype_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            SpacingText.Text=CurrentItem().MinSpacingMm.ToString("0",CultureInfo.InvariantCulture);
            RefreshReadings(); SaveLastChoice();
            if(preview.HasPreview) Regenerate();
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            RefreshReadings(); SaveLastChoice();
            if(preview.HasPreview) Regenerate();
        }
        private void Regenerate()
        {
            if(!placement.HasValue) return;
            try
            {
                var plan=G2AnchorCalculator.Calculate(Parameters());
                preview.Regenerate(plan,placement.Value);
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="预览已生成："+plan.AssemblyTag+"，锚板 "+
                    plan.PlateSideMm.ToString("0")+"×"+plan.PlateSideMm.ToString("0")+"×"+
                    plan.PlateThicknessMm.ToString("0")+"，M"+plan.BoltDiameterMm.ToString("0")+
                    "×"+plan.BoltLengthMm.ToString("0")+" 锚栓 ×"+plan.BoltCount+
                    "，有效埋深 "+plan.ActualEmbedmentMm.ToString("0")+" mm（≥"+
                    plan.RequiredEmbedmentMm.ToString("0")+"）。";
                Status("G2 锚板预览已生成；确定后写入支吊架材料清单。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                Status("预览失败："+ex.Message,true);
            }
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null || !model.Is3d)
                    throw new InvalidOperationException("请先打开三维模型。");
                G2AnchorCalculator.Calculate(Parameters());
                G2AnchorLocateTool.Begin(); locating=true;
                Status("点取混凝土表面上锚板背面的中心点；右键结束并取消未确认预览。",false);
            }
            catch(Exception ex) { Status("无法开始点取："+ex.Message,true); }
        }
        private void OnPicked(DPoint3d point)
        {
            if(!active || !locating) return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active || !locating) return;
                placement=point; Regenerate();
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            if(!active) return;
            locating=false;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            placement=null; ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";
            Status("已结束点取并取消未确认预览。",false);
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {
            G2AnchorLocateTool.End();
        }
        private void Update_Click(object sender,RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                preview.Cancel(); placement=null; ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览已取消。"; Status("预览已取消。",false);
            }
            catch(Exception ex) { Status(ex.Message,true); }
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                preview.Confirm();
                placement=null; ConfirmButton.IsEnabled=false;
                PreviewText.Text="已确认生成并写入支吊架材料清单，可继续点取下一处。";
                Status("G2 混凝土锚板已生成。",false);
            }
            catch(Exception ex) { Status("确认失败："+ex.Message,true); }
        }
        private static void Status(string message,bool error)
        { if(MainWindow.Current!=null) MainWindow.Current.SetStatus(message,error); }
    }
}
