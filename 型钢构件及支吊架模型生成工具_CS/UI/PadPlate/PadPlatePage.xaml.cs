using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace SteelSectionProbe
{
    internal partial class PadPlatePage:UserControl,IWorkspacePage
    {
        private readonly PadPlatePreviewSession preview=new PadPlatePreviewSession();
        private PipeClampSelection pipe;
        private PadPlateHvacDuct duct;
        private PadPlateElbow elbow;
        private bool active,ready,locating,dirty;
        public string PageId { get { return "pad-plate"; } }
        public string PageTitle { get { return "垫板"; } }
        public string PageSubtitle { get { return "Y2 弧形垫板 / 弯头垫板"; } }
        public FrameworkElement View { get { return this; } }
        internal PadPlatePage()
        {
            InitializeComponent();
            KindCombo.ItemsSource=new[]{"Y2 弧形垫板","弯头垫板"};KindCombo.SelectedIndex=0;
            DnCombo.ItemsSource=PadPlateCatalog.DnChoices;DnCombo.SelectedItem=100;
            MaterialCombo.ItemsSource=new[]{"L","C1","C2","A1","A2","S"};MaterialCombo.SelectedItem="C1";
            ready=true;UpdateKind();
            PageLastInput.Restore(this,PageId,"KindCombo","DnCombo","MaterialCombo",
                "AlphaText","LengthText","CoverageText","AutoMultiplierCheck",
                "MultiplierText","VentHoleCheck");
        }
        public void OnActivated(){active=true;PadPlateLocateTool.Picked+=OnPicked;PadPlateLocateTool.Ended+=OnEnded;}
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","DnCombo","MaterialCombo",
                "AlphaText","LengthText","CoverageText","AutoMultiplierCheck",
                "MultiplierText","VentHoleCheck");
            active=false;PadPlateLocateTool.Picked-=OnPicked;PadPlateLocateTool.Ended-=OnEnded;
            if(locating)PadPlateLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            pipe=null;duct=null;elbow=null;dirty=false;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览";
        }
        private PadPlateKind Kind { get { return KindCombo.SelectedIndex==1?PadPlateKind.Elbow:PadPlateKind.Y2; } }
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready)return;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            pipe=null;duct=null;elbow=null;dirty=false;ConfirmButton.IsEnabled=false;
            PreviewText.Text="型式已切换，请重新点选元素。";UpdateButton.Content="更新预览";UpdateKind();
        }
        private void UpdateKind()
        {
            bool isElbow=Kind==PadPlateKind.Elbow;
            Y2Panel.Visibility=isElbow?Visibility.Collapsed:Visibility.Visible;
            ElbowCoveragePanel.Visibility=isElbow?Visibility.Visible:Visibility.Collapsed;
            ElbowPanel.Visibility=isElbow?Visibility.Visible:Visibility.Collapsed;
            KindHint.Text=isElbow?"点选 90° 圆弧弯头；管道查 DN 表，HVAC 圆风管按实测外径与 RADIUS 建模。":"点选水平管道、HVAC 圆形直风管或水平辅助直线；圆风管按实测外径贴合，垫板贴在管底。";
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {if(!ready||pipe==null&&elbow==null)return;dirty=true;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览 ●";PreviewText.Text="参数已变更，请更新预览后确定生成。";}
        private static double Number(string raw,string name)
        {double value;if(!double.TryParse(raw,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
            !double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
            throw new InvalidOperationException(name+"应为数字。");return value;}
        private PadPlateParameters Parameters()
        {return new PadPlateParameters{Kind=Kind,FallbackDn=(int)DnCombo.SelectedItem,
            Material=(string)MaterialCombo.SelectedItem,AlphaDeg=Number(AlphaText.Text,"α"),
            LengthMm=Kind==PadPlateKind.Y2?Number(LengthText.Text,"L"):300,
            CoverageDeg=Kind==PadPlateKind.Elbow?Number(CoverageText.Text,"覆盖角"):75,
            AutoMultiplier=AutoMultiplierCheck.IsChecked==true,
            Multiplier=Kind==PadPlateKind.Elbow&&AutoMultiplierCheck.IsChecked!=true?
                Number(MultiplierText.Text,"倍率"):1.5,
            VentHole=VentHoleCheck.IsChecked==true};}
        private void Regenerate()
        {
            if(pipe==null&&elbow==null)return;
            try
            {
                var p=Parameters();var plan=Kind==PadPlateKind.Y2?PadPlateCatalog.Y2(p,pipe,duct):PadPlateCatalog.Elbow(p,elbow);
                preview.Show(plan);dirty=false;UpdateButton.Content="更新预览";ConfirmButton.IsEnabled=true;
                PreviewText.Text="编号："+plan.Number+"\n"+plan.Specification+
                    (Kind==PadPlateKind.Elbow?"\n沿弯头弧长："+plan.ArcLengthMm.ToString("0.#")+" mm":"");
                Status("垫板预览已生成。",false);
            }
            catch(Exception ex){ConfirmButton.IsEnabled=false;PreviewText.Text="预览未更新："+ex.Message;Status(ex.Message,true);}
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||!locating)return;
                try
                {
                    preview.Cancel();ConfirmButton.IsEnabled=false;dirty=false;
                    if(Kind==PadPlateKind.Y2)
                    {elbow=null;pipe=PadPlateStraightReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ,out duct);}
                    else{pipe=null;duct=null;elbow=PadPlateElbowReader.Read(located.ModelRef,located.ElementId);}
                    Regenerate();
                }
                catch(Exception ex){pipe=null;duct=null;elbow=null;Status("点选失败："+ex.Message,true);PreviewText.Text=ex.Message;}
            }),DispatcherPriority.Background);
        }
        private void OnEnded(){locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            pipe=null;duct=null;elbow=null;dirty=false;ConfirmButton.IsEnabled=false;PreviewText.Text="已结束点选。";UpdateButton.Content="更新预览";}
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{PadPlateLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){PadPlateLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();pipe=null;duct=null;elbow=null;dirty=false;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览";PreviewText.Text="已取消预览。";}catch(Exception ex){Status(ex.Message,true);}}
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;Status("正在写入垫板清单…",false);
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=Stopwatch.StartNew();
            try{preview.Confirm();pipe=null;duct=null;elbow=null;PreviewText.Text="已确认生成并写入清单，可继续点选。";
                Status("垫板已生成（"+timer.Elapsed.TotalSeconds.ToString("0.0")+" 秒）。",false);}
            catch(Exception ex){ConfirmButton.IsEnabled=preview.HasPreview;Status("确认失败："+ex.Message,true);}
        }
        private static void Status(string message,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error);}
    }
}
