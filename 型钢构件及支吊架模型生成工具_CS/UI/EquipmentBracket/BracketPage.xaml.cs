using System;
using System.Globalization;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using System.Windows.Media;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class BracketPage:UserControl,IWorkspacePage
    {
        private readonly bool isDouble;
        private readonly BracketPreviewSession preview=new BracketPreviewSession();
        private readonly BracketLastChoice.Data lastChoice=BracketLastChoice.Load();
        private PipeClampSelection line;
        private bool active,ready,locating,dirty;
        public string PageId{get{return isDouble?"n4-double-bracket":"n3-single-bracket";}}
        public string PageTitle{get{return isDouble?"N4 设备上生根双三角架":"N3 设备上生根单三角架";}}
        public string PageSubtitle{get{return isDouble?"设备中心至管中心定位":"设备表面至横担外端定位";}}
        public FrameworkElement View{get{return this;}}
        internal BracketPage(bool doubleBracket)
        {
            isDouble=doubleBracket;InitializeComponent();
            TitleText.Text=PageTitle;
            InstructionText.Text=isDouble?
                "绘制水平辅助线：起点为设备中心，终点为立管中心。输入设备外径后，由线长算出 L1。参数更改后须更新预览。":
                "绘制水平辅助线：起点在设备表面，终点为横担末端；辅助线标高为管底和横担顶面。";
            PreviewInstructionText.Text=isDouble?
                "点取设备中心至管中心的水平辅助线。修改参数后点击更新预览，确认后才写入清单；右键结束点取并取消未确认预览。":
                "点取设备表面至横担末端的水平辅助线。可调整参数并更新预览；确认后才写入清单，右键结束点取并取消未确认预览。";
            DoublePanel.Visibility=isDouble?Visibility.Visible:Visibility.Collapsed;
            EPanel.Visibility=isDouble?Visibility.Collapsed:Visibility.Visible;
            TypeCombo.ItemsSource=new[]{"类型 1：斜撑在下","类型 2：斜撑在上"};
            SubtypeCombo.ItemsSource=new[]{"A","B","C","D","E","F"};
            TypeCombo.SelectedIndex=0;SubtypeCombo.SelectedIndex=0;
            SetSubtypeDefaults();
            RestoreLastChoice();   // 必须在 SetSubtypeDefaults 之后、ready=true 之前，理由见方法注释
            ready=true;UpdateE();
        }
        /// <summary>恢复上次选择。</summary>
        /// <remarks>
        /// 两个顺序约束缺一不可：
        /// ① 必须在 <c>SetSubtypeDefaults()</c> <b>之后</b> —— 它会把 H / L2 重写成该子项的最小值，
        ///    先恢复就会被冲掉；子项索引也可能与上次不同，所以这里再调一次。
        /// ② 必须在 <c>ready=true</c> <b>之前</b> —— 赋值会触发 <c>TextChanged</c>/<c>SelectionChanged</c>，
        ///    ready 时它们会走 <c>Changed()</c>，页面一进来就被置脏、确认按钮被禁。
        /// </remarks>
        private void RestoreLastChoice()
        {
            try
            {
                int types=Math.Max(1,TypeCombo.Items.Count);
                int subtypes=Math.Max(1,SubtypeCombo.Items.Count);
                if(isDouble)
                {
                    TypeCombo.SelectedIndex=Math.Max(0,Math.Min(types-1,lastChoice.N4TypeIndex));
                    SubtypeCombo.SelectedIndex=Math.Max(0,Math.Min(subtypes-1,lastChoice.N4SubtypeIndex));
                    SetSubtypeDefaults();
                    if(!string.IsNullOrEmpty(lastChoice.N4Height)) HeightText.Text=lastChoice.N4Height;
                    if(!string.IsNullOrEmpty(lastChoice.N4L2)) L2Text.Text=lastChoice.N4L2;
                    L3Text.Text=lastChoice.N4L3??"";
                    L4Text.Text=lastChoice.N4L4??"";
                    EquipmentOdText.Text=lastChoice.N4Od??"";
                    PreweldText.Text=string.IsNullOrEmpty(lastChoice.N4Preweld)
                        ? "0" : lastChoice.N4Preweld;
                    ReverseCheck.IsChecked=lastChoice.N4Reverse;
                    KeepLineCheck.IsChecked=lastChoice.N4KeepLine;
                    ShowPreweldCheck.IsChecked=lastChoice.N4ShowPreweld;
                }
                else
                {
                    TypeCombo.SelectedIndex=Math.Max(0,Math.Min(types-1,lastChoice.N3TypeIndex));
                    SubtypeCombo.SelectedIndex=Math.Max(0,Math.Min(subtypes-1,lastChoice.N3SubtypeIndex));
                    SetSubtypeDefaults();
                    if(!string.IsNullOrEmpty(lastChoice.N3Height)) HeightText.Text=lastChoice.N3Height;
                    ReverseCheck.IsChecked=lastChoice.N3Reverse;
                    KeepLineCheck.IsChecked=lastChoice.N3KeepLine;
                }
            }
            catch { /* 恢复失败就用当前默认值，不要挡住页面 */ }
        }
        /// <summary>记住本次选择。N3 与 N4 共用一个 JSON 文件，因此只改自己那套字段。</summary>
        private void SaveLastChoice()
        {
            try
            {
                if(isDouble)
                {
                    lastChoice.N4TypeIndex=Math.Max(0,TypeCombo.SelectedIndex);
                    lastChoice.N4SubtypeIndex=Math.Max(0,SubtypeCombo.SelectedIndex);
                    lastChoice.N4Height=HeightText.Text??"";
                    lastChoice.N4L2=L2Text.Text??"";
                    lastChoice.N4L3=L3Text.Text??"";
                    lastChoice.N4L4=L4Text.Text??"";
                    lastChoice.N4Od=EquipmentOdText.Text??"";
                    lastChoice.N4Preweld=PreweldText.Text??"0";
                    lastChoice.N4Reverse=ReverseCheck.IsChecked==true;
                    lastChoice.N4KeepLine=KeepLineCheck.IsChecked==true;
                    lastChoice.N4ShowPreweld=ShowPreweldCheck.IsChecked==true;
                }
                else
                {
                    lastChoice.N3TypeIndex=Math.Max(0,TypeCombo.SelectedIndex);
                    lastChoice.N3SubtypeIndex=Math.Max(0,SubtypeCombo.SelectedIndex);
                    lastChoice.N3Height=HeightText.Text??"";
                    lastChoice.N3Reverse=ReverseCheck.IsChecked==true;
                    lastChoice.N3KeepLine=KeepLineCheck.IsChecked==true;
                }
                BracketLastChoice.Save(lastChoice);
            }
            catch { }
        }
        public void OnActivated()
        {
            active=true;BracketLocateTool.Picked+=OnPicked;BracketLocateTool.Ended+=OnEnded;
        }
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            active=false;BracketLocateTool.Picked-=OnPicked;BracketLocateTool.Ended-=OnEnded;
            if(locating)BracketLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览";UpdateE();
        }
        private void SetSubtypeDefaults()
        {
            int i=Math.Max(0,SubtypeCombo.SelectedIndex);
            HeightText.Text=BracketCatalog.MinH[i].ToString("0",CultureInfo.InvariantCulture);
            L2Text.Text=BracketCatalog.MinL2[i].ToString("0",CultureInfo.InvariantCulture);
            SectionText.Text="横担："+BracketCatalog.A[i]+"    斜撑："+BracketCatalog.B[i]+
                (isDouble?"\n连接横担："+BracketCatalog.C[i]:"")+"\nN8 板型："+
                BracketCatalog.PlateType[i];
        }
        private void Subtype_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready)return;SetSubtypeDefaults();Changed();SaveLastChoice();
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {if(ready){Changed();SaveLastChoice();}}
        private void Height_TextChanged(object sender,TextChangedEventArgs e)
        {
            if(!ready)return;
            UpdateE();Changed();SaveLastChoice();
        }
        private bool UpdateE()
        {
            if(isDouble)return true;
            if(line==null)
            {
                EText.Text="E = 横担长度 − H；点取辅助线后计算（最小 150 mm）。";
                EText.Foreground=Brushes.Black;return true;
            }
            double h;
            if(!double.TryParse(HeightText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out h)&&
                !double.TryParse(HeightText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out h))
            {
                EText.Text="H 输入不合规，无法计算 E。";
                EText.Foreground=Brushes.DarkRed;ConfirmButton.IsEnabled=false;return false;
            }
            int i=Math.Max(0,SubtypeCombo.SelectedIndex);
            double thickness=N8Catalog.Resolve(BracketCatalog.PlateType[i],"H",0,G2MountFace.Wall).T;
            double length=Math.Sqrt(line.AxisX*line.AxisX+line.AxisY*line.AxisY+line.AxisZ*line.AxisZ);
            double beamLength=length-thickness;
            double margin=BracketCalculator.N3EndMargin(length,thickness,h);
            bool valid=margin>=BracketCalculator.MinimumN3EndMargin;
            EText.Text="横担长度 "+beamLength.ToString("0.#")+" mm − H "+h.ToString("0.#")+
                " mm = E "+margin.ToString("0.#")+" mm（最小 150 mm）"+
                (valid?"":"\n输入不合规：末端太小，不合图集要求；请减小 H 或加长辅助线。");
            EText.Foreground=valid?Brushes.Black:Brushes.DarkRed;
            if(!valid)ConfirmButton.IsEnabled=false;
            return valid;
        }
        private void Changed()
        {
            UpdateE();
            if(line==null)return;
            dirty=true;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览 ●";
            PreviewText.Text="参数已变更，点击一次“更新预览”后即可确认。";
        }
        private static double Number(string text,string name,bool optional=false)
        {
            if(optional&&string.IsNullOrWhiteSpace(text))return 0;
            double value;
            if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(name+"应为数字。");
            return value;
        }
        private BracketParameters Parameters()
        {
            return new BracketParameters {Double=isDouble,Subtype="ABCDEF"[Math.Max(0,SubtypeCombo.SelectedIndex)],
                Type=Math.Max(0,TypeCombo.SelectedIndex)+1,
                HeightMm=Number(HeightText.Text,"H"),Reverse=ReverseCheck.IsChecked==true,
                KeepAuxiliaryLine=KeepLineCheck.IsChecked==true,
                L2Mm=isDouble?Number(L2Text.Text,"L2"):0,
                L3Mm=isDouble?Number(L3Text.Text,"L3",true):0,
                L4Mm=isDouble?Number(L4Text.Text,"L4",true):0,
                EquipmentOdMm=isDouble?Number(EquipmentOdText.Text,"设备外径 2R"):0,
                PreweldMm=isDouble?Number(PreweldText.Text,"D",true):0,
                ShowPreweld=isDouble&&ShowPreweldCheck.IsChecked==true};
        }
        private void Regenerate()
        {
            if(line==null)return;
            try
            {
                BracketCalculator.ValidateHorizontal(line);
                var plan=BracketCalculator.Calculate(Parameters(),
                    Math.Sqrt(line.AxisX*line.AxisX+line.AxisY*line.AxisY+line.AxisZ*line.AxisZ));
                preview.Show(plan,line);dirty=false;UpdateButton.Content="更新预览";
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="编号："+plan.Number+"\n"+plan.Specification+
                    "\n垂直荷载："+plan.VerticalLoad+" kN"+
                    (isDouble?"    水平荷载："+plan.HorizontalLoad+" kN":"");
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
                    preview.Cancel();ConfirmButton.IsEnabled=false;
                    dirty=false;UpdateButton.Content="更新预览";
                    line=PipeClampReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ);
                    BracketCalculator.ValidateHorizontal(line);
                    UpdateE();
                    KeepLineCheck.IsEnabled=!line.IsFromReference;
                    if(line.IsFromReference)KeepLineCheck.IsChecked=true;
                    Regenerate();
                }
                catch(Exception ex){line=null;UpdateE();Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;PreviewText.Text="已结束点取。";
            UpdateButton.Content="更新预览";UpdateE();
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{BracketLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){BracketLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();line=null;dirty=false;ConfirmButton.IsEnabled=false;
             UpdateButton.Content="更新预览";UpdateE();}
         catch(Exception ex){Status(ex.Message,true);}}
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;
            Status("正在写入三角架清单…",false);
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=Stopwatch.StartNew();
            try
            {
                bool delete=line!=null&&!line.IsPipe&&line.IsAuxiliaryLine&&
                    !line.IsFromReference&&KeepLineCheck.IsChecked!=true;
                ulong id=line==null?0:line.ElementId;
                preview.Confirm();
                if(delete)DeleteLine(id);
                line=null;ConfirmButton.IsEnabled=false;
                UpdateButton.Content="更新预览";UpdateE();
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
