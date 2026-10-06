using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using Bentley.GeometryNET;
namespace SteelSectionProbe
{
    internal partial class SquareManholePage:UserControl,IWorkspacePage
    {
        private readonly SquareManholePreviewSession preview=new SquareManholePreviewSession();
        private readonly string[] fields={"BarrelWidthText","BarrelDepthText","BarrelHeightText","CoverWidthText","CoverDepthText","CoverHeightText","WallText","RotationText"};
        private DPoint3d? origin;
        private bool ready,active;
        public string PageId {get{return "square-manhole";}}
        public string PageTitle {get{return "方形人孔";}}
        public string PageSubtitle {get{return "筒体、盖板及四个把手";}}
        public FrameworkElement View {get{return this;}}
        internal SquareManholePage()
        {
            InitializeComponent();PageLastInput.Restore(this,PageId,fields);ready=true;UpdateSpecification();
            SquareManholePlacementTool.Picked+=OnPicked;SquareManholePlacementTool.Ended+=OnEnded;
        }
        public void OnActivated(){active=true;}
        public void OnDeactivated()
        {
            PageLastInput.Save(this,PageId,fields);active=false;SquareManholePlacementTool.End();CancelPreview();
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();SquareManholePlacementTool.Picked-=OnPicked;SquareManholePlacementTool.Ended-=OnEnded;
        }
        private static double Number(TextBox box,string label)
        {
            double value;
            if(!double.TryParse(box.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(box.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(label+"必须是数字。");
            return value;
        }
        private SquareManholePlan Plan()
        {
            return SquareManholeCalculator.Calculate(new SquareManholeParameters {
                BarrelWidthMm=Number(BarrelWidthText,"筒体净长"),BarrelDepthMm=Number(BarrelDepthText,"筒体净宽"),
                BarrelHeightMm=Number(BarrelHeightText,"筒体高度"),CoverWidthMm=Number(CoverWidthText,"盖板外形长"),
                CoverDepthMm=Number(CoverDepthText,"盖板外形宽"),CoverHeightMm=Number(CoverHeightText,"盖板外形高"),
                WallMm=Number(WallText,"壁厚"),RotationDegrees=Number(RotationText,"朝向角")});
        }
        private void Parameter_Changed(object sender,TextChangedEventArgs e)
        {
            if(!ready)return;ConfirmButton.IsEnabled=false;UpdateSpecification();
            if(preview.HasPreview)PreviewText.Text="参数已变化，待更新预览。";
        }
        private void UpdateSpecification()
        {
            try{var p=Plan();SpecificationText.Text=string.Format(CultureInfo.CurrentCulture,
                "筒体外形 {0:G} × {1:G} mm；盖顶标高 +{2:G} mm；每侧间隙 {3:G} / {4:G} mm。",
                p.BarrelOutsideWidthMm,p.BarrelOutsideDepthMm,p.TotalHeightMm,p.ClearanceXmm,p.ClearanceYmm);}
            catch(Exception ex){SpecificationText.Text=ex.Message;}
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try{Plan();SquareManholePlacementTool.Begin();Status("请点取筒体下口中心。",false);}
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void OnPicked(DPoint3d point){if(!active)return;origin=point;Regenerate();}
        private void Regenerate()
        {
            if(!origin.HasValue){Status("请先点取筒体下口中心。",true);return;}
            ConfirmButton.IsEnabled=false;
            try{preview.Regenerate(Plan(),origin.Value);ConfirmButton.IsEnabled=true;
                PreviewText.Text="方形人孔预览已生成。";Status("方形人孔预览已更新。",false);}
            catch(Exception ex){PreviewText.Text=ex.Message;Status("方形人孔预览失败："+ex.Message,true);}
        }
        private void OnEnded(){if(active)CancelPreview();}
        private void CancelPreview()
        {
            ConfirmButton.IsEnabled=false;
            try{preview.Cancel();origin=null;PreviewText.Text="尚未点取筒体下口中心。";}
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e){SquareManholePlacementTool.End();CancelPreview();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e){CancelPreview();}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(!ConfirmButton.IsEnabled)return;
            try{preview.Confirm();origin=null;ConfirmButton.IsEnabled=false;PreviewText.Text="方形人孔已生成。";
                PageLastInput.Save(this,PageId,fields);Status("已生成一个方形人孔块。",false);}
            catch(Exception ex){Status(ex.Message,true);}
        }
        private static void Status(string message,bool error){if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error);}
    }
}
