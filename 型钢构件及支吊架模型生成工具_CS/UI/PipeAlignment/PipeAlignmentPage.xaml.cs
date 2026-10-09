using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using PA=SteelSectionProbe.PipeAlignment;
namespace SteelSectionProbe
{
    internal partial class PipeAlignmentPage:UserControl,IWorkspacePage
    {
        private readonly PA.PipeAlignSession session=new PA.PipeAlignSession();
        private readonly DispatcherTimer timer=new DispatcherTimer { Interval=TimeSpan.FromMilliseconds(150) };
        private readonly Queue<PendingPick> pending=new Queue<PendingPick>();
        private bool active,loading=true,applying,dirty;
        private DateTime previewAfter;
        private DateTime saveAfter;
        private bool settingsDirty;
        private int generation;
        private sealed class PendingPick { internal PA.LocatedElement Element;internal PA.PipePickTool.PickPurpose Purpose;internal int Generation; }
        public string PageId { get { return "pipe-alignment"; } }
        public string PageTitle { get { return "管道标高对齐"; } }
        public string PageSubtitle { get { return "管底 / 中心 / 管顶 · 连通随动 · 锁 Z 轴立管伸缩"; } }
        public FrameworkElement View { get { return this; } }
        internal PipeAlignmentPage()
        {
            InitializeComponent();
            if(session.Scope==PA.MoveScope.SelectedOnly){session.Scope=PA.MoveScope.ConnectedGroup;session.Options.DefaultMoveScope=session.Scope;settingsDirty=true;saveAfter=DateTime.UtcNow;}
            BottomRadio.IsChecked=session.Mode==PA.AlignmentMode.Bottom;CenterRadio.IsChecked=session.Mode==PA.AlignmentMode.Center;TopRadio.IsChecked=session.Mode==PA.AlignmentMode.Top;
            PipeSurface.IsChecked=session.SurfaceMode==PA.SurfaceMode.Pipe;InsulationSurface.IsChecked=session.SurfaceMode==PA.SurfaceMode.Insulation;
            SingleScope.IsChecked=session.Scope==PA.MoveScope.SelectedOnly;GroupScope.IsChecked=session.Scope==PA.MoveScope.ConnectedGroup;ZScope.IsChecked=session.Scope==PA.MoveScope.ZStretch;
            ToleranceText.Text=session.Options.HorizontalToleranceMm.ToString("F3",CultureInfo.InvariantCulture);
            timer.Tick+=delegate{if(active&&settingsDirty&&DateTime.UtcNow>=saveAfter)SaveSettings();ProcessPending();if(active&&dirty&&!applying&&DateTime.UtcNow>=previewAfter){dirty=false;BuildAndPreview();}};
            loading=false;RefreshView();
        }
        public void OnActivated()
        {
            if(active)return;active=true;generation++;timer.Start();TransactionManager.OnUndoRedoFinished+=UndoFinished;
            Status("选择基准和目标管 → 自动预览 → 应用",false);
            int token=generation;Dispatcher.BeginInvoke(new Action(delegate{
                if(!active||token!=generation)return;session.ReloadPipes(new List<string>());BuildAndPreview();}),DispatcherPriority.Background);
        }
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            if(!active)return;if(settingsDirty)SaveSettings();active=false;generation++;timer.Stop();TransactionManager.OnUndoRedoFinished-=UndoFinished;
            lock(pending)pending.Clear();dirty=false;session.Close();session.Plan=null;RefreshView();
        }
        private void Status(string text,bool error)
        {
            StatusText.Text=text;StatusText.Foreground=(Brush)FindResource(error?"ErrorBrush":"StatusBrush");
            if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);
        }
        private bool ReadParameters()
        {
            double value;if(!double.TryParse(ToleranceText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)
                &&!double.TryParse(ToleranceText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out value)){
                Status("水平容差必须是数字。",true);return false;}
            if(double.IsNaN(value)||double.IsInfinity(value)||value<0||value>1000){Status("水平容差应在 0～1000 mm。",true);return false;}
            session.Options.HorizontalToleranceMm=value;
            session.Mode=TopRadio.IsChecked==true?PA.AlignmentMode.Top:CenterRadio.IsChecked==true?PA.AlignmentMode.Center:PA.AlignmentMode.Bottom;
            session.SurfaceMode=InsulationSurface.IsChecked==true?PA.SurfaceMode.Insulation:PA.SurfaceMode.Pipe;
            session.Scope=ZScope.IsChecked==true?PA.MoveScope.ZStretch:PA.MoveScope.ConnectedGroup;
            PickTargetButton.Content=session.Scope==PA.MoveScope.ZStretch?"选择起点水平管（最多15根）":"选择目标管";return true;
        }
        private void Parameters_Changed(object sender,RoutedEventArgs e)
        {
            if(loading)return;settingsDirty=true;saveAfter=DateTime.UtcNow.AddMilliseconds(500);Invalidate();
        }
        private void Invalidate()
        {
            session.Plan=null;
            try{session.Preview.Clear();}catch(Exception ex){Status("预览清理失败："+ex.Message,true);}
            dirty=true;previewAfter=DateTime.UtcNow.AddMilliseconds(350);ReadParameters();RefreshView();
        }
        private void Reference_Click(object sender,RoutedEventArgs e){BeginPick(PA.PipePickTool.PickPurpose.Reference);}
        private void Target_Click(object sender,RoutedEventArgs e)
        {if(session.ReferencePipe==null){Status("请先选择基准。",true);return;}BeginPick(PA.PipePickTool.PickPurpose.Target);}
        private void BeginPick(PA.PipePickTool.PickPurpose purpose)
        {
            try{
                if(PA.PipePickTool.IsActive&&PA.PipePickTool.ActivePurpose!=purpose)PA.PipePickTool.End();
                PA.PipePickTool.Begin(purpose,delegate(PA.LocatedElement element){QueuePick(element,purpose);},delegate{if(active)Status("点取已结束。",false);});
                Status(purpose==PA.PipePickTool.PickPurpose.Reference?"请选择基准水平直管或水平直线（基准不移动）。":"请选择目标水平直管，右键结束。",false);
            }catch(Exception ex){Status(ex.Message,true);}
        }
        private void QueuePick(PA.LocatedElement element,PA.PipePickTool.PickPurpose purpose)
        {
            if(!active||element==null)return;
            lock(pending)pending.Enqueue(new PendingPick{Element=element,Purpose=purpose,Generation=generation});
            Dispatcher.BeginInvoke(new Action(ProcessPending),DispatcherPriority.Background); // EC读取必须离开SDK点取回调。
        }
        private void ProcessPending()
        {
            if(!active||applying)return;
            while(true){PendingPick pick;lock(pending){if(pending.Count==0)break;pick=pending.Dequeue();}
                if(pick.Generation!=generation)continue;
                try{var pipe=pick.Purpose==PA.PipePickTool.PickPurpose.Reference?session.ReadReference(pick.Element):session.ReadPipe(pick.Element,false,true);
                    if(pick.Purpose==PA.PipePickTool.PickPurpose.Reference){
                        session.SetReferencePipe(pipe);
                    }else{if(!session.AddTargetPipe(pipe))continue;
                        }
                    Invalidate();Status("选择已更新，正在自动计算。",false);
                }catch(Exception ex){Status("读取对象失败："+ex.Message,true);}}
        }
        private void Selection_Click(object sender,RoutedEventArgs e)
        {
            try{uint count=SelectionSetManager.NumSelected();if(count==0){Status("请先在模型中建立选择集。",true);return;}
                if(count>15){Status("一次最多选择 15 根起点/目标管。",true);return;}
                for(uint i=0;i<count;i++){Element element=null;DgnModelRef model=null;
                    if(SelectionSetManager.GetElement(i,ref element,ref model)!=StatusInt.Success||element==null)continue;
                    QueuePick(new PA.LocatedElement{ModelRef=model??element.DgnModelRef,ElementId=(ulong)element.ElementId},PA.PipePickTool.PickPurpose.Target);}
            }catch(Exception ex){Status(ex.Message,true);}
        }
        private void RemoveRow_Click(object sender,RoutedEventArgs e)
        {
            var button=sender as Button;var row=button==null?null:button.DataContext as PipeRow;
            if(row==null||!session.TargetPipes.Any(pipe=>PA.PipeIdentity.Key(pipe)==row.Key))return;
            session.RemoveTargetPipe(row.Key);e.Handled=true;
            Invalidate();
        }
        private void ClearTargets_Click(object sender,RoutedEventArgs e){session.ClearTargets();Invalidate();}
        private bool BuildAndPreview()
        {
            if(!active||!ReadParameters())return false;
            if(session.ReferencePipe==null||session.TargetPipes.Count==0){RefreshView();return false;}
            try{
                session.Log.Detail("自动预览开始：起点="+session.TargetPipes.Count);session.Log.Flush();
                session.BuildPlan();RefreshView();
                session.Log.Detail("批量规划完成，开始绘制预览。");session.Log.Flush();
                session.Preview.Rebuild(session.Plan,session.Units,ShowCurrent.IsChecked==true,ShowTarget.IsChecked==true);
                Status("计算完成："+SummaryText.Text,false);
                session.Log.Detail("自动预览完成。");session.Log.Flush();return true;}
            catch(Exception ex){session.Plan=null;RefreshView();Status(ex.Message,true);session.Log.Detail("自动预览失败："+ex);session.Log.Flush();return false;}
        }
        private void Preview_Click(object sender,RoutedEventArgs e){dirty=false;BuildAndPreview();}
        private void Preview_Changed(object sender,RoutedEventArgs e){if(!loading&&active)BuildAndPreview();}
        private void ClearPreview_Click(object sender,RoutedEventArgs e){dirty=false;
            try{session.Preview.Clear();Status("已清除临时预览。",false);}catch(Exception ex){Status(ex.Message,true);}}
        private void Apply_Click(object sender,RoutedEventArgs e)
        {
            if(applying)return;PA.PipePickTool.End();ProcessPending();dirty=false;
            try{session.ReloadPipes(new List<string>());if(!BuildAndPreview())return;
                if(session.Plan.ReadyCount==0){Status("没有需要移动的目标管。",false);return;}
                applying=true;ApplyButton.IsEnabled=false;
                var result=session.Apply();session.Preview.Clear();session.ReloadPipes(new List<string>());BuildAndPreview();
                string summary=string.Format("移动 {0}，已对齐 {1}，跳过 {2}，失败 {3}。",result.MovedCount,result.AlreadyAlignedCount,result.SkippedCount,result.FailedCount);
                var reasons=result.Items.Where(x=>x.Outcome==PA.MoveOutcome.Skipped||x.Outcome==PA.MoveOutcome.Failed).Select(x=>x.Describe()).ToList();
                if(!string.IsNullOrEmpty(result.FailureMessage))reasons.Add(result.FailureMessage);
                bool failed=result.FailedCount>0||!string.IsNullOrEmpty(result.FailureMessage);
                // 完整逐级过程已由 session.Apply 写入日志，弹窗不重复整段诊断。
                if(failed){summary+="\n模型修改未通过复核。"+(result.RolledBack?"本批已回滚。":"请检查模型是否存在未回滚修改。")
                    +"\n详细过程：%LOCALAPPDATA%\\PipeAlign\\PipeAlign_debug_log.txt";
                    MessageBox.Show(summary,"管道对齐执行失败",MessageBoxButton.OK,MessageBoxImage.Error);}
                else if(reasons.Count>0)summary+="\n"+string.Join("\n",reasons.Take(3));
                Status(summary,failed);
            }catch(Exception ex){Status(ex.Message,true);MessageBox.Show(ex.Message,"管道对齐执行失败",MessageBoxButton.OK,MessageBoxImage.Error);}
            finally{applying=false;ApplyButton.IsEnabled=true;}
        }
        private void UndoFinished(object sender,OnUndoRedoFinishedEventArgs e)
        {
            if(!active||applying)return;int token=generation;Dispatcher.BeginInvoke(new Action(delegate{
                if(!active||token!=generation||applying)return;session.ReloadPipes(new List<string>());BuildAndPreview();}),DispatcherPriority.Background);
        }
        private void Reset_Click(object sender,RoutedEventArgs e){
            try{PA.PipePickTool.End();lock(pending)pending.Clear();generation++;dirty=false;session.Reset();RefreshView();Status("已重置选择与预览。",false);}
            catch(Exception ex){Status(ex.Message,true);}}
        private void SaveSettings()
        {
            settingsDirty=false;
            if(!ReadParameters())return;
            try{
                session.Options.DefaultMoveScope=session.Scope;
                session.Options.DefaultAlignmentMode=session.Mode;
                session.Options.DefaultSurfaceMode=session.SurfaceMode;
                session.SaveOptions();
            }catch(Exception ex){Status("自动记住设置失败："+ex.Message,true);}
        }
        private void Debug_Click(object sender,RoutedEventArgs e)
        {
            try{bool all=(sender as MenuItem)!=null&&(string)((MenuItem)sender).Tag=="all";
                string report=PA.PipeDebugReport.Build(session,all);session.Log.Flush();
                MessageBox.Show(report,"管道对齐只读调试",MessageBoxButton.OK,MessageBoxImage.Information);
            }catch(Exception ex){Status(ex.Message,true);}
        }
        private void RefreshView()
        {
            CountText.Text="已选 "+session.TargetPipes.Count+" / 15 根";
            var pipe=session.ReferencePipe;ReferenceText.Text=pipe==null?"尚未选择基准":pipe.IsReferenceLine?pipe.DisplayName+" · 只读基准\n直线标高 "+pipe.Axis.CenterElevationMm.ToString("F2",CultureInfo.InvariantCulture)+" mm":pipe.DisplayName+" · "+pipe.ClassName+"\n外径 "+pipe.OutsideDiameterMm+" mm · 保温 "+pipe.InsulationThicknessMm+" mm\n"+(pipe.ReadWarning??"读取正常");
            var plan=session.Plan;var rows=new List<PipeRow>();
            if(plan!=null){foreach(var item in plan.Items)rows.Add(new PipeRow(item));
                SummaryText.Text=string.Format(CultureInfo.InvariantCulture,"基准标高 {0:F2} mm · 将移动 {1}，已对齐 {2}，跳过 {3}",plan.ReferenceElevationMm,plan.ReadyCount,plan.AlreadyAlignedCount,plan.SkippedCount);
                ReadoutText.Text="基准轴线标高 "+plan.ReferencePipe.Axis.CenterElevationMm.ToString("F2",CultureInfo.InvariantCulture)+" mm\n"
                    +PA.AlignmentModes.Chinese(plan.Mode)+" / "+PA.SurfaceModes.Chinese(plan.SurfaceMode)+"\n"+session.DescribeTolerance()+"\n"+session.LastGroupNote;
            }else{foreach(var target in session.TargetPipes)rows.Add(new PipeRow(target));SummaryText.Text="选择完成后自动计算。";ReadoutText.Text="";}
            foreach(var row in rows)row.RemoveVisibility=session.TargetPipes.Any(target=>PA.PipeIdentity.Key(target)==row.Key)?Visibility.Visible:Visibility.Collapsed;
            PipeList.ItemsSource=rows;
        }
        private sealed class PipeRow
        {
            public Visibility RemoveVisibility { get; set; }
            public string Key { get; private set; }public string Name { get; private set; }public string Connection { get; private set; }
            public string Current { get; private set; }public string Target { get; private set; }public string Delta { get; private set; }
            public string Status { get; private set; }public string Details { get; private set; }public Brush StatusBrush { get; private set; }
            internal PipeRow(PA.PipeInfo pipe){Key=PA.PipeIdentity.Key(pipe);Name=pipe.DisplayName;Connection=pipe.ClassName;Status="等待计算";StatusBrush=Brushes.Gray;Details=Name;}
            internal PipeRow(PA.AlignmentPlanItem item):this(item.Pipe)
            {
                Name=(item.AddedByGroup?"＋ ":"")+Name;Connection=item.Pipe.ClassName+" · "+(item.Pipe.Topology==null?"连接未知":item.Pipe.Topology.Summary());
                Current="当前 "+item.CurrentElevationMm.ToString("F2",CultureInfo.InvariantCulture);
                Target="目标 "+item.ReferenceElevationMm.ToString("F2",CultureInfo.InvariantCulture);
                Delta="ΔZ "+(item.Status==PA.PlanItemStatus.Skipped?"—":item.DeltaZmm.ToString("+0.00;-0.00;0.00",CultureInfo.InvariantCulture));
                Status=item.Status==PA.PlanItemStatus.Skipped?"跳过："+item.SkipReason:item.Status==PA.PlanItemStatus.AlreadyAligned?"已对齐，无需移动":item.IsStretch?
                    string.Format(CultureInfo.InvariantCulture,"立管伸缩 {0:F2} → {1:F2} mm，另一端固定",item.Pipe.Axis.LengthMm,item.TargetAxis.LengthMm):"将移动";
                Status="外径 "+item.OutsideDiameterMm.ToString("F1",CultureInfo.InvariantCulture)+" mm · "+Status;
                StatusBrush=new SolidColorBrush(item.Status==PA.PlanItemStatus.AlreadyAligned?Color.FromRgb(61,122,55):Color.FromRgb(154,111,20));
                Details=Name+"\n"+Connection+"\n"+Current+" → "+Target+" · "+Delta+" mm\n"+Status;
            }
        }
    }
}
