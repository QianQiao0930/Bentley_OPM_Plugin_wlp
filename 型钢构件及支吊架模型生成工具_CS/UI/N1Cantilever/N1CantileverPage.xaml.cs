using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
namespace SteelSectionProbe
{
    internal partial class N1CantileverPage:UserControl,IWorkspacePage
    {
        private readonly N1CantileverPreviewSession preview=new N1CantileverPreviewSession();
        private readonly string[] fields={"TypeCombo","SubtypeCombo","EquipmentOdText","PreweldText","L2Text","ReverseCheck","ShowPreweldCheck"};
        private PipeClampSelection line;
        private bool ready,active,locating,dirty;
        private int revision;
        public string PageId{get{return "n1-cantilever";}}
        public string PageTitle{get{return "N1 设备上生根单悬臂架";}}
        public string PageSubtitle{get{return "类型 1：悬臂 L1 · 类型 2：设备中心至立管中心 L";}}
        public FrameworkElement View{get{return this;}}
        internal N1CantileverPage()
        {
            InitializeComponent();TypeCombo.SelectedIndex=0;SubtypeCombo.SelectedIndex=0;
            PageLastInput.Restore(this,PageId,fields);ready=true;UpdateReadings();
        }
        public void OnActivated()
        {if(active)return;active=true;BracketLocateTool.Picked+=OnPicked;BracketLocateTool.Ended+=OnEnded;}
        public void OnDeactivated()
        {
            PageLastInput.Save(this,PageId,fields);active=false;revision++;
            BracketLocateTool.Picked-=OnPicked;BracketLocateTool.Ended-=OnEnded;
            if(locating)BracketLocateTool.End();locating=false;ClearPreview();
        }
        public void OnWorkspaceClosing(){OnDeactivated();}
        private static double Number(string text,string name)
        {
            double value;
            if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(name+"必须为数字。");
            return value;
        }
        private N1CantileverParameters Parameters()
        {
            int type=TypeCombo.SelectedIndex+1;
            return new N1CantileverParameters{Type=type,Subtype=(char)('A'+SubtypeCombo.SelectedIndex),
                EquipmentOdMm=type==2?Number(EquipmentOdText.Text,"设备外径"):0,
                PreweldMm=type==2||ShowPreweldCheck.IsChecked==true?Number(PreweldText.Text,"D"):0,
                L2Mm=type==2?Number(L2Text.Text,"L2"):0,ShowPreweld=ShowPreweldCheck.IsChecked==true,
                Reverse=ReverseCheck.IsChecked==true};
        }
        private N1CantileverFrame Frame()
        {
            if(line==null)throw new InvalidOperationException("请先点取水平辅助线。");
            return N1CantileverCalculator.Frame(line.StartX,line.StartY,line.StartZ,line.EndX,line.EndY,line.EndZ,
                ReverseCheck.IsChecked==true);
        }
        private N1CantileverPlan Plan()
        {return N1CantileverCalculator.Calculate(Parameters(),Frame().LengthMm);}
        private void UpdateReadings()
        {
            bool two=TypeCombo.SelectedIndex==1;
            EquipmentPanel.Visibility=two?Visibility.Visible:Visibility.Collapsed;
            PreweldPanel.Visibility=two||ShowPreweldCheck.IsChecked==true?Visibility.Visible:Visibility.Collapsed;
            InstructionText.Text=two?"请选择设备中心至立管中心的水平辅助线 L；标高为构件 A 顶面。":
                "请直接选择悬臂辅助线 L1：起点为连接板框架侧外表面，终点为悬臂末端；标高为构件 A 顶面。";
            LoadNoteText.Text=two?"荷载按设备外壁至立管中心距离 a 查表，不外推。预焊件占位不计入清单。":
                "类型 1 直接采用辅助线长，不使用设备或管道外径，也不附加 150 mm。由于未提供载荷位置，不计算允许荷载。";
            L2Panel.Visibility=two?Visibility.Visible:Visibility.Collapsed;
            try
            {
                var v=N1CantileverCatalog.Require((char)('A'+SubtypeCombo.SelectedIndex));
                SectionText.Text="构件 A："+v.SectionA+(two?"；构件 B："+v.SectionB:"")+"；连接板 N8-"+v.PlateType;
                if(line==null){DimensionsText.Text=two?"请选择设备中心至立管中心辅助线（L）。":"请选择悬臂辅助线（L1）。";return;}
                var p=Plan();DimensionsText.Text=two?"L="+p.LMm.ToString("0.###")+"；L1="+p.L1Mm.ToString("0.###")+
                    "；L2="+p.L2Mm.ToString("0.###")+"；a="+p.LoadArmMm.ToString("0.###")+
                    " mm；允许垂直荷载 "+p.VerticalLoadKn.ToString("0.###")+" kN。":
                    "L1="+p.L1Mm.ToString("0.###")+" mm（直接采用悬臂辅助线长）。";
            }
            catch(Exception ex){DimensionsText.Text=ex.Message;}
        }
        private void Type_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(!ready)return;
            revision++;
            if(locating)BracketLocateTool.End();
            if(ClearPreview())Status("类型已切换，请按当前类型重新点取辅助线。",false);
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;UpdateReadings();
            if(line==null)return;
            dirty=true;ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,true);
            PreviewText.Text="参数已变更，请更新预览后确定生成。";
        }
        private void Regenerate()
        {
            if(line==null){Status("请先点取水平辅助线。",true);return;}
            dirty=true;ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,true);
            try
            {
                var f=Frame();var plan=N1CantileverCalculator.Calculate(Parameters(),f.LengthMm);
                preview.Show(plan,f);dirty=false;ConfirmButton.IsEnabled=true;PreviewUpdateHint.Set(UpdateButton,false);
                PreviewText.Text="编号："+plan.Number+"\n"+plan.Specification;UpdateReadings();
                Status("N1 单悬臂架预览已生成，确定后写入清单。",false);
            }
            catch(Exception ex){PreviewText.Text="预览未更新："+ex.Message;Status(ex.Message,true);}
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            int ticket=++revision;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||!locating||ticket!=revision)return;
                try
                {
                    // Keep the previous preview until the replacement has been created successfully.
                    var next=PipeClampReader.Read(located.ModelRef,located.ElementId,located.ClickX,located.ClickY,located.ClickZ);
                    if(next.IsPipe||!next.IsAuxiliaryLine)throw new InvalidOperationException("请选择普通直线辅助线，不支持管道或复杂路径。");
                    N1CantileverCalculator.Frame(next.StartX,next.StartY,next.StartZ,next.EndX,next.EndY,next.EndZ,ReverseCheck.IsChecked==true);
                    line=next;Regenerate();
                }
                catch(Exception ex){Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try{BracketLocateTool.Begin(TypeCombo.SelectedIndex==0?"请选择悬臂辅助线 L1，左键生成 N1 预览；右键退出。":"请选择设备中心至立管中心的水平辅助线 L，左键生成 N1 预览；右键退出。");locating=true;}
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void OnEnded(){locating=false;revision++;ClearPreview();}
        private bool ClearPreview()
        {
            ConfirmButton.IsEnabled=false;
            try
            {
                preview.Cancel();line=null;dirty=false;PreviewUpdateHint.Set(UpdateButton,false);
                PreviewText.Text="已取消未确认预览。";UpdateReadings();return true;
            }
            catch(Exception ex){Status("清理失败："+ex.Message,true);return false;}
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {if(locating)BracketLocateTool.End();else{revision++;ClearPreview();}}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {revision++;if(locating)BracketLocateTool.End();else ClearPreview();}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty||!ConfirmButton.IsEnabled){Status("请先成功更新预览。",true);return;}
            try
            {
                revision++;string writeElapsed=WriteDuration.Measure(preview.Confirm);line=null;dirty=false;ConfirmButton.IsEnabled=false;
                PreviewUpdateHint.Set(UpdateButton,false);PageLastInput.Save(this,PageId,fields);UpdateReadings();
                PreviewText.Text="N1 已确认生成并写入清单，辅助线保留。";PreviewText.Text += " 写入耗时 "+writeElapsed+"。";
                Status("N1 单悬臂架已生成；写入耗时 "+writeElapsed+"。",false);
            }
            catch(Exception ex){Status("确认失败："+ex.Message,true);}
        }
        private static void Status(string text,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);}
    }
}
