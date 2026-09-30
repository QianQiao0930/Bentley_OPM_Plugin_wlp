using System;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class ColdRiserGuidePage:UserControl,IWorkspacePage
    {
        private readonly L7GuidePreviewSession preview=new L7GuidePreviewSession();
        private PipeClampSelection selection;
        private DPoint3d center;
        private DVector3d axis;
        private double angle,length=L7GuideCatalog.MinLengthMm;
        private bool active,locating,initializing;
        public string PageId {get{return "cold-riser-guide";}}
        public string PageTitle {get{return "保冷立管导向架";}}
        public string PageSubtitle {get{return "L7 / L8 · 结构或设备上生根";}}
        public FrameworkElement View {get{return this;}}
        internal ColdRiserGuidePage()
        {
            initializing=true;
            InitializeComponent();
            SeriesCombo.ItemsSource=new[]{"L7 · 结构上生根","L8 · 结构或设备上生根"};
            SeriesCombo.SelectedIndex=0;
            KindCombo.ItemsSource=new[]{"类型 1 · A22 + 构件 A","类型 2 · A24 四螺栓管夹"};
            MaterialCombo.ItemsSource=new[]{"C1","L","S"};MaterialCombo.SelectedIndex=0;
            KindCombo.SelectedIndex=0;
            var dns=L7GuideCatalog.Dns;
            DnCombo.ItemsSource=dns.Select(n=>"DN"+n).ToArray();
            DnCombo.SelectedIndex=Array.IndexOf(dns,100);
            PageLastInput.Restore(this,PageId,"KindCombo","DnCombo","ColdText",
                "BearingLengthText","SeriesCombo","MaterialCombo");
            initializing=false;Series_Changed(null,null);
        }
        public void OnActivated()
        {
            active=true;
            PipeClampLocateTool.Picked+=OnPicked;
            PipeClampLocateTool.Ended+=OnLocateEnded;
            L7GuideDirectionTool.Oriented+=OnOriented;
            L7GuideDirectionTool.Cancelled+=OnDirectionCancelled;
            L7GuideLengthTool.LengthChanged+=OnLengthChanged;
            L7GuideLengthTool.Accepted+=OnLengthAccepted;
            L7GuideLengthTool.Cancelled+=OnLengthCancelled;
            L7GuideLengthTool.Failed+=OnLengthFailed;
        }
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","DnCombo","ColdText",
                "BearingLengthText","SeriesCombo","MaterialCombo");
            active=false;
            PipeClampLocateTool.Picked-=OnPicked;
            PipeClampLocateTool.Ended-=OnLocateEnded;
            L7GuideDirectionTool.Oriented-=OnOriented;
            L7GuideDirectionTool.Cancelled-=OnDirectionCancelled;
            L7GuideLengthTool.LengthChanged-=OnLengthChanged;
            L7GuideLengthTool.Accepted-=OnLengthAccepted;
            L7GuideLengthTool.Cancelled-=OnLengthCancelled;
            L7GuideLengthTool.Failed-=OnLengthFailed;
            if(PipeClampLocateTool.IsActive&&locating)PipeClampLocateTool.End();
            if(L7GuideDirectionTool.IsActive)L7GuideDirectionTool.End();
            if(L7GuideLengthTool.IsActive)L7GuideLengthTool.End();
            locating=false;selection=null;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            ConfirmButton.IsEnabled=false;
        }
        private int Dn()
        {
            var text=DnCombo.SelectedItem as string??"DN100";
            return int.Parse(text.Substring(2),CultureInfo.InvariantCulture);
        }
        private L7GuideKind Kind()
        {return KindCombo.SelectedIndex==1?L7GuideKind.Type2:L7GuideKind.Type1;}
        private ColdRiserGuideSeries Series()
        {return SeriesCombo.SelectedIndex==1?ColdRiserGuideSeries.L8:ColdRiserGuideSeries.L7;}
        private string LengthSymbol {get{return Series()==ColdRiserGuideSeries.L8?"L1":"L";}}
        private bool HasMember()
        {return Series()==ColdRiserGuideSeries.L8 || Kind()==L7GuideKind.Type1;}
        private void Series_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||KindCombo==null)return;
            EndOperation();
            int index=Math.Max(0,KindCombo.SelectedIndex);
            KindCombo.ItemsSource=Series()==ColdRiserGuideSeries.L8?
                new[]{"类型 1 · A22 + 构件 A","类型 2 · A22 + 构件 A + N8"}:
                new[]{"类型 1 · A22 + 构件 A","类型 2 · A24 四螺栓管夹"};
            KindCombo.SelectedIndex=index;UpdateKindUi();
        }
        private void Data_Changed(object sender,RoutedEventArgs e)
        {
            if(initializing||DataText==null)return;
            try {if(preview.HasPreview){preview.Cancel();ConfirmButton.IsEnabled=false;}}
            catch(Exception ex){Status(ex.Message,true);}
            UpdateData();
        }
        private void UpdateData()
        {
            try {
                double? travel=L7GuideCatalog.AxialTravel(BearingLength());
                DataText.Text="允许荷载："+L7GuideCatalog.AllowableLoad(Dn()).ToString("0.##")+
                    " kN；允许轴向位移："+(travel.HasValue?travel.Value+" mm":"当前夹板长度未列入标准表")+
                    "。\n"+L7GuideCatalog.Material(MaterialCombo.SelectedItem as string??"C1");
            }catch(Exception ex){DataText.Text=ex.Message;}
        }
        private void UpdateKindUi()
        {
            bool type2=!HasMember();
            MaterialPanel.Visibility=Series()==ColdRiserGuideSeries.L8?Visibility.Visible:Visibility.Collapsed;
            DataText.Visibility=MaterialPanel.Visibility;
            Type1Info.Text=Series()==ColdRiserGuideSeries.L8?
                "L 为沿管轴夹板长度（≥300 mm），L1 为管中心至构件末端（300～1000 mm）；类型 2 按表 1 选角钢/槽钢及 N8 连接板。":
                "类型 1：构件 A 按 A22 内径 A 选型；L 从管中心至末端，拉伸范围 300～1000 mm。";
            UpdateData();
            Type1Info.Visibility=type2?Visibility.Collapsed:Visibility.Visible;
            ProcessText.Text=type2?
                "类型 2：点取标高 → 在垂直管轴的 XY 罗盘内定方向 → 左键出预览 → 确定。":
                "点取标高 → 在垂直管轴的 XY 罗盘内定方向 → 拉伸构件 A → 预览 → 确定。";
            MeasureText.Text=type2?"承重夹板长度默认 300 mm；无需拉伸构件 A。":
                LengthSymbol+" = 300 mm；待点取方向";
        }
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||Type1Info==null)return;
            EndOperation();UpdateKindUi();
            PreviewText.Text="类型已切换，请重新点取立管。";
        }
        private double Cold()
        {
            double value;
            if(!double.TryParse(ColdText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(ColdText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException("保冷厚度必须是数字。");
            return value;
        }
        private double BearingLength()
        {
            double value;
            if(!double.TryParse(BearingLengthText.Text,NumberStyles.Float,
                CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(BearingLengthText.Text,NumberStyles.Float,
                    CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException("承重夹板长度必须是数字。");
            return value;
        }
        private L7GuidePlan Plan()
        {
            if(selection==null)throw new InvalidOperationException("请先点取立管。");
            int dn=Dn();
            if(selection.IsPipe)
            {
                int? matched=A22ClampCatalog.MatchDn(selection.NominalMm);
                if(!matched.HasValue)
                    throw new InvalidOperationException("无法识别所选管道的公称直径，请检查管道 EC 属性。");
                dn=matched.Value;
            }
            double outside=selection.IsPipe&&selection.OutsideMm.HasValue&&
                selection.OutsideMm.Value>0?selection.OutsideMm.Value:E1GuideCatalog.Outside(dn);
            double cold=selection.IsPipe&&selection.InsulationMm.HasValue?
                selection.InsulationMm.Value:Cold();
            return L7GuideCalculator.Calculate(Series(),Kind(),dn,outside,cold,length,angle,
                selection.PipeNumber,BearingLength(),MaterialCombo.SelectedItem as string??"C1");
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                if(PipeClampLocateTool.IsActive&&locating){Status("可直接点取下一处，无需再点开始点取。",false);return;}
                if(L7GuideDirectionTool.IsActive)L7GuideDirectionTool.End();
                if(L7GuideLengthTool.IsActive)L7GuideLengthTool.End();
                preview.Cancel();ConfirmButton.IsEnabled=false;selection=null;
                PipeClampLocateTool.Begin();locating=true;
                PreviewText.Text="请点取立管或竖直辅助线上的安装标高。";
                Status("请选择立管或竖直辅助线。",false);
            }
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            PipeClampLocateTool.RetireForHandoff();locating=false;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active)return;
                try
                {
                    selection=PipeClampReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ);
                    VerticalPipeSupportCalculator.ValidateVertical(selection);
                    int? matched=selection.IsPipe?A22ClampCatalog.MatchDn(selection.NominalMm):null;
                    if(matched.HasValue&&matched.Value<=150)
                    {
                        var choice="DN"+matched.Value;
                        DnCombo.SelectedItem=choice;
                    }
                    var model=Session.Instance.GetActiveDgnModel();
                    double scale=model.GetModelInfo().UorPerMeter/1000.0;
                    var projected=selection.ProjectedCenter();
                    center=new DPoint3d(projected[0]*scale,projected[1]*scale,projected[2]*scale);
                    axis=new DVector3d(selection.AxisX,selection.AxisY,selection.AxisZ);
                    angle=0;length=L7GuideCatalog.MinLengthMm;
                    if(HasMember())
                    {
                        // 初始 L=300 可能尚短于大保冷层的管夹半径，仍允许拉伸。
                        double initialLength=length;
                        length=L7GuideCatalog.MaxLengthMm;
                        try{Plan();}finally{length=initialLength;}
                    }
                    else Plan();
                    L7GuideDirectionTool.Begin(center,axis,HasMember());
                    PreviewText.Text="标高已确定；请在 XY 罗盘平面内转动，左键锁定安装方向。";
                }
                catch(Exception ex)
                {selection=null;PreviewText.Text="点取失败："+ex.Message;Status(ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnLocateEnded()
        {
            if(!active)return;
            locating=false;PreviewText.Text="已结束点取。";
        }
        private void OnOriented(double chosen,int view,double x,double y)
        {
            if(!active||selection==null)return;
            angle=chosen;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||selection==null)return;
                try
                {
                    if(!HasMember())
                    {
                        Regenerate();
                        return;
                    }
                    double[] zero,turn,along;
                    A1ClampCalculator.RadialFrame(new[]{axis.X,axis.Y,axis.Z},
                        out zero,out turn,out along);
                    double radians=angle*Math.PI/180,c=Math.Cos(radians),s=Math.Sin(radians);
                    var radial=new DVector3d(c*zero[0]+s*turn[0],
                        c*zero[1]+s*turn[1],c*zero[2]+s*turn[2]);
                    L7GuideLengthTool.Begin(center,radial,view,x,y);
                    PreviewText.Text="方向 "+angle.ToString("0.#")+"° 已确定；请沿构件 A 方向拉伸 "+LengthSymbol+"。";
                }
                catch(Exception ex){Status(ex.Message,true);PreviewText.Text=ex.Message;}
            }),DispatcherPriority.Background);
        }
        private void OnDirectionCancelled()
        {if(active)PreviewText.Text="已取消方向选择；可重新开始点取。";}
        private void OnLengthChanged(double value)
        {
            if(!active)return;
            length=value;
            MeasureText.Text=LengthSymbol+" = "+value.ToString("0.#")+" mm（从管中心计）";
        }
        private void OnLengthAccepted(double value)
        {
            if(!active||selection==null)return;
            length=value;Regenerate();
        }
        private void OnLengthCancelled()
        {if(active)PreviewText.Text="已取消长度拉伸；可重新开始点取。";}
        private void OnLengthFailed(string message)
        {if(active)Status(message,true);}
        private void Regenerate()
        {
            if(selection==null)return;
            try
            {
                var plan=Plan();preview.Show(plan,center,axis);
                ConfirmButton.IsEnabled=true;
                MeasureText.Text=!plan.HasMember?
                    "夹板长 "+plan.BearingLengthMm.ToString("0.#")+" mm；方向 "+
                        plan.AngleDeg.ToString("0.#")+"°":
                    LengthSymbol+" = "+plan.LengthMm.ToString("0.#")+" mm；方向 "+
                        plan.AngleDeg.ToString("0.#")+"°";
                PreviewText.Text="预览："+plan.Number+"；"+plan.Specification+
                    (!plan.HasMember?"。":
                        "；构件 A 实长 "+plan.MemberLengthMm.ToString("0.#")+" mm。");
                Status(Series()+" 预览已生成；点击确定后写入附加项。",false);
            }
            catch(Exception ex)
            {ConfirmButton.IsEnabled=false;PreviewText.Text="预览未更新："+ex.Message;Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {EndOperation();PreviewText.Text="已结束本次操作。";}
        private void EndOperation()
        {
            if(PipeClampLocateTool.IsActive&&locating)PipeClampLocateTool.End();
            if(L7GuideDirectionTool.IsActive)L7GuideDirectionTool.End();
            if(L7GuideLengthTool.IsActive)L7GuideLengthTool.End();
            locating=false;
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            selection=null;ConfirmButton.IsEnabled=false;
        }
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                EndOperation();PreviewText.Text="预览已取消。";
            }
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                var watch=Stopwatch.StartNew();
                preview.Confirm();watch.Stop();
                string elapsed=watch.Elapsed.TotalMilliseconds.ToString("0.0",
                    CultureInfo.InvariantCulture)+" ms";
                ConfirmButton.IsEnabled=false;selection=null;
                PreviewText.Text="已确认生成并写入附加项；写入耗时 "+elapsed+"。可继续点取下一处。";
                Status(Series()+" 保冷立管导向架已生成；附加项写入耗时 "+elapsed+"。",false);
            }
            catch(Exception ex){Status("确认失败："+ex.Message,true);}
        }
        private static void Status(string text,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);}
    }
}
