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
    internal partial class Q1SupportPage:UserControl,IWorkspacePage
    {
        private readonly Q1SupportPreviewSession preview=new Q1SupportPreviewSession();
        private readonly string[] fields={"TypeCombo","SmallDnCombo","HeightText","MirrorCheck","Q2ItemCombo","BearingCombo","SeriesCombo"};
        private PipeClampSelection selection;
        private int[] smallDns=Q2SupportCatalog.SmallDns;
        private bool ready,active,locating,sliding,syncingOffset,offsetPending,orienting,orientationFinishing;
        private double axisOffsetMm,slideAnchorOffsetMm,angleDeg;
        private int slideRevision;
        private int revision;
        public string PageId {get{return "q1-small-pipe-support";}}
        public string PageTitle {get{return "大管支撑小管";}}
        public string PageSubtitle {get{return "Q1 / Q2 · 角钢支撑与立管承重块";}}
        public FrameworkElement View {get{return this;}}
        internal Q1SupportPage()
        {
            InitializeComponent();
            SmallDnCombo.ItemsSource=Q2SupportCatalog.SmallDns.Select(dn=>"DN"+dn+" | "+A1ClampCatalog.Require(dn).Nps).ToArray();
            SmallDnCombo.SelectedIndex=0;PageLastInput.Restore(this,PageId,fields);ready=true;SetSeriesPanel();RefreshSpecification();
            PipeClampLocateTool.Picked+=OnPicked;PipeClampLocateTool.Ended+=OnLocateEnded;
            A1ClampOrientationTool.Oriented+=OnOriented;A1ClampOrientationTool.Ended+=OnOrientationEnded;
            AxisSlideTool.Locked+=OnSlideLocked;AxisSlideTool.Ended+=OnSlideEnded;AxisSlideTool.Moved+=OnSlideMoved;
        }
        public void OnActivated(){active=true;revision++;}
        public void OnDeactivated()
        {
            PageLastInput.Save(this,PageId,fields);active=false;revision++;
            if(locating)PipeClampLocateTool.End();
            StopSlide();StopOrientation();locating=false;CancelPreview();selection=null;axisOffsetMm=0;UpdatePositionReadout();
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();PipeClampLocateTool.Picked-=OnPicked;PipeClampLocateTool.Ended-=OnLocateEnded;
            A1ClampOrientationTool.Oriented-=OnOriented;A1ClampOrientationTool.Ended-=OnOrientationEnded;
            AxisSlideTool.Locked-=OnSlideLocked;AxisSlideTool.Ended-=OnSlideEnded;AxisSlideTool.Moved-=OnSlideMoved;
        }
        private bool NeedsAngle {get{return IsQ2&&TypeCombo.SelectedIndex==3;}}
        private bool IsQ2 {get{return SeriesCombo.SelectedIndex==1;}}
        private string Q2Item {get{return new[]{"A","B","C"}[Math.Max(0,Q2ItemCombo.SelectedIndex)];}}
        private void Series_Changed(object sender,RoutedEventArgs e)
        {if(!ready)return;End_Click(sender,e);SetSeriesPanel();Parameter_Changed(sender,e);}
        private void SetSeriesPanel()
        {
            ready=false;int selectedDn=smallDns[Math.Min(Math.Max(0,SmallDnCombo.SelectedIndex),smallDns.Length-1)];
            var dns=IsQ2?Q2SupportCatalog.SmallDns:Q1SupportCatalog.SmallDns;smallDns=dns;
            SmallDnCombo.ItemsSource=dns.Select(dn=>"DN"+dn+" | "+A1ClampCatalog.Require(dn).Nps).ToArray();
            SmallDnCombo.SelectedIndex=Math.Max(0,Array.IndexOf(dns,selectedDn));
            int old=Math.Max(0,TypeCombo.SelectedIndex);TypeCombo.Items.Clear();
            foreach(string label in IsQ2?new[]{"类型1 · 水平大管，两侧水平小管","类型2 · 水平大管，单侧水平小管","类型3 · 水平大管，单侧立管","类型4 · 立管支撑立管"}:new[]{"类型1 · 小管在下，两管垂直","类型2 · 小管在上，两管垂直","类型3 · 小管在上，两管平行（带垫板）","类型4 · 小管在下，两管平行（带垫板）"})TypeCombo.Items.Add(label);
            TypeCombo.SelectedIndex=Math.Min(old,3);Q2Panel.Visibility=IsQ2?Visibility.Visible:Visibility.Collapsed;
            DistanceLabel.Text=IsQ2?"两管中心间距 L（mm，最大1000）":"小管与大管中心间距 H（mm，最大1000）";ready=true;
        }
        private Q2SupportPlan Q2Plan()
        {
            if(selection==null||!selection.IsPipe)throw new InvalidOperationException("请点取可读取管径的支撑大管。");
            int? dn=A1ClampCatalog.MatchDn(selection.NominalMm);
            if(!dn.HasValue)throw new InvalidOperationException("未读到大管公称直径。");
            var p=Q2SupportCalculator.Calculate(TypeCombo.SelectedIndex+1,Q2Item,SmallDn,dn.Value,ReadHeight(),MirrorCheck.IsChecked==true,BearingCombo.SelectedIndex==1,selection.PipeNumber,selection.OutsideMm,selection.InsulationMm);
            p.AngleDeg=NeedsAngle?angleDeg:0;
            if(NeedsAngle)p.Specification+=" · 布置角 "+angleDeg.ToString("0.###")+"°";
            double[] x,y,z;Q2SupportCalculator.Axes(new[]{selection.AxisX,selection.AxisY,selection.AxisZ},p.BigVertical,p.Mirrored,out x,out y,out z,p.AngleDeg);return p;
        }
        private void ValidatePlan(){if(IsQ2)Q2Plan();else Plan();}
        private int SmallDn {get{return smallDns[Math.Max(0,SmallDnCombo.SelectedIndex)];}}
        private double ReadHeight()
        {
            double value;
            if(!double.TryParse(HeightText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out value)&&
                !double.TryParse(HeightText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                throw new InvalidOperationException("中心间距 "+(IsQ2?"L":"H")+" 必须是数字。");
            return value;
        }
        private Q1SupportPlan Plan()
        {
            if(selection==null||!selection.IsPipe)throw new InvalidOperationException("请点取可读取管径的支撑大管。");
            int? dn=A1ClampCatalog.MatchDn(selection.NominalMm);
            if(!dn.HasValue)throw new InvalidOperationException("未读到可匹配 A1 管卡的大管公称直径。");
            return Q1SupportCalculator.Calculate(TypeCombo.SelectedIndex+1,SmallDn,dn.Value,ReadHeight(),MirrorCheck.IsChecked==true,
                selection.PipeNumber,selection.OutsideMm,selection.InsulationMm);
        }
        private void Frame(out DPoint3d center,out DVector3d axis)
        {
            double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000;
            var point=PlacementPoint(axisOffsetMm);
            center=new DPoint3d(point[0]*scale,point[1]*scale,point[2]*scale);
            axis=new DVector3d(selection.AxisX,selection.AxisY,selection.AxisZ);
        }
        private Bentley.DgnPlatformNET.Elements.Element Prototype()
        {
            DPoint3d center;DVector3d axis;Frame(out center,out axis);
            return IsQ2?Q1SupportPreviewSession.Prototype(Q2Plan(),center,axis):Q1SupportPreviewSession.Prototype(Plan(),center,axis);
        }
        private void RefreshSpecification()
        {
            try
            {
                AngleButton.Visibility=NeedsAngle?Visibility.Visible:Visibility.Collapsed;
                BearingCombo.IsEnabled=IsQ2&&TypeCombo.SelectedIndex>=2;
                string item=IsQ2?Q2Item:Q1SupportCatalog.Subitem(SmallDn);
                SpecificationText.Text="子项 "+item+" · "+Q1SupportCatalog.Section(item)+" · 允许荷载 "+(IsQ2?Q2SupportCatalog.Load(item,ReadHeight()):Q1SupportCatalog.Load(item)).ToString("0.#")+" kN";
                if(selection!=null)SpecificationText.Text+="\n"+(IsQ2?Q2Plan().Specification:Plan().Specification);
            }
            catch(Exception ex){SpecificationText.Text=ex.Message;}
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;
            StopSlide();StopOrientation();revision++;ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,selection!=null);
            RefreshSpecification();
            
            if(selection!=null)PreviewText.Text="参数已修改，请更新预览后确认；Q2类型4可点击调整角度。";
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null||!model.Is3d)throw new InvalidOperationException("请先打开三维模型。");
                if(orienting){Status("请先左键锁定或右键取消布置角度。",false);return;}
                if(sliding){Status("请先锁定或取消沿轴滑动。",false);return;}
                if(locating&&PipeClampLocateTool.IsActive){PipeClampLocateTool.Begin();Status("已清空当前选择，可直接点击支撑大管。",false);return;}
                double h=ReadHeight();
                if(double.IsNaN(h)||double.IsInfinity(h)||h<=0||h>1000)throw new InvalidOperationException("中心间距须大于0且不超过1000 mm。");
                StopSlide();PipeClampLocateTool.Begin();locating=true;revision++;
                Status(NeedsAngle?"请点击主管立管，随后绕管轴选取布置角度。":"请点击支撑大管；直接生成固定方向预览。",false);
            }
            catch(Exception ex){Status(ex.Message,true);}
        }
        private void OnPicked(LocatedElement located)
        {
            if(!active||!locating||located==null)return;
            int token=revision;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||!locating||token!=revision)return;
                try
                {
                    ConfirmButton.IsEnabled=false;
                    var candidate=PipeClampReader.Read(located.ModelRef,located.ElementId,located.ClickX,located.ClickY,located.ClickZ);
                    StopSlide();selection=candidate;axisOffsetMm=0;angleDeg=0;UpdatePositionReadout();ValidatePlan();
                    if(NeedsAngle)BeginOrientation();else Regenerate();
                }
                catch(Exception ex)
                {

                    selection=null;ConfirmButton.IsEnabled=false;PreviewText.Text="点取失败："+ex.Message;Status(PreviewText.Text,true);
                }
            }),DispatcherPriority.Background);
        }
        private void StopOrientation()
        {bool was=orienting;orienting=false;orientationFinishing=false;if(was)A1ClampOrientationTool.End();}
        private void Angle_Click(object sender,RoutedEventArgs e)
        {
            if(!NeedsAngle||selection==null){Status("请先点取Q2类型4主管立管。",true);return;}
            if(sliding||orienting){Status("请先完成当前鼠标定位。",false);return;}
            try{ValidatePlan();BeginOrientation();}catch(Exception ex){StopOrientation();ConfirmButton.IsEnabled=false;Status(ex.Message,true);}
        }
        private void BeginOrientation()
        {
            DPoint3d center;DVector3d axis;Frame(out center,out axis);
            Q2Plan();StopSlide();double[] x,y,z;
            Q2SupportCalculator.Axes(new[]{axis.X,axis.Y,axis.Z},true,false,out x,out y,out z);
            preview.Cancel();ConfirmButton.IsEnabled=false;
            if(locating&&PipeClampLocateTool.IsActive){PipeClampLocateTool.RetireForHandoff();locating=false;}
            orienting=true;orientationFinishing=false;
            try
            {
                A1ClampOrientationTool.Begin(center,new DVector3d(z[0],z[1],z[2]),rotation=>
                {var plan=Q2Plan();plan.AngleDeg=rotation;return Q1SupportPreviewSession.Prototype(plan,center,axis);},"Q2类型4布置方向");
            }
            catch{orienting=false;throw;}
            PreviewText.Text="绕主管立管调整角度，左键锁定；右键取消。";
            Status(PreviewText.Text,false);
        }
        private void OnOriented(double angle)
        {
            if(!active||!orienting||selection==null)return;
            orientationFinishing=true;angleDeg=angle;int token=revision;
            Dispatcher.BeginInvoke(new Action(delegate{if(active&&token==revision&&selection!=null&&NeedsAngle)Regenerate();}),DispatcherPriority.Background);
        }
        private void OnOrientationEnded()
        {
            if(!active||!orienting)return;
            orienting=false;if(orientationFinishing){orientationFinishing=false;return;}
            revision++;CancelPreview();selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewText.Text="已取消布置角度选取。";
        }
        private void OnLocateEnded()
        {
            if(!active||!locating)return;
            locating=false;revision++;CancelPreview();selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewText.Text="已结束点取。";
        }
        private void Update_Click(object sender,RoutedEventArgs e)
        {
            if(orienting){Status("请先左键锁定或右键取消布置角度。",false);return;}
                if(sliding){Status("请先锁定或取消沿轴滑动。",false);return;}Regenerate();
        }
        private void Regenerate()
        {
            ConfirmButton.IsEnabled=false;
            try
            {
                if(orienting)throw new InvalidOperationException("请先左键锁定布置角度。");
                if(offsetPending){double value=ReadAxisOffset();PlacementPoint(value);axisOffsetMm=value;offsetPending=false;}
                DPoint3d center;DVector3d axis;Frame(out center,out axis);
                string number;double length;bool mirror;
                if(IsQ2){var p=Q2Plan();preview.Show(p,center,axis);number=p.Number;length=p.LengthMm;mirror=p.Mirrored;}
                else{var p=Plan();preview.Show(p,center,axis);number=p.Number;length=p.LengthMm;mirror=p.Mirrored;}
                ConfirmButton.IsEnabled=true;PreviewUpdateHint.Set(UpdateButton,false);
                PreviewText.Text="预览："+number+"\n构件 A 长 "+length.ToString("0.###")+" mm"+(mirror?" · 镜像":"")+(NeedsAngle?" · 角度 "+angleDeg.ToString("0.#")+"°":"");
                if(!string.IsNullOrEmpty(selection.AxisNote))PreviewText.Text+="\n"+selection.AxisNote;
                UpdatePositionReadout();RefreshSpecification();Status("支架预览已生成；确认后写入支吊架清单。",false);
            }
            catch(Exception ex){Status("预览失败："+ex.Message,true);}
        }
        private void CancelPreview()
        {
            ConfirmButton.IsEnabled=false;PreviewUpdateHint.Set(UpdateButton,false);
            try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {
            revision++;StopSlide();StopOrientation();if(locating)PipeClampLocateTool.End();locating=false;CancelPreview();selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewText.Text="预览已取消。";RefreshSpecification();
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(!ConfirmButton.IsEnabled||sliding||orienting)return;
            try
            {
                string elapsed=WriteDuration.Measure(preview.Confirm);revision++;selection=null;axisOffsetMm=0;UpdatePositionReadout();ConfirmButton.IsEnabled=false;
                PageLastInput.Save(this,PageId,fields);PreviewText.Text="已生成支架并写入支吊架清单。写入耗时 "+elapsed+"。";
                Status(PreviewText.Text,false);
            }
            catch(Exception ex){Status("确认失败："+ex.Message,true);}
        }
        private double[] PlacementOrigin()
        {
            if(selection==null)throw new InvalidOperationException("请先点取支撑大管。");
            return selection.ProjectedCenter();
        }

        private double[] PlacementPoint(double offset)
        {
            return AxisPlacementCalculator.Shift(PlacementOrigin(),
                new[]{selection.StartX,selection.StartY,selection.StartZ},
                new[]{selection.EndX,selection.EndY,selection.EndZ},offset,true);
        }

        private void UpdatePositionReadout()
        {
            if(AxisPositionText==null)return;
            AxisOffsetText.IsEnabled=!sliding;
            if(selection==null){AxisPositionText.Text="基点：尚未点取。";SetOffsetText("0");return;}
            var p=PlacementPoint(axisOffsetMm);
            SetOffsetText(axisOffsetMm.ToString("0.###",CultureInfo.InvariantCulture));
            AxisPositionText.Text="基点："+"管轴上的构件定位截面"+
                "；X="+p[0].ToString("0.###")+"，Y="+p[1].ToString("0.###")+"，Z="+p[2].ToString("0.###")+
                " mm";
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
            if(sliding||orienting){Status("请先完成鼠标定位。",true);return;}
            double previous=axisOffsetMm;
            try
            {
                if(selection==null||!preview.HasPreview)throw new InvalidOperationException("请先生成预览。");
                double value=ReadAxisOffset();
                PlacementPoint(value);axisOffsetMm=value;Regenerate();
            }
            catch(Exception ex){axisOffsetMm=previous;Status(ex.Message,true);}
        }

        private void StopSlide()
        {
            slideRevision++;
            bool wasSliding=sliding;sliding=false;AxisOffsetText.IsEnabled=true;
            if(wasSliding)AxisSlideTool.End();
        }

        private void Slide_Click(object sender,RoutedEventArgs e)
        {
            if(!active)return;
            if(sliding)return;
            if(orienting){Status("请先左键锁定布置角度。",false);return;}
            try
            {
                if(selection==null||!preview.HasPreview||!ConfirmButton.IsEnabled)
                    throw new InvalidOperationException("请先成功更新预览，再沿轴滑动。");
                var prototype=Prototype();
                double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
                var origin=PlacementOrigin();var projected=selection.ProjectedCenter();var current=PlacementPoint(axisOffsetMm);
                var anchor=new DPoint3d(current[0]*scale,current[1]*scale,current[2]*scale);
                var start=new DPoint3d((selection.StartX+origin[0]-projected[0])*scale,
                    (selection.StartY+origin[1]-projected[1])*scale,(selection.StartZ+origin[2]-projected[2])*scale);
                var end=new DPoint3d((selection.EndX+origin[0]-projected[0])*scale,
                    (selection.EndY+origin[1]-projected[1])*scale,(selection.EndZ+origin[2]-projected[2])*scale);
                preview.Cancel();ConfirmButton.IsEnabled=false;
                if(PipeClampLocateTool.IsActive){PipeClampLocateTool.RetireForHandoff();locating=false;}
                slideAnchorOffsetMm=axisOffsetMm;slideRevision++;sliding=true;AxisOffsetText.IsEnabled=false;
                AxisSlideTool.Begin(anchor,start,end,point=>prototype);
                PreviewText.Text="沿轴滑动中：黄色十字是当前基点，蓝色十字是本次移动起点。X 输入本次位移；左键锁定、右键恢复。";
            }
            catch(Exception ex){StopSlide();if(selection!=null)Regenerate();Status("无法开始滑动："+ex.Message,true);}
        }

        private void OnSlideMoved(DPoint3d point)
        {
            if(!active||!sliding||selection==null)return;
            double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
            var p=new[]{point.X/scale,point.Y/scale,point.Z/scale};
            double offset=AxisPlacementCalculator.Offset(PlacementOrigin(),p,
                new[]{selection.StartX,selection.StartY,selection.StartZ},new[]{selection.EndX,selection.EndY,selection.EndZ});
            string text="当前基点 X="+p[0].ToString("0.###")+"，Y="+p[1].ToString("0.###")+"，Z="+p[2].ToString("0.###")+
                " mm；累计偏移 "+offset.ToString("0.###")+" mm；本次位移 "+(offset-slideAnchorOffsetMm).ToString("0.###")+" mm。";
            if(AxisPositionText.Text!=text)AxisPositionText.Text=text;
        }

        private void OnSlideLocked(DPoint3d point)
        {
            if(!active||!sliding||selection==null)return;
            int ticket=slideRevision;sliding=false;AxisOffsetText.IsEnabled=true;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active||ticket!=slideRevision||selection==null)return;
                try
                {
                    double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
                    axisOffsetMm=AxisPlacementCalculator.Offset(PlacementOrigin(),new[]{point.X/scale,point.Y/scale,point.Z/scale},
                        new[]{selection.StartX,selection.StartY,selection.StartZ},new[]{selection.EndX,selection.EndY,selection.EndZ});
                    Regenerate();
                }
                catch(Exception ex){axisOffsetMm=slideAnchorOffsetMm;Regenerate();Status(ex.Message,true);}
            }),DispatcherPriority.Background);
        }

        private void OnSlideEnded()
        {
            if(!active||!sliding)return;
            sliding=false;AxisOffsetText.IsEnabled=true;slideRevision++;axisOffsetMm=slideAnchorOffsetMm;
            if(selection!=null)Regenerate();
            Status("已取消沿轴滑动，恢复原位置。",false);
        }


        private static void Status(string text,bool error){if(MainWindow.Current!=null)MainWindow.Current.SetStatus(text,error);}
    }
}
