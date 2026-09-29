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
    internal partial class PortalFramePage:UserControl,IWorkspacePage
    {
        private readonly PortalFramePreviewSession preview=new PortalFramePreviewSession();
        private PipeClampSelection line;
        private bool active,ready,locating,dirty;
        public string PageId{get{return "portal-frame";}}
        public string PageTitle{get{return "门型架";}}
        public string PageSubtitle{get{return "D8 / D13 / G5 / G6";}}
        public FrameworkElement View{get{return this;}}
        internal PortalFramePage()
        {
            InitializeComponent();
            KindCombo.ItemsSource=new[]{"D8 角钢与槽钢","D13 H 型钢","G5 地面生根","G6 H 型钢与双槽钢"};
            KindCombo.SelectedIndex=0;
            ready=true;UpdateKind(true);
            PageLastInput.Restore(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "SpanText","HeadingText","NameText","KeepLineCheck");
        }
        public void OnActivated(){active=true;PortalFrameLocateTool.Picked+=OnPicked;
            PortalFrameLocateTool.Ended+=OnEnded;}
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "SpanText","HeadingText","NameText","KeepLineCheck");
            active=false;PortalFrameLocateTool.Picked-=OnPicked;PortalFrameLocateTool.Ended-=OnEnded;
            if(locating)PortalFrameLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览";
        }
        private string Kind{get{return PortalFrameCatalog.Kinds[Math.Max(0,KindCombo.SelectedIndex)];}}
        private char Variant{get{return PortalFrameCatalog.Variants(Kind)[Math.Max(0,VariantCombo.SelectedIndex)];}}
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {if(!ready)return;UpdateKind(true);Changed();}
        private void UpdateKind(bool reset)
        {
            string kind=Kind;
            if(reset)
            {
                VariantCombo.ItemsSource=null;
                var chars=PortalFrameCatalog.Variants(kind);
                var choices=new string[chars.Length];
                for(int i=0;i<chars.Length;i++)choices[i]=chars[i].ToString();
                VariantCombo.ItemsSource=choices;VariantCombo.SelectedIndex=0;
                TypeCombo.ItemsSource=kind=="D8"
                    ?new[]{"类型 1：正门端焊","类型 2：正门侧焊","类型 3：倒门端焊","类型 4：倒门侧焊"}
                    :kind=="D13"?new[]{"类型 1：正门","类型 2：倒门"}
                    :new[]{"地面生根"};
                TypeCombo.SelectedIndex=0;SpanText.Text=kind=="D8"?"500":"1000";
                NameText.Text=kind;
            }
            SpanLabel.Text=kind=="D8"?"立柱净距 B（mm）":
                kind=="G6"?"两柱外缘间距 L（mm）":"横担全长 L（mm）";
            var v=PortalFrameCatalog.Variant(kind,Variant);
            SectionText.Text="立柱："+v.PostSpecification+"    横担："+v.ArmSpecification+
                (kind=="G6"?" ×2，槽钢腹板净距 S="+v.ChannelGap+" mm":"")+
                (v.Ground==null?"":"\n地面生根：锚板 "+v.Ground.PlateSide+"×"+
                    v.Ground.PlateSide+"×"+v.Ground.PlateThickness+
                    "；每柱 4 根 M"+v.Ground.BoltDiameter+" 锚栓；地坪最小厚度 "+
                    v.Ground.MinPavement+" mm");
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {if(!ready)return;UpdateKind(false);Changed();}
        private void Changed()
        {if(line==null)return;dirty=true;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览 ●";PreviewText.Text="参数已变更，请更新预览后再确定生成。";}
        private static double Number(string text,string label)
        {double value;if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
            !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
            throw new InvalidOperationException(label+"应为数字。");return value;}
        private PortalFrameParameters Parameters()
        {return new PortalFrameParameters{Kind=Kind,Variant=Variant,
            Type=Math.Max(0,TypeCombo.SelectedIndex)+1,
            SpanMm=Number(SpanText.Text,Kind=="D8"?"B":"L"),
            HeadingDegrees=Number(HeadingText.Text,"方向角"),Name=NameText.Text,
            KeepAuxiliaryLine=KeepLineCheck.IsChecked==true};}
        private static double LineHeightMm(PipeClampSelection value)
        {return Math.Abs(value.AxisZ);}
        private static void ValidateLine(PipeClampSelection value)
        {
            if(value.IsPipe||!value.IsAuxiliaryLine)
                throw new InvalidOperationException("请选择绘制好的竖直辅助直线。");
            double horizontal=Math.Sqrt(value.AxisX*value.AxisX+value.AxisY*value.AxisY);
            if(LineHeightMm(value)<1e-9||Math.Atan2(horizontal,LineHeightMm(value))>5*Math.PI/180)
                throw new InvalidOperationException("辅助线与竖直方向的夹角不得超过 5°。");
        }
        private void Regenerate()
        {
            if(line==null)return;
            try
            {
                ValidateLine(line);
                var plan=PortalFrameCalculator.Calculate(Parameters(),LineHeightMm(line));
                preview.Show(plan,line);dirty=false;UpdateButton.Content="更新预览";
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="编号："+plan.Number+"\n"+plan.AssemblySpecification+
                    "\n净距 B="+plan.SpanMm.ToString("0.#")+" mm；立柱下料="+
                    plan.PostLengthMm.ToString("0.#")+" mm"+
                    (plan.AllowableLoadKn.HasValue?"\n允许垂直荷载："+
                        plan.AllowableLoadKn.Value.ToString("0.#")+" kN":"\n该 H/L 档位无允许荷载值");
                Status("门型架预览已生成。",false);
            }
            catch(Exception ex){ConfirmButton.IsEnabled=false;PreviewText.Text="预览未更新："+ex.Message;
                Status(ex.Message,true);}
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
        {locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";UpdateButton.Content="更新预览";}
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{PortalFrameLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){PortalFrameLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();line=null;dirty=false;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览";PreviewText.Text="已取消预览。";}
            catch(Exception ex){Status(ex.Message,true);}}
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;Status("正在写入门型架清单…",false);
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=Stopwatch.StartNew();
            try
            {
                bool delete=line!=null&&line.IsAuxiliaryLine&&!line.IsFromReference&&
                    KeepLineCheck.IsChecked!=true;
                ulong id=line==null?0:line.ElementId;
                preview.Confirm();
                if(delete)DeleteLine(id);
                line=null;UpdateButton.Content="更新预览";
                PreviewText.Text="已确认生成并写入清单，可继续点取下一条辅助线。";
                Status("门型架已生成（"+timer.Elapsed.TotalSeconds.ToString("0.0")+" 秒）。",false);
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
