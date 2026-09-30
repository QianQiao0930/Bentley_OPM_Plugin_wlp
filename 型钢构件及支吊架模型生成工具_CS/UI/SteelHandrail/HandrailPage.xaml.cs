using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
namespace SteelSectionProbe
{
    internal partial class HandrailPage:UserControl,IWorkspacePage
    {
        private readonly HandrailPreviewSession preview=new HandrailPreviewSession();
        private readonly DispatcherTimer regenerate=new DispatcherTimer{Interval=TimeSpan.FromMilliseconds(150)};
        private List<HandrailPoint> vertices;
        private bool ready,active,locating,dirty;
        public string PageId {get{return HandrailCatalog.PageId;}}
        public string PageTitle {get{return HandrailCatalog.SupportType;}}
        public string PageSubtitle {get{return "沿路径建模 · 水平 / 坡段围栏";}}
        public FrameworkElement View {get{return this;}}
        internal HandrailPage()
        {
            InitializeComponent();ConnectionCombo.ItemsSource=HandrailCatalog.ConnectionLabels;ConnectionCombo.SelectedIndex=1;
            SideCombo.ItemsSource=new[]{"路径左侧","路径右侧"};SideCombo.SelectedIndex=0;
            ClosureCombo.ItemsSource=HandrailCatalog.ClosureLabels;ClosureCombo.SelectedIndex=0;
            PageLastInput.Restore(this,PageId,"ConnectionCombo","SideCombo","ClosureCombo","OffsetText","ReverseCheck");
            regenerate.Tick+=delegate{regenerate.Stop();if(active&&vertices!=null)Regenerate(vertices);};
            ready=true;UpdateConnection();
        }
        public void OnActivated(){if(active)return;active=true;HandrailLocateTool.Picked+=OnPicked;HandrailLocateTool.Ended+=OnEnded;}
        public void OnDeactivated(){Close();}
        public void OnWorkspaceClosing(){Close();}
        private void Close()
        {
            PageLastInput.Save(this,PageId,"ConnectionCombo","SideCombo","ClosureCombo","OffsetText","ReverseCheck");
            active=false;regenerate.Stop();HandrailLocateTool.Picked-=OnPicked;HandrailLocateTool.Ended-=OnEnded;
            if(locating)HandrailLocateTool.End();locating=false;
            ClearPreview();
        }
        private HandrailConnection Connection {get{return (HandrailConnection)(Math.Max(0,ConnectionCombo.SelectedIndex)+1);}}
        private void UpdateConnection()
        {
            OffsetPanel.Visibility=Connection==HandrailConnection.Type2?Visibility.Visible:Visibility.Collapsed;
            ConnectionText.Text=Connection==HandrailConnection.Type1?
                "146×75×10 侧板；圆管向 70×16.1 椭圆压扁端过渡，过渡长 38.5 mm（沿用原版暂定尺寸和空心近似）。":
                Connection==HandrailConnection.Type2?"R76 下弯至安装面下方 76 mm，管端设置 146×75×10 侧板。":
                Connection==HandrailConnection.Type3?"145×75×10 水平底板；坡段底板也保持水平，立柱从板顶向上。":
                "类型 4 沿用原版预留形式，生成围栏本体，不生成底部连接节点。";
        }
        private HandrailParameters Parameters()
        {
            double offset=120;
            if(Connection==HandrailConnection.Type2&&
                !double.TryParse(OffsetText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out offset)&&
                !double.TryParse(OffsetText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out offset))
                throw new InvalidOperationException("立柱中心至连接板距离必须是数字。");
            return new HandrailParameters{Connection=Connection,Side=SideCombo.SelectedIndex==1?-1:1,
                Closure=(HandrailClosure)Math.Max(0,ClosureCombo.SelectedIndex),Reverse=ReverseCheck.IsChecked==true,StructureOffsetMm=offset};
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;UpdateConnection();if(vertices==null)return;
            dirty=true;ConfirmButton.IsEnabled=false;PreviewText.Text="参数已变更，正在更新预览。";
            regenerate.Stop();regenerate.Start();
        }
        private void Regenerate(List<HandrailPoint> next)
        {
            regenerate.Stop();vertices=next;
            try{
                var plan=HandrailCalculator.Calculate(Parameters(),next);preview.Show(plan);
                vertices=next;dirty=false;ConfirmButton.IsEnabled=true;
                PreviewText.Text="路径长 "+plan.LengthMm.ToString("0.#")+" mm；"+plan.Stations.Count+" 根立柱、"+
                    plan.Stations.Count*2+" 个连接球；"+plan.Corners.Count(x=>!x.GradeBreak)+" 个圆角、"+
                    plan.Corners.Count(x=>x.GradeBreak)+" 个变坡点。\n预览可取消；确定后写入钢材清单，辅助线保留。";
                Status("围栏预览已更新。",false);
            }catch(Exception ex){dirty=true;ConfirmButton.IsEnabled=false;PreviewText.Text="预览未更新："+ex.Message;Status("围栏预览失败，请查看面板。",true);}
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            Dispatcher.BeginInvoke(new Action(delegate{
                if(!active||!locating)return;
                try{var next=HandrailPathReader.Read(located.ElementId);Regenerate(next);}
                catch(Exception ex){PreviewText.Text="点取失败："+ex.Message;Status("围栏点取失败，请查看面板。",true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded(){locating=false;regenerate.Stop();ClearPreview();}
        private void ClearPreview()
        {
            try{preview.Cancel();vertices=null;dirty=false;ConfirmButton.IsEnabled=false;PreviewText.Text="已取消未确认预览。";}
            catch(Exception ex){ConfirmButton.IsEnabled=false;PreviewText.Text=ex.Message;Status("围栏预览清理失败。",true);}
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try{if(HandrailLocateTool.IsActive&&locating){Status("可直接点取下一条辅助线，无需再点开始点取。",false);return;}
                locating=true;HandrailLocateTool.Begin();Status("请选择活动模型中的围栏辅助线。",false);}
            catch(Exception ex){locating=false;Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e){if(locating)HandrailLocateTool.End();else ClearPreview();}
        private void Update_Click(object sender,RoutedEventArgs e){if(vertices!=null)Regenerate(vertices);else Status("请先点取围栏辅助线。",false);}
        private void Cancel_Click(object sender,RoutedEventArgs e){regenerate.Stop();ClearPreview();}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(dirty){Status("请先成功更新预览。",true);return;}
            try{regenerate.Stop();preview.Confirm();vertices=null;ConfirmButton.IsEnabled=false;
                PreviewText.Text="围栏已确认，并写入钢材清单；可继续点取下一条辅助线。";Status("普通钢结构围栏已生成。",false);}
            catch(Exception ex){Status("确认失败："+ex.Message,true);}
        }
        private void Export_Click(object sender,RoutedEventArgs e)
        {
            try{
                var snapshot=SupportStatisticsReader.Read();
                var report=SupportStatisticsCalculator.Summarize(snapshot.Records.Where(x=>x.SupportType==HandrailCatalog.SupportType));
                if(report.AssemblyCount==0){Status("当前 DGN 文件没有已确认的 C# 围栏清单。",false);return;}
                var dialog=new Microsoft.Win32.SaveFileDialog{Filter="JSON 清单 (*.json)|*.json",FileName="普通钢结构围栏_bom.json",DefaultExt=".json"};
                if(dialog.ShowDialog()!=true)return;SupportStatisticsExporter.WriteJson(dialog.FileName,report);
                Status("围栏 JSON 清单已导出。",false);
            }catch(Exception ex){Status("导出失败："+ex.Message,true);}
        }
        private static void Status(string message,bool error){if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error);}
    }
}
