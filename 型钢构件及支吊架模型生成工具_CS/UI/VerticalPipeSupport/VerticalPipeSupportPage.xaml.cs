using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class VerticalPipeSupportPage : UserControl,IWorkspacePage
    {
        private readonly VerticalPipeSupportPreviewSession preview=new VerticalPipeSupportPreviewSession();
        private PipeClampSelection selection;
        private bool active,locating,initializing;
        public string PageId { get { return "vertical-pipe-support"; } }
        public string PageTitle { get { return "立管耳轴"; } }
        public string PageSubtitle { get { return "F6 单耳轴 · F7 双耳轴 · F10 小管径立管耳板"; } }
        public FrameworkElement View { get { return this; } }
        internal VerticalPipeSupportPage()
        {
            initializing=true;
            InitializeComponent();
            KindCombo.ItemsSource=new[]{"F6 单耳轴","F7 双耳轴","F10 小管径立管耳板"};
            KindCombo.SelectedIndex=0;
            TrunnionPipeDn.ItemsSource=VerticalPipeSupportCatalog.TrunnionDns.Select(n=>"DN"+n).ToArray();
            TrunnionPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.TrunnionDns,100);
            EarPipeDn.ItemsSource=VerticalPipeSupportCatalog.F10Dns.Select(n=>"DN"+n).ToArray();
            EarPipeDn.SelectedIndex=2;
            EndTypeCombo.ItemsSource=new[]{"A","B","C"};EndTypeCombo.SelectedIndex=0;
            TrunnionMaterial.ItemsSource=new[]{"L","C1","C2","A1","A2","S","S1"};
            TrunnionMaterial.SelectedIndex=1;
            EarMaterial.ItemsSource=new[]{"L","C1","C2","A1","A2","S"};
            EarMaterial.SelectedIndex=1;
            EarLength.ItemsSource=new[]{"1 — 100 mm","2 — 150 mm","3 — 200 mm"};EarLength.SelectedIndex=0;
            EarHeight.ItemsSource=new[]{"A — 50 mm","B — 100 mm","C — 150 mm","D — 200 mm"};EarHeight.SelectedIndex=0;
            RefreshTrunnionChoices();
            UpdatePanels();
            initializing=false;
            PageLastInput.Restore(this,PageId,"KindCombo","TrunnionPipeDn","TrunnionDn",
                "LengthText","WallText","EndTypeCombo","TrunnionMaterial","TrunnionAngle",
                "PadCheck","PadThickness","EarPipeDn","EarLength","EarHeight",
                "EarMaterial","EarAngle","FixedCheck");
        }
        public void OnActivated()
        {
            active=true;
            PipeClampLocateTool.Picked+=OnPicked;
            PipeClampLocateTool.Ended+=OnEnded;
        }
        public void OnDeactivated() { Close(); }
        public void OnWorkspaceClosing() { Close(); }
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","TrunnionPipeDn","TrunnionDn",
                "LengthText","WallText","EndTypeCombo","TrunnionMaterial","TrunnionAngle",
                "PadCheck","PadThickness","EarPipeDn","EarLength","EarHeight",
                "EarMaterial","EarAngle","FixedCheck");
            active=false;
            PipeClampLocateTool.Picked-=OnPicked;
            PipeClampLocateTool.Ended-=OnEnded;
            if(locating) PipeClampLocateTool.End();
            locating=false;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            selection=null;ConfirmButton.IsEnabled=false;
        }
        private VerticalPipeSupportKind Kind()
        {
            return KindCombo.SelectedIndex==1?VerticalPipeSupportKind.F7:
                KindCombo.SelectedIndex==2?VerticalPipeSupportKind.F10:VerticalPipeSupportKind.F6;
        }
        private void UpdatePanels()
        {
            bool ear=Kind()==VerticalPipeSupportKind.F10;
            TrunnionPanel.Visibility=ear?Visibility.Collapsed:Visibility.Visible;
            EarPlatePanel.Visibility=ear?Visibility.Visible:Visibility.Collapsed;
        }
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||TrunnionPanel==null)return;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true);return; }
            selection=null;ConfirmButton.IsEnabled=false;
            UpdatePanels();PreviewText.Text="类型已切换，请点取立管或竖直辅助线。";
        }
        private void RefreshTrunnionChoices()
        {
            int index=TrunnionPipeDn.SelectedIndex;
            if(index<0)return;
            var candidates=VerticalPipeSupportCatalog.TrunnionCandidates(
                VerticalPipeSupportCatalog.TrunnionDns[index]);
            TrunnionDn.ItemsSource=candidates.Select(n=>"DN"+n).ToArray();
            TrunnionDn.SelectedIndex=candidates.Length-1;
        }
        private void PipeDn_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||TrunnionDn==null)return;
            RefreshTrunnionChoices();
            Parameter_Changed(sender,e);
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(initializing||!active||selection==null)return;
            Regenerate();
        }
        private static double Number(string raw,string label,bool blankZero=false)
        {
            if(blankZero&&string.IsNullOrWhiteSpace(raw))return 0;
            double value;
            if(!double.TryParse(raw,NumberStyles.Float,CultureInfo.CurrentCulture,out value) &&
                !double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(label+"应为数字。");
            return value;
        }
        private VerticalPipeSupportParameters Parameters()
        {
            var kind=Kind();
            var p=new VerticalPipeSupportParameters {Kind=kind};
            if(kind==VerticalPipeSupportKind.F10)
            {
                p.PipeDn=VerticalPipeSupportCatalog.F10Dns[Math.Max(0,EarPipeDn.SelectedIndex)];
                p.F10Length=(EarLength.SelectedIndex+1).ToString(CultureInfo.InvariantCulture);
                p.F10Height="ABCD"[Math.Max(0,EarHeight.SelectedIndex)].ToString();
                p.Material=EarMaterial.SelectedItem as string??"C1";
                p.AzimuthDegrees=Number(EarAngle.Text,"方位角");
                p.F10Fixed=FixedCheck.IsChecked==true;
            }
            else
            {
                p.PipeDn=VerticalPipeSupportCatalog.TrunnionDns[Math.Max(0,TrunnionPipeDn.SelectedIndex)];
                var candidates=VerticalPipeSupportCatalog.TrunnionCandidates(p.PipeDn);
                p.TrunnionDn=candidates[Math.Max(0,Math.Min(TrunnionDn.SelectedIndex,candidates.Length-1))];
                p.LengthMm=Number(LengthText.Text,"耳轴长度 L");
                p.WallMm=Number(WallText.Text,"耳轴壁厚",true);
                p.EndType=EndTypeCombo.SelectedItem as string??"A";
                p.Material=TrunnionMaterial.SelectedItem as string??"C1";
                p.AzimuthDegrees=Number(TrunnionAngle.Text,"方位角");
                p.BuildPad=PadCheck.IsChecked==true;
                p.PadThicknessMm=Number(PadThickness.Text,"补强板厚度");
            }
            return p;
        }
        private void Regenerate()
        {
            if(selection==null)return;
            try
            {
                VerticalPipeSupportCalculator.ValidateVertical(selection);
                var p=Parameters();
                var plan=VerticalPipeSupportCalculator.Calculate(p,selection.IsPipe,
                    selection.NominalMm,selection.PipeNumber);
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null) throw new InvalidOperationException("没有活动模型。");
                double scale=model.GetModelInfo().UorPerMeter/1000.0;
                var center=selection.ProjectedCenter();
                preview.Show(plan,new DPoint3d(center[0]*scale,center[1]*scale,center[2]*scale),
                    new DVector3d(selection.AxisX,selection.AxisY,selection.AxisZ));
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="预览："+plan.Number+"；"+plan.Specification+
                    (string.IsNullOrEmpty(selection.AxisNote)?"":"；"+selection.AxisNote);
                Status("立管耳轴预览已生成。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览未更新："+ex.Message;
                Status(ex.Message,true);
            }
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||!locating)return;
                try
                {
                    preview.Cancel();
                    ConfirmButton.IsEnabled=false;
                    selection=PipeClampReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ);
                    if(selection.IsPipe && selection.NominalMm.HasValue)
                    {
                        int matched=VerticalPipeSupportCatalog.MatchDn(selection.NominalMm.Value,Kind());
                        if(matched>0)
                        {
                            initializing=true;
                            if(Kind()==VerticalPipeSupportKind.F10)
                                EarPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.F10Dns,matched);
                            else
                            {
                                TrunnionPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.TrunnionDns,matched);
                                RefreshTrunnionChoices();
                            }
                            initializing=false;
                        }
                    }
                    Regenerate();
                }
                catch(Exception ex) {initializing=false;selection=null;Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            locating=false;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            selection=null;ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try {PipeClampLocateTool.Begin();locating=true;Status("请选择立管或竖直辅助线。",false);}
            catch(Exception ex) {Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e) { PipeClampLocateTool.End(); }
        private void Update_Click(object sender,RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try {preview.Cancel();selection=null;ConfirmButton.IsEnabled=false;PreviewText.Text="预览已取消。";}
            catch(Exception ex) {Status(ex.Message,true);}
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                preview.Confirm();selection=null;ConfirmButton.IsEnabled=false;
                PreviewText.Text="已确认生成并写入清单；可继续点取下一处。";
                Status("立管耳轴已生成。",false);
            }
            catch(Exception ex) {Status("确认失败："+ex.Message,true);}
        }
        private static void Status(string message,bool error)
        { if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error); }
    }
}
