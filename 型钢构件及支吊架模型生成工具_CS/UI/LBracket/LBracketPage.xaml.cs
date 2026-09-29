using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class LBracketPage:UserControl,IWorkspacePage
    {
        private readonly LBracketPreviewSession preview=new LBracketPreviewSession();
        private LBracketSelection selection;
        private bool active,ready,locating,dirty;
        public string PageId {get{return "l-bracket";}}
        public string PageTitle {get{return "L 型架";}}
        public string PageSubtitle {get{return "D7 · L 形 / 倒 L 形架";}}
        public FrameworkElement View {get{return this;}}
        internal LBracketPage()
        {
            InitializeComponent();
            VariantCombo.ItemsSource=new[]{"A  ∠50×6","B  ∠75×7","C  ∠100×10",
                "D  [16a","E  H125×125×6.5×9","F  H150×150×7×10"};
            TypeCombo.ItemsSource=new[]{"1 正 L 端焊","2 正 L 侧焊",
                "3 倒 L 端焊","4 倒 L 侧焊"};
            VariantCombo.SelectedIndex=0;TypeCombo.SelectedIndex=0;
            ready=true;
            PageLastInput.Restore(this,PageId,"VariantCombo","TypeCombo","WidthText",
                "NameText","KeepLineCheck");
            UpdateLimits();
        }
        public void OnActivated(){active=true;LBracketLocateTool.Picked+=OnPicked;
            LBracketLocateTool.Ended+=OnEnded;}
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"VariantCombo","TypeCombo","WidthText",
                "NameText","KeepLineCheck");
            active=false;LBracketLocateTool.Picked-=OnPicked;LBracketLocateTool.Ended-=OnEnded;
            if(locating)LBracketLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){PreviewText.Text=ex.Message;Status("D7 预览清理失败。",true);}
            selection=null;dirty=false;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览";
            UpdateLimits();
        }
        private char Variant {get{return LBracketCatalog.Keys[Math.Max(0,VariantCombo.SelectedIndex)];}}
        private int Type {get{return Math.Max(0,TypeCombo.SelectedIndex)+1;}}
        private static bool TryNumber(string raw,out double value)
        {return (double.TryParse(raw,NumberStyles.Float,CultureInfo.CurrentCulture,out value)||
            double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out value))&&
            !double.IsNaN(value)&&!double.IsInfinity(value);}
        private LBracketParameters Parameters()
        {
            double width;
            if(!TryNumber(WidthText.Text,out width))
                throw new InvalidOperationException("B 应为数字；当前输入："+WidthText.Text);
            return new LBracketParameters {Variant=Variant,Type=Type,WidthMm=width,
                Name=NameText.Text,KeepAuxiliaryLine=KeepLineCheck.IsChecked==true};
        }
        private void UpdateLimits()
        {
            if(!ready)return;
            var v=LBracketCatalog.Require(Variant);
            SectionText.Text="立杆 / 横担："+v.Specification+
                (Variant>='E'?"；子项 E/F 仅可选类型 1 或 3。":"");
            double width;bool valid=TryNumber(WidthText.Text,out width);
            string h=selection==null?"未点取":selection.HeightMm.ToString("0.#")+" mm";
            string b=valid?width.ToString("0.#")+" mm":"输入无效";
            LimitText.Text="标准上限：H ≤ "+v.MaxHeightMm.ToString("0.#")+
                " mm；当前 H："+h+"\nB ≤ "+v.MaxWidthMm.ToString("0.#")+
                " mm；当前 B："+b+"。L 由辅助线读取，无独立标准上限。";
            bool exceeded=(selection!=null&&selection.HeightMm>v.MaxHeightMm+1)||
                !valid||width<=0||width>v.MaxWidthMm||Variant>='E'&&(Type==2||Type==4);
            LimitText.Foreground=(System.Windows.Media.Brush)FindResource(exceeded?"ErrorBrush":"StatusBrush");
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;UpdateLimits();
            if(selection==null)return;
            dirty=true;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览 ●";
            PreviewText.Text="参数已更改，请更新预览。";
        }
        private void Regenerate()
        {
            if(selection==null)return;
            try
            {
                var plan=LBracketCalculator.Calculate(Parameters(),selection);
                preview.Show(plan);dirty=false;ConfirmButton.IsEnabled=true;
                UpdateButton.Content="更新预览";
                PreviewText.Text="编号："+(plan.Number.Length==0?"未编号":plan.Number)+
                    "\nH="+plan.Selection.HeightMm.ToString("0.#")+" mm，L="+
                    plan.Selection.LengthMm.ToString("0.#")+" mm，B="+
                    plan.Parameters.WidthMm.ToString("0.#")+" mm"+
                    "\n立杆下料长 "+plan.PostCutLengthMm.ToString("0.#")+
                    " mm；横担下料长 "+plan.ArmCutLengthMm.ToString("0.#")+" mm"+
                    (plan.AllowableLoadKn.HasValue?"\n允许垂直荷载 "+
                        plan.AllowableLoadKn.Value.ToString("0.##")+" kN（按 H="+
                        plan.UsedHeightMm.Value.ToString("0.#")+"、B≤"+
                        plan.UsedWidthMm.Value.ToString("0.#")+" 查表）":
                        "\n当前 H / B 档位无允许荷载值。");
                Status("D7 预览已更新。",false);
            }
            catch(Exception ex){ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览未更新："+ex.Message;
                Status("D7 预览失败，请查看面板。",true);}
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
                    selection=LBracketReader.Read(located.ModelRef,located.ElementId);
                    KeepLineCheck.IsEnabled=!selection.IsFromReference;
                    if(selection.IsFromReference)KeepLineCheck.IsChecked=true;
                    UpdateLimits();Regenerate();
                }
                catch(Exception ex){selection=null;UpdateLimits();
                    PreviewText.Text="点取失败："+ex.Message;
                    Status("D7 点取失败，请查看面板。",true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            locating=false;try{preview.Cancel();}catch(Exception ex){PreviewText.Text=ex.Message;}
            selection=null;dirty=false;ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";UpdateButton.Content="更新预览";UpdateLimits();
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{LBracketLocateTool.Begin();locating=true;}
            catch(Exception ex){PreviewText.Text=ex.Message;Status("D7 无法开始点取。",true);}}
        private void End_Click(object sender,RoutedEventArgs e){LBracketLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();selection=null;dirty=false;ConfirmButton.IsEnabled=false;
                PreviewText.Text="已取消预览。";UpdateButton.Content="更新预览";UpdateLimits();}
            catch(Exception ex){PreviewText.Text=ex.Message;Status("D7 取消失败。",true);}}
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=System.Diagnostics.Stopwatch.StartNew();
            try
            {
                bool remove=selection!=null&&!selection.IsFromReference&&
                    KeepLineCheck.IsChecked!=true;
                ulong id=selection==null?0:selection.ElementId;
                preview.Confirm();selection=null;UpdateLimits();
                timer.Stop();
                PreviewText.Text="D7 已生成并写入清单，耗时 "+
                    timer.Elapsed.TotalSeconds.ToString("0.0",CultureInfo.InvariantCulture)+" 秒。可继续点取。";
                Status("D7 已生成（"+timer.Elapsed.TotalSeconds.ToString("0.0",CultureInfo.InvariantCulture)+" 秒）。",false);
                if(remove)try{DeleteLine(id);}catch(Exception ex)
                    {PreviewText.Text+="\n辅助折线未删除："+ex.Message;
                        Status("D7 已生成，辅助线未删除。",true);}
            }
            catch(Exception ex){ConfirmButton.IsEnabled=preview.HasPreview;
                PreviewText.Text="确认失败："+ex.Message;
                Status("D7 确认失败，请查看面板。",true);}
        }
        private static void DeleteLine(ulong id)
        {
            LBracketReader.Read(null,id);
            var model=Session.Instance.GetActiveDgnModel();
            var element=model.FindElementById(new ElementId(ref id));
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("删除失败："+status);
        }
        private static void Status(string message,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error);}
    }
}
