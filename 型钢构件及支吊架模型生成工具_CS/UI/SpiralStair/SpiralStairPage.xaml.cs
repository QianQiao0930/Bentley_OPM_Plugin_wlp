using System;
using System.Diagnostics;
using System.Globalization;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal partial class SpiralStairPage:UserControl,IWorkspacePage
    {
        private readonly SpiralStairPreviewSession preview=new SpiralStairPreviewSession();
        private readonly string[] fields={"DiameterText","WidthText","StartText","EndText","IntervalText","GapText","RiserText","DepthText","LandingText","TopText","AngleText","DirectionCombo","InnerCheck","SpacingText","ConnectionCombo","OffsetText"};
        private bool ready,active,busy,updating,optionalInnerRailing;
        private int revision;
        private double lastBuildSeconds;
        private string lastLogPath;
        private DPoint3d? origin;
        public string PageId {get{return "tank-spiral-stair";}}
        public string PageTitle {get{return "罐体盘梯生成";}}
        public string PageSubtitle {get{return "梯梁、踏步、平台及栏杆";}}
        public FrameworkElement View {get{return this;}}
        internal SpiralStairPage()
        {
            InitializeComponent();DirectionCombo.ItemsSource=new[]{"正向（逆时针上升）","反向（顺时针上升）"};DirectionCombo.SelectedIndex=0;
            ConnectionCombo.ItemsSource=HandrailCatalog.ConnectionLabels;ConnectionCombo.SelectedIndex=1;
            PageLastInput.Restore(this,PageId,fields);optionalInnerRailing=InnerCheck.IsChecked==true;ready=true;UpdateSpecification();
        }
        public void OnActivated(){if(active)return;active=true;SpiralStairPlacementTool.Picked+=OnPicked;SpiralStairPlacementTool.Ended+=OnEnded;}
        public void OnDeactivated()
        {
            SaveParameters();active=false;revision++;
            SpiralStairPlacementTool.Picked-=OnPicked;SpiralStairPlacementTool.Ended-=OnEnded;
            SpiralStairPlacementTool.End();ClearPreview();
        }
        public void OnWorkspaceClosing(){OnDeactivated();}
        private static double Number(TextBox box,string label)
        {
            double v;if(!double.TryParse(box.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out v)&&!double.TryParse(box.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out v))
                throw new InvalidOperationException(label+"必须是数字。");return v;
        }
        private SpiralStairParameters Parameters()
        {
            return new SpiralStairParameters{TankDiameterMm=Number(DiameterText,"罐体外径"),ClearWidthMm=Number(WidthText,"盘梯宽度"),
                StartZmm=Number(StartText,"起点标高"),EndZmm=Number(EndText,"终点标高"),LandingIntervalMm=Number(IntervalText,"平台高度间隔"),
                WallGapMm=Number(GapText,"罐壁间隙"),RiserMm=Number(RiserText,"踏步高度"),TreadDepthMm=Number(DepthText,"踏面深度"),
                LandingLengthMm=Number(LandingText,"休息平台长度"),TopLengthMm=Number(TopText,"顶部平台长度"),StartAngleDegrees=Number(AngleText,"起始角"),
                Direction=DirectionCombo.SelectedIndex==1?-1:1,InnerRailing=InnerCheck.IsChecked==true,MaxPostSpacingMm=Number(SpacingText,"立柱最大间距"),
                Connection=(HandrailConnection)(Math.Max(0,ConnectionCombo.SelectedIndex)+1),StructureOffsetMm=Number(OffsetText,"连接板距离")};
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {if(!ready||updating)return;if(ReferenceEquals(sender,InnerCheck))optionalInnerRailing=InnerCheck.IsChecked==true;ConfirmButton.IsEnabled=false;revision++;UpdateSpecification();}
        private void UpdateSpecification()
        {
            updating=true;
            try{
                double gap;bool forced=double.TryParse(GapText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out gap)&&gap>100;
                InnerCheck.IsEnabled=!forced;
                // 强制状态不覆盖用户的可选设置，降低间隙后恢复原选择。
                InnerCheck.IsChecked=forced||optionalInnerRailing;
                InnerHint.Text=forced?"罐壁间隙大于100mm，内侧栏杆将强制生成。":"罐壁间隙不大于100mm，内侧栏杆可选。";
                OffsetPanel.Visibility=ConnectionCombo.SelectedIndex==1?Visibility.Visible:Visibility.Collapsed;
                var plan=SpiralStairCalculator.Calculate(Parameters());
                LayoutText.Text=string.Format(CultureInfo.CurrentCulture,"{0}个梯段、{1}级踏步、{2}个休息平台及1个顶部平台；倾角 {3:0.0}°。\n内梁半径 {4:0.#}mm；栏杆路径在梁顶开口外缘。",plan.FlightCounts.Count,plan.TreadCount,plan.RestPlatformCount,plan.SlopeDegrees,plan.InnerRadiusMm);
                if(plan.Parameters.WallGapMm==0)LayoutText.Text+="\n平台采用水平直线连接，罐壁附近的实际净空需复核。";
            }catch(Exception ex){LayoutText.Text=ex.Message;}
            finally{updating=false;}
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{if(busy)return;SpiralStairCalculator.Calculate(Parameters());SpiralStairPlacementTool.Begin();Status("请点取罐体中心基点。",false);}catch(Exception ex){Status(ex.Message,true);}}
        private void OnPicked(DPoint3d point)
        {
            if(!active||busy)return;
            Dispatcher.BeginInvoke(new Action(async delegate{if(!active||busy)return;origin=point;await Generate();}),DispatcherPriority.Background);
        }
        private void SetBusy(bool value)
        {busy=value;ParametersPanel.IsEnabled=!value;PickButton.IsEnabled=!value;UpdateButton.IsEnabled=!value;}
        private void SaveParameters()
        {
            bool wasUpdating=updating;var displayed=InnerCheck.IsChecked;updating=true;
            try{InnerCheck.IsChecked=optionalInnerRailing;PageLastInput.Save(this,PageId,fields);}
            finally{InnerCheck.IsChecked=displayed;updating=wasUpdating;}
        }
        private async Task Generate()
        {
            if(!active||busy)return;if(!origin.HasValue){Status("请先点取罐体中心。",true);return;}
            int ticket=++revision;var watch=Stopwatch.StartNew();string stage="计算布局";int complete=0,total=1;
            var log=new SpiralStairLog();lastLogPath=log.FilePath;
            LogButton.IsEnabled=System.IO.File.Exists(lastLogPath);
            log.Write(stage,string.Format(CultureInfo.InvariantCulture,"点取中心UOR：({0:R},{1:R},{2:R})；日志：{3}",origin.Value.X,origin.Value.Y,origin.Value.Z,lastLogPath));
            SetBusy(true);ConfirmButton.IsEnabled=false;
            double lastReport=-1;
            Action report=()=>{
                if(lastReport>=0&&watch.Elapsed.TotalSeconds-lastReport<0.5)return;
                lastReport=watch.Elapsed.TotalSeconds;
                if(MainWindow.Current!=null)MainWindow.Current.SetBuildProgress((int)(complete*100.0/total),stage,(int)watch.Elapsed.TotalSeconds);
            };
            var timer=new DispatcherTimer{Interval=TimeSpan.FromMilliseconds(500)};timer.Tick+=delegate{if(active&&ticket==revision)report();};timer.Start();
            try{
                report();await Dispatcher.InvokeAsync(delegate{},DispatcherPriority.Background);
                if(!active||ticket!=revision)throw new OperationCanceledException();
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null||!model.Is3d)throw new InvalidOperationException("请激活三维模型。");
                var modelId=model.GetModelId();var fileName=Session.Instance.GetActiveDgnFile().GetFileName();
                var parameters=Parameters();log.Parameters(parameters);
                log.Write("模型","文件："+fileName+"；模型："+modelId+"；UOR/m："+model.GetModelInfo().UorPerMeter);
                var plan=SpiralStairCalculator.Calculate(parameters);var result=new SpiralStairBuildResult();
                stage="准备梯梁与栏杆";report();
                var steps=SpiralStairBuilder.Steps(plan,origin.Value,result);total=steps.Count+1;
                foreach(var step in steps)
                {
                    stage=step.Name;report();
                    log.Write(stage,"开始；工作单元 "+(complete+1)+"/"+total+"；用时 "+watch.Elapsed.TotalSeconds.ToString("0.000")+"s");
                    await Dispatcher.InvokeAsync(delegate{
                        if(!active||ticket!=revision)throw new OperationCanceledException();
                        var current=Session.Instance.GetActiveDgnModel();
                        if(current==null||!modelId.Equals(current.GetModelId())||!fileName.Equals(Session.Instance.GetActiveDgnFile().GetFileName()))throw new InvalidOperationException("活动模型已切换，本次建模已停止。");
                        step.Run();
                    },DispatcherPriority.Background);
                    complete++;
                    log.Write(stage,"完成");
                }
                stage="写入盘梯预览";report();
                if(!active||ticket!=revision)throw new OperationCanceledException();
                preview.Show(result);complete=total;ConfirmButton.IsEnabled=true;
                log.Write(stage,"预览完成；顶层元素 "+result.Elements.Count+"；用时 "+watch.Elapsed.TotalSeconds.ToString("0.000")+"s");
                lastBuildSeconds=watch.Elapsed.TotalSeconds;SaveParameters();
                Status(string.Format(CultureInfo.CurrentCulture,"盘梯预览完成 100% · 用时 {0:0.0}s；请确定生成。",watch.Elapsed.TotalSeconds),false);
            }catch(OperationCanceledException){log.Write(stage,"取消");if(active)Status("盘梯建模已取消 · 用时 "+watch.Elapsed.TotalSeconds.ToString("0.0")+"s。",false);}
            catch(Exception ex){log.Write(stage,"失败；用时 "+watch.Elapsed.TotalSeconds.ToString("0.000")+"s；"+ex);lastLogPath=log.FilePath;if(active)Status("盘梯失败："+stage+" · "+ex.Message+"；日志："+lastLogPath,true);}
            finally{timer.Stop();watch.Stop();log.Dispose();SetBusy(false);}
        }
        private async void Update_Click(object sender,RoutedEventArgs e){await Generate();}
        private void OnEnded(){if(active){revision++;ClearPreview();}}
        private bool ClearPreview()
        {ConfirmButton.IsEnabled=false;origin=null;try{preview.Cancel();SpiralStairLog.Append(lastLogPath,"取消预览","完成");return true;}catch(Exception ex){SpiralStairLog.Append(lastLogPath,"取消预览",ex.ToString());Status(ex.Message,true);return false;}}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {revision++;SpiralStairPlacementTool.End();if(ClearPreview()&&active)Status("已取消盘梯建模及未确认预览。",false);}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(busy||!ConfirmButton.IsEnabled)return;
            try{preview.Confirm();SpiralStairLog.Append(lastLogPath,"确认生成","完成，栏杆清单已写入");origin=null;ConfirmButton.IsEnabled=false;SaveParameters();Status("罐体盘梯已生成 100% · 建模用时 "+lastBuildSeconds.ToString("0.0")+"s；栏杆已写入钢材清单，无辅助线残留。",false);}
            catch(Exception ex){SpiralStairLog.Append(lastLogPath,"确认生成",ex.ToString());Status("盘梯确认失败："+ex.Message+"；日志："+lastLogPath,true);}
        }
        private void Log_Click(object sender,RoutedEventArgs e)
        {
            try{if(!System.IO.File.Exists(lastLogPath))throw new InvalidOperationException(lastLogPath??"尚未建模，没有日志。");Process.Start(new ProcessStartInfo(lastLogPath){UseShellExecute=true});}
            catch(Exception ex){Status("打开日志失败："+ex.Message,true);}
        }
        private static void Status(string text,bool error){if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);}
    }
}
