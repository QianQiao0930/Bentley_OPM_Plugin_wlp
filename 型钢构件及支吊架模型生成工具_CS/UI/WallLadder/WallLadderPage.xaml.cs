using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
namespace SteelSectionProbe
{
    internal partial class WallLadderPage : UserControl,IWorkspacePage
    {
        private readonly WallLadderPreviewSession preview=new WallLadderPreviewSession();
        private readonly string[] fields={"WidthText","StandoffText","FirstRungText","BracketSpacingText","HeadingText","CageCheck"};
        private WallLadderSelection selection;
        private bool ready,active;
        private int revision;
        private string elapsed;
        public string PageId {get{return "wall-ladder";}}
        public string PageTitle {get{return "墙面爬梯";}}
        public string PageSubtitle {get{return "竖直线定位、圆钢横担及真实圆弧护笼";}}
        public FrameworkElement View {get{return this;}}
        internal WallLadderPage(){InitializeComponent();PageLastInput.Restore(this,PageId,fields);ready=true;UpdateSpecification();}
        public void OnActivated(){if(active)return;active=true;WallLadderLocateTool.Picked+=OnPicked;WallLadderLocateTool.Ended+=OnEnded;}
        public void OnDeactivated()
        {
            active=false;revision++;WallLadderLocateTool.Picked-=OnPicked;WallLadderLocateTool.Ended-=OnEnded;
            PageLastInput.Save(this,PageId,fields);WallLadderLocateTool.End();ClearPreview();
        }
        public void OnWorkspaceClosing(){OnDeactivated();}
        private static double Number(TextBox input,string name)
        {
            double v;if(!double.TryParse(input.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out v)&&!double.TryParse(input.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out v))
                throw new InvalidOperationException(name+"必须是数字。");return v;
        }
        private WallLadderParameters Parameters()
        {
            return WallLadderCalculator.Snapshot(new WallLadderParameters { WidthMm=Number(WidthText,"梯宽"),StandoffMm=Number(StandoffText,"距墙"),FirstRungMm=Number(FirstRungText,"最低横担离地"),
                BracketSpacingMm=Number(BracketSpacingText,"支架间距"),HeadingDegrees=Number(HeadingText,"出梯方向角"),CageEnabled=CageCheck.IsChecked==true });
        }
        private WallLadderPlan Plan(){if(selection==null)throw new InvalidOperationException("请先选择竖直辅助线。");return WallLadderCalculator.Calculate(selection.HeightMm,Parameters());}
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;preview.Invalidate();ConfirmButton.IsEnabled=false;UpdateSpecification();PageLastInput.Save(this,PageId,fields);
            if(selection!=null||preview.HasPreview){PreviewUpdateHint.Set(UpdateButton,true);PreviewText.Text="参数已变化，请更新预览。";}
        }
        private void UpdateSpecification()
        {
            try
            {
                Parameters();if(selection==null){SpecificationText.Text="选择竖直线后显示立柱选型、横担与护笼布置。";return;}
                var plan=Plan();HeightText.Text=plan.HeightMm.ToString("0.#",CultureInfo.CurrentCulture)+" mm";
                SpecificationText.Text=string.Format(CultureInfo.CurrentCulture,"立柱75×{0:0}；横担{1}根，长{2:0.#} mm。\n支架{3}处；护笼{4}环；平台以上延长1200 mm。",plan.StileThicknessMm,plan.RungLevels.Length,plan.RungLengthMm,plan.BracketLevels.Length,plan.HoopLevels.Length);
            }catch(Exception ex){SpecificationText.Text=ex.Message;}
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{Parameters();WallLadderLocateTool.Begin();Status("请选择代表墙面与爬梯中心投影的竖直线。",false);}catch(Exception ex){Status(ex.Message,true);}}
        private void OnPicked(LocatedElement located)
        {
            if(!active)return;int token=++revision;preview.Invalidate();ConfirmButton.IsEnabled=false;
            try
            {
                // Read native geometry in the tool callback; only immutable millimetre coordinates enter the queue.
                var picked=WallLadderReader.Read(located);
                Dispatcher.BeginInvoke(new Action(delegate{if(!active||token!=revision)return;selection=picked;UpdateSpecification();Regenerate();}),DispatcherPriority.Background);
            }catch(Exception ex){Status(ex.Message,true);}
        }
        private void Regenerate()
        {
            if(selection==null){Status("请先选择竖直辅助线。",true);return;}
            preview.Invalidate();ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,true);Status("正在生成墙面爬梯预览…",false);
            var watch=Stopwatch.StartNew();
            try
            {
                var plan=Plan();var cells=WallLadderBuilder.Build(plan,selection.BasePointMm);preview.Show(cells);
                elapsed=WriteDuration.Format(watch.Elapsed.TotalMilliseconds);ConfirmButton.IsEnabled=true;PreviewUpdateHint.Set(UpdateButton,false);
                PreviewText.Text="预览已生成，"+cells.Length+"个模型块；用时"+elapsed+"。";UpdateSpecification();Status("墙面爬梯预览已更新。",false);
            }catch(Exception ex){PreviewText.Text=ex.Message;Status("预览失败："+ex.Message,true);}
        }
        private void OnEnded(){revision++;ClearPreview();}
        private void ClearPreview()
        {
            preview.Invalidate();ConfirmButton.IsEnabled=false;
            try{preview.Cancel();selection=null;HeightText.Text="尚未选择竖直线";PreviewUpdateHint.Set(UpdateButton,false);PreviewText.Text="尚未选择竖直辅助线。";UpdateSpecification();}
            catch(Exception ex){Status("预览清理失败："+ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e){bool was=WallLadderLocateTool.IsActive;WallLadderLocateTool.End();if(!was){revision++;ClearPreview();}}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e){revision++;ClearPreview();}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(!ConfirmButton.IsEnabled)return;
            try{preview.Confirm();revision++;selection=null;ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,false);PageLastInput.Save(this,PageId,fields);
                HeightText.Text="尚未选择竖直线";PreviewText.Text="墙面爬梯已确认生成；用时"+elapsed+"。";Status("墙面爬梯已生成。",false);UpdateSpecification();}
            catch(Exception ex){ConfirmButton.IsEnabled=false;Status(ex.Message,true);}
        }
        private static void Status(string text,bool error){if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);}
    }
}
