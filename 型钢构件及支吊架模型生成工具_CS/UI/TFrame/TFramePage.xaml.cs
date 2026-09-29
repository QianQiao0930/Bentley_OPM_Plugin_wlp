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
    internal partial class TFramePage:UserControl,IWorkspacePage
    {
        private readonly TFramePreviewSession preview=new TFramePreviewSession();
        private PipeClampSelection line;
        private bool active,ready,locating,dirty,updatingKind;
        public string PageId{get{return "t-frame";}}
        public string PageTitle{get{return "T 型架";}}
        public string PageSubtitle{get{return "D12 / G4 / D15";}}
        public FrameworkElement View{get{return this;}}
        internal TFramePage()
        {
            InitializeComponent();
            KindCombo.ItemsSource=new[]{"D12 钢结构生根","G4 地面生根","D15 水平 T 形架"};
            JointCombo.ItemsSource=new[]{"A","B","C","D","E","F"};
            KindCombo.SelectedIndex=0;JointCombo.SelectedIndex=0;
            ready=true;UpdateKind(true);
            PageLastInput.Restore(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "DimensionText","HeadingText","JointCombo","StiffenerText","KeepLineCheck");
        }
        public void OnActivated(){active=true;TFrameLocateTool.Picked+=OnPicked;
            TFrameLocateTool.Ended+=OnEnded;}
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","VariantCombo","TypeCombo",
                "DimensionText","HeadingText","JointCombo","StiffenerText","KeepLineCheck");
            active=false;TFrameLocateTool.Picked-=OnPicked;TFrameLocateTool.Ended-=OnEnded;
            if(locating)TFrameLocateTool.End();locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;UpdateButton.Content="更新预览";
            UpdateLimits();
        }
        private string Kind{get{return TFrameCatalog.Kinds[Math.Max(0,KindCombo.SelectedIndex)];}}
        private char Variant{get{return TFrameCatalog.Variants(Kind)[Math.Max(0,VariantCombo.SelectedIndex)];}}
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {if(!ready)return;UpdateKind(true);Changed();}
        private void UpdateKind(bool reset)
        {
            string kind=Kind;
            if(reset)
            {
                updatingKind=true;
                try
                {
                    string variants=TFrameCatalog.Variants(kind);var items=new string[variants.Length];
                    for(int i=0;i<variants.Length;i++)items[i]=variants[i].ToString();
                    VariantCombo.ItemsSource=items;VariantCombo.SelectedIndex=0;
                    TypeCombo.ItemsSource=kind=="G4"?new[]{"类型 1：正 T 形架"}:
                        kind=="D15"?new[]{"类型 1：对称","类型 2：偏心"}:
                        new[]{"类型 1：正 T 形架","类型 2：倒 T 形吊架"};
                    TypeCombo.SelectedIndex=0;
                    DimensionText.Text=kind=="D15"?"200":"250";
                }
                finally{updatingKind=false;}
            }
            bool horizontal=kind=="D15";
            HeadingPanel.Visibility=horizontal?Visibility.Collapsed:Visibility.Visible;
            D15Panel.Visibility=horizontal?Visibility.Visible:Visibility.Collapsed;
            DimensionLabel.Text=horizontal?"构件 B 高度 L2（mm）":"横担全长 L（mm）";
            KindHint.Text=horizontal
                ?"D15 点取水平辅助直线；线长=L1+构件 B 腹板厚。"
                :"点取整组中心竖直辅助直线；线长为 H。";
            var v=TFrameCatalog.Variant(kind,Variant);
            SectionText.Text="构件 A："+v.SpecA+"    构件 B："+v.SpecB+
                (v.Ground==null?"":"\n地面生根：锚板 "+v.Ground.PlateSide+"×"+
                    v.Ground.PlateSide+"×"+v.Ground.PlateThickness+"，4 根 M"+
                    v.Ground.BoltDiameter+" 锚栓，地坪最小厚度 "+v.Ground.MinPavement+" mm")+
                (horizontal?"\n筋板尺寸只加入编号，不生成筋板实体。":"");
            UpdateLimits();
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {if(!ready||updatingKind)return;UpdateKind(false);Changed();}
        private static bool TryNumber(string text,out double value)
        {return (double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)||
            double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))&&
            !double.IsNaN(value)&&!double.IsInfinity(value);}
        private static string Fmt(double value){return value.ToString("0.##",CultureInfo.CurrentCulture);}
        private static string LimitValue(string label,double max,double? current,ref bool exceeded)
        {
            if(!current.HasValue)return label+" 上限 "+Fmt(max)+" mm；当前：未点取辅助线";
            double value=current.Value;
            if(value>max+1){exceeded=true;return label+" 上限 "+Fmt(max)+" mm；当前 "+
                Fmt(value)+" mm（超出 "+Fmt(value-max)+" mm）";}
            return label+" 上限 "+Fmt(max)+" mm；当前 "+Fmt(value)+" mm"+
                (value>max?"（在 1 mm 校验容差内）":"");
        }
        private void UpdateLimits()
        {
            if(!ready)return;
            try
            {
                int type=Math.Max(0,TypeCombo.SelectedIndex)+1;
                var limits=TFrameCalculator.Limits(Kind,Variant,type);
                bool exceeded=false;double input;
                bool valid=TryNumber(DimensionText.Text,out input);
                string span=valid?LimitValue(limits.Horizontal?"L2":"L",limits.MaxSpanMm,
                    input,ref exceeded):"当前 "+(limits.Horizontal?"L2":"L")+" 输入不是数字";
                if(!valid)exceeded=true;
                if(limits.Horizontal)
                {
                    double? lineLength=line==null?(double?)null:Length(line);
                    double? l1=lineLength.HasValue?lineLength.Value-limits.WebThicknessMm:(double?)null;
                    string first=LimitValue("L1",limits.MaxHeightMm,l1,ref exceeded);
                    string axis=LimitValue("辅助线长",limits.MaxLineMm,lineLength,ref exceeded);
                    LimitText.Text="当前子项与类型的标准上限（mm）：\n"+first+"\n"+span+"\n"+
                        axis+"（tb="+Fmt(limits.WebThicknessMm)+" mm）";
                }
                else
                {
                    double? height=line==null?(double?)null:Math.Abs(line.AxisZ);
                    LimitText.Text="当前子项的标准上限（mm）：\n"+
                        LimitValue("H",limits.MaxHeightMm,height,ref exceeded)+"\n"+span;
                }
                LimitText.Foreground=(System.Windows.Media.Brush)FindResource(exceeded?"ErrorBrush":"StatusBrush");
            }
            catch(Exception ex){LimitText.Text="标准上限暂无法读取："+ex.Message;
                LimitText.Foreground=(System.Windows.Media.Brush)FindResource("ErrorBrush");}
        }
        private void Stiffener_Changed(object sender,TextChangedEventArgs e)
        {
            if(!ready||Kind!="D15"||dirty)return;
            string number=preview.UpdateStiffener(StiffenerText.Text);
            if(number!=null)PreviewText.Text="编号："+number+"\n筋板尺寸已同步到清单；几何预览未变化。";
        }
        private void Changed()
        {if(line==null)return;dirty=true;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览 ●";
            PreviewText.Text="参数已变更，请更新预览后再确定生成。";}
        private static double Number(string text,string label)
        {double value;if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
            !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
            throw new InvalidOperationException(label+"应为数字。");return value;}
        private TFrameParameters Parameters()
        {return new TFrameParameters{Kind=Kind,Variant=Variant,Type=Math.Max(0,TypeCombo.SelectedIndex)+1,
            SpanMm=Number(DimensionText.Text,Kind=="D15"?"L2":"L"),
            HeadingDegrees=Kind=="D15"?0:Number(HeadingText.Text,"方向角"),
            WeldJoint="ABCDEF"[Math.Max(0,JointCombo.SelectedIndex)],
            Stiffener=StiffenerText.Text,KeepAuxiliaryLine=KeepLineCheck.IsChecked==true};}
        private static double Length(PipeClampSelection value)
        {return Math.Sqrt(value.AxisX*value.AxisX+value.AxisY*value.AxisY+value.AxisZ*value.AxisZ);}
        private void ValidateLine(PipeClampSelection value)
        {
            if(value.IsPipe||!value.IsAuxiliaryLine)
                throw new InvalidOperationException("请选择绘制好的普通辅助直线。");
            double horizontal=Math.Sqrt(value.AxisX*value.AxisX+value.AxisY*value.AxisY);
            double angle=Kind=="D15"?Math.Atan2(Math.Abs(value.AxisZ),horizontal):
                Math.Atan2(horizontal,Math.Abs(value.AxisZ));
            if(Length(value)<150||angle>5*Math.PI/180)
                throw new InvalidOperationException(Kind=="D15"
                    ?"请选择长度不小于 150 mm 的水平辅助线（偏角不超过 5°）。"
                    :"请选择长度不小于 150 mm 的竖直辅助线（偏角不超过 5°）。");
        }
        private void Regenerate()
        {
            if(line==null)return;
            UpdateLimits();
            try
            {
                ValidateLine(line);
                var plan=TFrameCalculator.Calculate(Parameters(),Kind=="D15"?Length(line):Math.Abs(line.AxisZ));
                preview.Show(plan,line);dirty=false;UpdateButton.Content="更新预览";
                ConfirmButton.IsEnabled=true;
                PreviewText.Text="编号："+plan.Number+"\n"+plan.AssemblySpecification+
                    "\n构件 A 下料长="+plan.PostLengthMm.ToString("0.#")+
                    " mm；构件 B 下料长="+plan.L2Mm.ToString("0.#")+" mm"+
                    (plan.AllowableLoadKn.HasValue?"\n允许垂直荷载："+
                        plan.AllowableLoadKn.Value.ToString("0.##")+" kN":"\n当前 H/L 档位无允许荷载值");
                Status("T 型架预览已生成。",false);
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
                    UpdateLimits();
                    ValidateLine(line);
                    KeepLineCheck.IsEnabled=!line.IsFromReference;
                    if(line.IsFromReference)KeepLineCheck.IsChecked=true;
                    Regenerate();
                }
                catch(Exception ex){line=null;UpdateLimits();Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            line=null;dirty=false;ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";UpdateButton.Content="更新预览";UpdateLimits();}
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{TFrameLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){TFrameLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();line=null;dirty=false;ConfirmButton.IsEnabled=false;
            UpdateButton.Content="更新预览";PreviewText.Text="已取消预览。";UpdateLimits();}
            catch(Exception ex){Status(ex.Message,true);}}
        private async void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先更新预览。",true);return;}
            ConfirmButton.IsEnabled=false;Status("正在写入 T 型架清单…",false);
            await Dispatcher.Yield(DispatcherPriority.Background);
            var timer=Stopwatch.StartNew();
            try
            {
                bool delete=line!=null&&line.IsAuxiliaryLine&&!line.IsFromReference&&
                    KeepLineCheck.IsChecked!=true;
                ulong id=line==null?0:line.ElementId;
                preview.Confirm();if(delete)DeleteLine(id);
                line=null;UpdateButton.Content="更新预览";
                UpdateLimits();
                PreviewText.Text="已确认生成并写入清单，可继续点取下一条辅助线。";
                Status("T 型架已生成（"+timer.Elapsed.TotalSeconds.ToString("0.0")+" 秒）。",false);
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
