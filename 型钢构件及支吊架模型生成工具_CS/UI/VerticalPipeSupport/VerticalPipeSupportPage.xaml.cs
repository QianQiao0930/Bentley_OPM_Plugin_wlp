using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class VerticalPipeSupportPage : UserControl,IWorkspacePage
    {
        private readonly VerticalPipeSupportPreviewSession preview=new VerticalPipeSupportPreviewSession();
        private PipeClampSelection selection;
        private bool active,locating,initializing;
        // 沿轴滑动状态：axisOffsetMm=相对点取位置的沿轴偏移（正=朝 +Z 一侧，竖管即向上）；
        // slideAnchorOffsetMm=进入滑动时刻的偏移快照（锁定时在此基础上叠加光标位移）；
        // slideFinishing 用于吞掉锁定后 End() 引发的那次 Ended（同 A1 页面的 finishing 做法）。
        private bool sliding,slideFinishing;
        private double axisOffsetMm,slideAnchorOffsetMm;
        private int slideRevision;
        private bool syncingOffset, offsetPending;
        public string PageId { get { return "vertical-pipe-support"; } }
        public string PageTitle { get { return "立管耳轴"; } }
        public string PageSubtitle { get { return "F6 单耳轴 · F7 双耳轴 · F10 小管径立管耳板"; } }
        public FrameworkElement View { get { return this; } }
        internal VerticalPipeSupportPage()
        {
            initializing=true;
            InitializeComponent();
            AxisSlideTool.Locked+=OnSlideLocked;
            AxisSlideTool.Ended+=OnSlideEnded;
            AxisSlideTool.Moved+=OnSlideMoved;
            KindCombo.ItemsSource=new[]{"F6 单耳轴","F7 双耳轴","F10 小管径立管耳板"};
            KindCombo.SelectedIndex=0;
            TrunnionPipeDn.ItemsSource=VerticalPipeSupportCatalog.TrunnionDns.Select(n=>"DN"+n).ToArray();
            TrunnionPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.TrunnionDns,100);
            EarPipeDn.ItemsSource=VerticalPipeSupportCatalog.F10Dns.Select(n=>"DN"+n).ToArray();
            EarPipeDn.SelectedIndex=2;
            EndTypeCombo.ItemsSource=new[]{"A","B","C"};EndTypeCombo.SelectedIndex=0;
            TrunnionMaterial.ItemsSource=new[]{"L","C1","C2","A1","A2","S","S1"};
            TrunnionMaterial.SelectedIndex=1;
            EarMaterial.ItemsSource=new[]{"L","C1","C2","A1","A2","S"};
            EarMaterial.SelectedIndex=1;
            EarLength.ItemsSource=new[]{"1 — 100 mm","2 — 150 mm","3 — 200 mm"};EarLength.SelectedIndex=0;
            EarHeight.ItemsSource=new[]{"A — 50 mm","B — 100 mm","C — 150 mm","D — 200 mm"};EarHeight.SelectedIndex=0;
            RefreshTrunnionChoices();
            UpdatePanels();
            initializing=false;
            PageLastInput.Restore(this,PageId,"KindCombo","TrunnionPipeDn","TrunnionDn",
                "LengthText","WallText","EndTypeCombo","TrunnionMaterial","TrunnionAngle",
                "PadCheck","PadThickness","EarPipeDn","EarLength","EarHeight",
                "EarMaterial","EarAngle","FixedCheck");
        }
        public void OnActivated()
        {
            active=true;
            PipeClampLocateTool.Picked+=OnPicked;
            PipeClampLocateTool.Ended+=OnEnded;
        }
        public void OnDeactivated() { Close(); }
        public void OnWorkspaceClosing()
        {
            AxisSlideTool.Locked-=OnSlideLocked;
            AxisSlideTool.Ended-=OnSlideEnded;
            AxisSlideTool.Moved-=OnSlideMoved;
            Close();
        }
        private void Close()
        {
            PageLastInput.Save(this,PageId,"KindCombo","TrunnionPipeDn","TrunnionDn",
                "LengthText","WallText","EndTypeCombo","TrunnionMaterial","TrunnionAngle",
                "PadCheck","PadThickness","EarPipeDn","EarLength","EarHeight",
                "EarMaterial","EarAngle","FixedCheck");
            active=false;
            slideRevision++;
            sliding=false;
            AxisSlideTool.End();
            PipeClampLocateTool.Picked-=OnPicked;
            PipeClampLocateTool.Ended-=OnEnded;
            if(locating) PipeClampLocateTool.End();
            locating=false;
            axisOffsetMm=0;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;
        }
        private VerticalPipeSupportKind Kind()
        {
            return KindCombo.SelectedIndex==1?VerticalPipeSupportKind.F7:
                KindCombo.SelectedIndex==2?VerticalPipeSupportKind.F10:VerticalPipeSupportKind.F6;
        }
        private void UpdatePanels()
        {
            bool ear=Kind()==VerticalPipeSupportKind.F10;
            TrunnionPanel.Visibility=ear?Visibility.Collapsed:Visibility.Visible;
            UpdatePositionReadout();
            EarPlatePanel.Visibility=ear?Visibility.Visible:Visibility.Collapsed;
        }
        private void Kind_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||TrunnionPanel==null)return;
            slideRevision++;sliding=false;
            if(AxisSlideTool.IsActive)AxisSlideTool.End();
            axisOffsetMm=0;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true);return; }
            selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;
            UpdatePanels();PreviewText.Text="类型已切换，请点取立管或竖直辅助线。";
        }
        private void RefreshTrunnionChoices()
        {
            int index=TrunnionPipeDn.SelectedIndex;
            if(index<0)return;
            var candidates=VerticalPipeSupportCatalog.TrunnionCandidates(
                VerticalPipeSupportCatalog.TrunnionDns[index]);
            int kept=DnValue(TrunnionDn.SelectedValue as string);
            int restore=kept>0?Array.IndexOf(candidates,kept):-1;
            TrunnionDn.ItemsSource=candidates.Select(n=>"DN"+n).ToArray();
            TrunnionDn.SelectedIndex=restore<0?candidates.Length-1:restore;
        }
        private static int DnValue(string text)
        {
            int value;
            return text!=null&&text.Length>2&&text.StartsWith("DN")&&
                int.TryParse(text.Substring(2),NumberStyles.Integer,
                CultureInfo.InvariantCulture,out value)?value:0;
        }
        private void PipeDn_Changed(object sender,SelectionChangedEventArgs e)
        {
            if(initializing||TrunnionDn==null)return;
            RefreshTrunnionChoices();
            Parameter_Changed(sender,e);
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(initializing||!active||selection==null)return;
            // 滑动中参数变化：动态原型回锚点按新参数重建，进行中的拖动作废（同 A1 的
            // InvalidatePrototype 语义）；正式预览要等左键锁定后才写。
            if(sliding)
            {
                if(AxisSlideTool.IsActive)AxisSlideTool.InvalidatePrototype();
                return;
            }
            Regenerate();
        }
        private static double Number(string raw,string label,bool blankZero=false)
        {
            if(blankZero&&string.IsNullOrWhiteSpace(raw))return 0;
            double value;
            if(!double.TryParse(raw,NumberStyles.Float,CultureInfo.CurrentCulture,out value) &&
                !double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException(label+"应为数字。");
            return value;
        }
        private VerticalPipeSupportParameters Parameters()
        {
            var kind=Kind();
            var p=new VerticalPipeSupportParameters {Kind=kind};
            if(kind==VerticalPipeSupportKind.F10)
            {
                p.PipeDn=VerticalPipeSupportCatalog.F10Dns[Math.Max(0,EarPipeDn.SelectedIndex)];
                p.F10Length=(EarLength.SelectedIndex+1).ToString(CultureInfo.InvariantCulture);
                p.F10Height="ABCD"[Math.Max(0,EarHeight.SelectedIndex)].ToString();
                p.Material=EarMaterial.SelectedItem as string??"C1";
                p.AzimuthDegrees=Number(EarAngle.Text,"方位角");
                p.F10Fixed=FixedCheck.IsChecked==true;
            }
            else
            {
                p.PipeDn=VerticalPipeSupportCatalog.TrunnionDns[Math.Max(0,TrunnionPipeDn.SelectedIndex)];
                var candidates=VerticalPipeSupportCatalog.TrunnionCandidates(p.PipeDn);
                p.TrunnionDn=candidates[Math.Max(0,Math.Min(TrunnionDn.SelectedIndex,candidates.Length-1))];
                p.LengthMm=Number(LengthText.Text,"耳轴长度 L");
                p.WallMm=Number(WallText.Text,"耳轴壁厚",true);
                p.EndType=EndTypeCombo.SelectedItem as string??"A";
                p.Material=TrunnionMaterial.SelectedItem as string??"C1";
                p.AzimuthDegrees=Number(TrunnionAngle.Text,"方位角");
                p.BuildPad=PadCheck.IsChecked==true;
                p.PadThicknessMm=Number(PadThickness.Text,"补强板厚度");
            }
            return p;
        }
        private void Regenerate()
        {
            if(selection==null)return;
            PreviewUpdateHint.Set(UpdateButton,true);
            try
            {
                if(offsetPending)
                {
                    double value=ReadAxisOffset();
                    AxisPlacementCalculator.Shift(selection.ProjectedCenter(),new[]{selection.StartX,selection.StartY,selection.StartZ},
                        new[]{selection.EndX,selection.EndY,selection.EndZ},value,true);
                    axisOffsetMm=value;offsetPending=false;
                }
                VerticalPipeSupportCalculator.ValidateVertical(selection);
                var p=Parameters();
                var plan=VerticalPipeSupportCalculator.Calculate(p,selection.IsPipe,
                    selection.NominalMm,selection.PipeNumber);
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null) throw new InvalidOperationException("没有活动模型。");
                double scale=model.GetModelInfo().UorPerMeter/1000.0;
                var center=ShiftAlongAxis(selection,axisOffsetMm);
                UpdatePositionReadout();
                preview.Show(plan,new DPoint3d(center[0]*scale,center[1]*scale,center[2]*scale),
                    new DVector3d(selection.AxisX,selection.AxisY,selection.AxisZ),selection);
                ConfirmButton.IsEnabled=true;PreviewUpdateHint.Set(UpdateButton,false);
                PreviewText.Text="预览："+plan.Number+"；"+plan.Specification+
                    (axisOffsetMm!=0?"；沿轴偏移 "+
                        axisOffsetMm.ToString("0.#",CultureInfo.InvariantCulture)+" mm":"")+
                    (string.IsNullOrEmpty(selection.AxisNote)?"":"；"+selection.AxisNote);
                Status(NativePipeSupportSource.Eligible(selection)?"立管耳轴预览已生成；确认后关联原生管道。":"立管耳轴预览已生成；辅助线/参考来源生成普通构件，不建立ISO关联。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览未更新："+ex.Message;
                Status(ex.Message,true);
            }
        }
        /// <summary>
        /// 点取投影中心沿管轴偏移 offsetMm（正=朝 +Z 一侧，竖管即向上；毫米坐标），
        /// 偏移后再截断回线段两端，与 <see cref="PipeClampSelection.ProjectedCenter"/> 语义一致。
        /// </summary>
        private static double[] ShiftAlongAxis(PipeClampSelection s,double offsetMm)
        {
            return VerticalPipeSupportPositionCalculator.ShiftAlongAxis(s.ProjectedCenter(),
                new[]{s.StartX,s.StartY,s.StartZ},new[]{s.EndX,s.EndY,s.EndZ},offsetMm);
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||!locating)return;
                try
                {
                    preview.Cancel();
                    ConfirmButton.IsEnabled=false;
                    slideRevision++;axisOffsetMm=0;   // 新点取 = 新基准，沿用上一次的滑动偏移没有意义
                    selection=PipeClampReader.Read(located.ModelRef,located.ElementId,
                        located.ClickX,located.ClickY,located.ClickZ);
                    if(selection.IsPipe && selection.NominalMm.HasValue)
                    {
                        int matched=VerticalPipeSupportCatalog.MatchDn(selection.NominalMm.Value,Kind());
                        if(matched>0)
                        {
                            initializing=true;
                            if(Kind()==VerticalPipeSupportKind.F10)
                                EarPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.F10Dns,matched);
                            else
                            {
                                TrunnionPipeDn.SelectedIndex=Array.IndexOf(VerticalPipeSupportCatalog.TrunnionDns,matched);
                                RefreshTrunnionChoices();
                            }
                            initializing=false;
                        }
                    }
                    Regenerate();
                }
                catch(Exception ex) {initializing=false;selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);Status("点取失败："+ex.Message,true);}
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            locating=false;
            axisOffsetMm=0;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;
            PreviewText.Text="已结束点取。";
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                // 滑动工具还装着时先结束（Ended 会按当前偏移恢复正式预览）
                if(AxisSlideTool.IsActive)AxisSlideTool.End();
                PipeClampLocateTool.Begin();locating=true;
                Status("请选择立管或竖直辅助线。",false);
            }
            catch(Exception ex) {Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {
            AxisSlideTool.End();
            PipeClampLocateTool.End();
        }
        private void Update_Click(object sender,RoutedEventArgs e)
        {
            if(sliding&&AxisSlideTool.IsActive)
            {Status("请先左键锁定滑动位置（或右键取消滑动）。",false);return;}
            Regenerate();
        }
        /// <summary>回传给滑动工具的原型构造：在给定中心按当前参数建模（不写模型）。</summary>
        private Bentley.DgnPlatformNET.Elements.Element SlidePrototype(DPoint3d center)
        {
            var plan=VerticalPipeSupportCalculator.Calculate(Parameters(),selection.IsPipe,
                selection.NominalMm,selection.PipeNumber);
            return VerticalPipeSupportPreviewSession.CreateCell(plan,center,
                new DVector3d(selection.AxisX,selection.AxisY,selection.AxisZ));
        }
        /// <summary>滑动锚点（UOR）：点取投影中心按当前沿轴偏移落位后的点。</summary>
        private DPoint3d SlideAnchorUor(double scale)
        {
            var center=ShiftAlongAxis(selection,axisOffsetMm);
            return new DPoint3d(center[0]*scale,center[1]*scale,center[2]*scale);
        }
        /// <summary>
        /// 开始沿轴滑动：正式预览撤为动态原型（锚点=当前预览位置，起点不跳变）；
        /// 点取工具用 RetireForHandoff 静默交接，避开 Ended 双发的竞态（同 A1 做法）。
        /// </summary>
        private void Slide_Click(object sender,RoutedEventArgs e)
        {
            if(!active)return;
            if(selection==null){Status("请先点取立管或辅助线生成预览，再沿轴滑动。",true);return;}
            if(!preview.HasPreview||!ConfirmButton.IsEnabled){Status("请先成功更新预览。",true);return;}
            if(sliding&&AxisSlideTool.IsActive)
            {Status("已在沿轴滑动中：移动光标滑动，左键锁定，右键取消。",false);return;}
            try
            {
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null)throw new InvalidOperationException("没有活动模型。");
                double scale=model.GetModelInfo().UorPerMeter/1000.0;
                preview.Cancel();ConfirmButton.IsEnabled=false;
                slideAnchorOffsetMm=axisOffsetMm;
                var anchor=SlideAnchorUor(scale);
                var lineStart=new DPoint3d(selection.StartX*scale,selection.StartY*scale,
                    selection.StartZ*scale);
                var lineEnd=new DPoint3d(selection.EndX*scale,selection.EndY*scale,
                    selection.EndZ*scale);
                if(PipeClampLocateTool.IsActive)
                {
                    PipeClampLocateTool.RetireForHandoff();
                    locating=false;
                }
                slideRevision++;sliding=true;AxisOffsetText.IsEnabled=false;
                AxisSlideTool.Begin(anchor,lineStart,lineEnd,SlidePrototype);
                PreviewText.Text="沿轴滑动中：黄色十字为当前基点，蓝色十字为本次移动起点；X 输入本次位移，左键锁定，右键恢复。";
                Status("沿轴滑动已开始。",false);
            }
            catch(Exception ex){sliding=false;if(selection!=null)Regenerate();Status("无法开始沿轴滑动："+ex.Message,true);}
        }
        private void OnSlideLocked(DPoint3d locked)
        {
            if(!active||!sliding||selection==null)return;
            AxisOffsetText.IsEnabled=true;
            slideFinishing=true;
            int ticket=slideRevision;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||selection==null||ticket!=slideRevision)return;
                sliding=false;
                try
                {
                    var model=Session.Instance.GetActiveDgnModel();
                    double scale=model.GetModelInfo().UorPerMeter/1000.0;
                    var anchor=SlideAnchorUor(scale);
                    double dx=selection.AxisX,dy=selection.AxisY,dz=selection.AxisZ;
                    double len=Math.Sqrt(dx*dx+dy*dy+dz*dz);
                    if(len<=1.0e-9)throw new InvalidOperationException("管轴无效。");
                    if(dz<0){dx=-dx;dy=-dy;dz=-dz;}
                    // (锁定点-锚点)在轴向的分量（UOR），除以 scale 得毫米
                    axisOffsetMm=slideAnchorOffsetMm+
                        (((locked.X-anchor.X)*dx+(locked.Y-anchor.Y)*dy+
                          (locked.Z-anchor.Z)*dz)/len)/scale;
                    Regenerate();
                    Status("沿轴位置已锁定。",false);
                }
                catch(Exception ex)
                {
                    axisOffsetMm=slideAnchorOffsetMm;
                    Status("沿轴位置锁定失败："+ex.Message,true);
                }
            }),DispatcherPriority.Background);
        }
        private void OnSlideEnded()
        {
            if(!active)return;
            if(slideFinishing){slideFinishing=false;return;}
            if(!sliding)return;
            slideRevision++;
            // 右键/外部结束取消滑动：偏移保持进入时的值，恢复正式预览
            sliding=false;
            if(selection!=null)Regenerate();
            Status("已取消沿轴滑动，恢复原位置预览。",false);
        }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                slideRevision++;sliding=false;
                if(AxisSlideTool.IsActive)AxisSlideTool.End();
                axisOffsetMm=0;
                preview.Cancel();selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;
                PreviewText.Text="预览已取消。";
            }
            catch(Exception ex) {Status(ex.Message,true);}
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(sliding||!ConfirmButton.IsEnabled){Status("请先完成定位并更新预览。",true);return;}
            slideRevision++;
            try
            {
                string writeElapsed=WriteDuration.Measure(preview.Confirm);selection=null;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;
                sliding=false;axisOffsetMm=0;
                PreviewText.Text=preview.LastConfirmedNative?"已生成原生关联耳轴并写入清单；可继续点取下一处。":"已生成普通耳轴并写入清单（无ISO关联）；可继续点取下一处。";
                PreviewText.Text += " 写入耗时 "+writeElapsed+"。";
                Status("立管耳轴已生成；写入耗时 "+writeElapsed+"。",false);
            }
            catch(Exception ex) {Status("确认失败："+ex.Message,true);}
        }
        private void UpdatePositionReadout()
        {
            if(AxisPositionText==null)return;
            AxisOffsetText.IsEnabled=!sliding;
            if(selection==null){AxisPositionText.Text="定位基点：尚未点取。";SetOffsetText("0");return;}
            var p=ShiftAlongAxis(selection,axisOffsetMm);
            SetOffsetText(axisOffsetMm.ToString("0.###",CultureInfo.InvariantCulture));
            AxisPositionText.Text="基点："+(Kind()==VerticalPipeSupportKind.F10?"底板顶面与管轴交点":"耳轴中心线与管轴交点")+
                "；X="+p[0].ToString("0.###")+"，Y="+p[1].ToString("0.###")+"，Z="+p[2].ToString("0.###")+
                " mm；累计偏移 "+axisOffsetMm.ToString("0.###")+" mm（正值向上）。";
        }

        private double ReadAxisOffset()
        {
            double value;
            if(!double.TryParse(AxisOffsetText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(AxisOffsetText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException("沿轴偏移必须为数字。");
            return value;
        }

        private void SetOffsetText(string value)
        {
            offsetPending=false;syncingOffset=true;
            try { AxisOffsetText.Text=value; }
            finally { syncingOffset=false; }
        }

        private void AxisOffset_Changed(object sender,RoutedEventArgs e)
        {
            if(syncingOffset||selection==null||ConfirmButton==null)return;
            offsetPending=true;ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,true);
            PreviewText.Text="沿轴偏移尚未应用，请点击「应用偏移」后确认。";
        }

        private void ApplyOffset_Click(object sender,RoutedEventArgs e)
        {
            if(sliding){Status("请先锁定或取消沿轴滑动。",true);return;}
            double previous=axisOffsetMm;
            try
            {
                if(selection==null||!preview.HasPreview)throw new InvalidOperationException("请先生成预览。");
                double value=ReadAxisOffset();
                AxisPlacementCalculator.Shift(selection.ProjectedCenter(),new[]{selection.StartX,selection.StartY,selection.StartZ},
                    new[]{selection.EndX,selection.EndY,selection.EndZ},value,true);
                axisOffsetMm=value;Regenerate();
            }
            catch(Exception ex){axisOffsetMm=previous;Status(ex.Message,true);}
        }

        private void OnSlideMoved(DPoint3d point)
        {
            if(!active||!sliding||selection==null)return;
            double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
            var p=new[]{point.X/scale,point.Y/scale,point.Z/scale};
            double offset=AxisPlacementCalculator.Offset(selection.ProjectedCenter(),p,
                new[]{selection.StartX,selection.StartY,selection.StartZ},new[]{selection.EndX,selection.EndY,selection.EndZ});
            string text="当前基点 X="+p[0].ToString("0.###")+"，Y="+p[1].ToString("0.###")+"，Z="+p[2].ToString("0.###")+
                " mm；累计偏移 "+offset.ToString("0.###")+" mm；本次位移 "+(offset-slideAnchorOffsetMm).ToString("0.###")+" mm。";
            if(AxisPositionText.Text!=text)AxisPositionText.Text=text;
        }

        private static void Status(string message,bool error)
        { if(MainWindow.Current!=null)MainWindow.Current.SetStatus(message,error); }
    }
}
