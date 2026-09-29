using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class TriangleBracketPage:UserControl,IWorkspacePage
    {
        private readonly TriangleBracketPreviewSession preview=new TriangleBracketPreviewSession();
        private PipeClampSelection line;
        private bool active,ready,locating,dirty;
        public string PageId {get{return "triangle-bracket";}}
        public string PageTitle {get{return "三角架";}}
        public string PageSubtitle {get{return "D5 / D6 / G12 / D19";}}
        public FrameworkElement View {get{return this;}}
        internal TriangleBracketPage()
        {
            InitializeComponent();
            KindCombo.ItemsSource=new[]{"D5 端焊","D6 侧焊","G12 锚固","D19 双槽钢"};
            VariantCombo.ItemsSource=new[]{"A","B","C","D"};
            TypeCombo.ItemsSource=new[]{"类型 1：斜撑在下","类型 2：斜撑在上"};
            PlateSubtypeCombo.ItemsSource=new[]{"A","B","C","D"};
            KindCombo.SelectedIndex=0;VariantCombo.SelectedIndex=0;
            TypeCombo.SelectedIndex=0;PlateSubtypeCombo.SelectedIndex=0;
            ready=true;UpdateKind();
            PageLastInput.Restore(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "L1Text","NameText","ReverseCheck","KeepLineCheck","PlateCheck",
                "PlateSubtypeCombo","PlateOffsetText");
        }
        public void OnActivated()
        {
            active=true;BracketLocateTool.Picked+=OnPicked;BracketLocateTool.Ended+=OnEnded;
        }
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "L1Text","NameText","ReverseCheck","KeepLineCheck","PlateCheck",
                "PlateSubtypeCombo","PlateOffsetText");
            active=false;BracketLocateTool.Picked-=OnPicked;BracketLocateTool.Ended-=OnEnded;
            if(locating)BracketLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览";
        }
        private string Kind {get{return TriangleBracketCatalog.Kinds[Math.Max(0,KindCombo.SelectedIndex)];}}
        private char Variant {get{return "ABCD"[Math.Max(0,VariantCombo.SelectedIndex)];}}
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready)return;
            NameText.Text=Kind;
            UpdateKind();Changed();
        }
        private void UpdateKind()
        {
            string kind=Kind;
            PlatePanel.Visibility=kind=="D5"?Visibility.Visible:Visibility.Collapsed;
            var v=TriangleBracketCatalog.Variant(kind,Variant);
            SectionText.Text="横担："+v.SectionA+"    斜撑："+v.SectionB+
                "    L2 上限："+TriangleBracketCatalog.MaxLength(kind)+" mm"+
                (kind=="G12"?"\n锚栓："+v.BoltSubtype+" 子项，S="+v.BoltSpacing+" mm":"")+
                (kind=="D19"?"\n两片槽钢背靠背，S="+v.WebGap+" mm；端部连接板 "+
                    v.ConnectorLength+"×"+v.ConnectorHeight+"×"+v.ConnectorThickness:"");
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;
            UpdateKind();Changed();
        }
        private void Changed()
        {
            if(line==null)return;
            dirty=true;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览 ●";
            PreviewText.Text="参数已变更，请更新预览后再确定生成。";
        }
        private static double Number(string text,string name)
        {
            double value;
            if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(name+"应为数字。");
            return value;
        }
        private TriangleBracketParameters Parameters()
        {
            return new TriangleBracketParameters {Kind=Kind,Variant=Variant,
                Type=Math.Max(0,TypeCombo.SelectedIndex)+1,L1Mm=Number(L1Text.Text,"L1"),
                Name=NameText.Text,Reverse=ReverseCheck.IsChecked==true,
                KeepAuxiliaryLine=KeepLineCheck.IsChecked==true,
                AddPlate=Kind=="D5"&&PlateCheck.IsChecked==true,
                PlateSubtype="ABCD"[Math.Max(0,PlateSubtypeCombo.SelectedIndex)].ToString(),
                PlateOffsetMm=Kind=="D5"&&PlateCheck.IsChecked==true
                    ?Number(PlateOffsetText.Text,"端板外移"):0};
        }
        private static double Length(PipeClampSelection value)
        {return Math.Sqrt(value.AxisX*value.AxisX+value.AxisY*value.AxisY+value.AxisZ*value.AxisZ);}
        private static void ValidateLine(PipeClampSelection value)
        {
            if(value.IsPipe||!value.IsAuxiliaryLine)
                throw new InvalidOperationException("请选择绘制好的水平辅助直线。");
            double horizontal=Math.Sqrt(value.AxisX*value.AxisX+value.AxisY*value.AxisY);
            if(horizontal<1e-9||Math.Atan2(Math.Abs(value.AxisZ),horizontal)>5*Math.PI/180)
                throw new InvalidOperationException("辅助线与水平面的夹角不得超过 5°。");
        }
        private void Regenerate()
        {
            if(line==null)return;
            try
            {
                ValidateLine(line);
                var p=Parameters();
                double heading=Math.Atan2(p.Reverse?-line.AxisY:line.AxisY,
                    p.Reverse?-line.AxisX:line.AxisX)*180/Math.PI;
                var plan=TriangleBracketCalculator.Calculate(p,Length(line),heading);
                preview.Show(plan,line);dirty=false;UpdateButton.Content="更新预览";
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="编号："+plan.Number+"\n"+plan.AssemblySpecification+
                    "\nL1="+plan.L1Mm.ToString("0.#")+" mm；L2="+plan.L2Mm.ToString("0.#")+
                    " mm；端部余量="+plan.EndOverhangMm.ToString("0.#")+" mm"+
                    (plan.HasLoad?"\n允许垂直荷载："+
                        plan.AllowableVerticalKn.ToString("0.#")+" kN"+
                        (p.Kind=="D19"?"":"；允许水平荷载："+
                            plan.AllowableHorizontalKn.ToString("0.#")+" kN"):
                        (p.Kind=="D5"?"":"\n该 L1 档位未给出允许荷载"));
                Status("三角架预览已生成。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;PreviewText.Text="预览未更新："+ex.Message;
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
                    preview.Cancel();ConfirmButton.IsEnabled=false;dirty=false;
                    line=PipeClampReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ);
                    ValidateLine(line);
                    KeepLineCheck.IsEnabled=!line.IsFromReference;
                    if(line.IsFromReference)KeepLineCheck.IsChecked=true;
                    Regenerate();
                }
                catch(Exception ex){line=null;Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";UpdateButton.Content="更新预览";
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{BracketLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){BracketLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try{preview.Cancel();line=null;dirty=false;ConfirmButton.IsEnabled=false;
                UpdateButton.Content="更新预览";PreviewText.Text="已取消预览。";}
            catch(Exception ex){Status(ex.Message,true);}
        }
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;
            Status("正在写入三角架清单…",false);
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=Stopwatch.StartNew();
            try
            {
                bool delete=line!=null&&line.IsAuxiliaryLine&&!line.IsFromReference&&
                    KeepLineCheck.IsChecked!=true;
                ulong id=line==null?0:line.ElementId;
                preview.Confirm();
                if(delete)DeleteLine(id);
                line=null;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览";
                PreviewText.Text="已确认生成并写入清单，可继续点取下一条辅助线。";
                Status("三角架已生成（"+timer.Elapsed.TotalSeconds.ToString("0.0")+" 秒）。",false);
            }
            catch(Exception ex){ConfirmButton.IsEnabled=preview.HasPreview;
                Status("确认失败："+ex.Message,true);}
        }
        private static void DeleteLine(ulong id)
        {
            var model=Session.Instance.GetActiveDgnModel();
            var element=model==null?null:model.FindElementById(new ElementId(ref id));
            if(element==null||!element.IsValid)return;
            var com=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference
                .GetElementByID64(checked((long)id));
            if(com==null||com.Type!=Bentley.Interop.MicroStationDGN.MsdElementType.Line)
                throw new InvalidOperationException("所选辅助线不再是普通直线，未删除。");
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("辅助线删除失败："+status);
        }
        private static void Status(string message,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error);}
    }
}
