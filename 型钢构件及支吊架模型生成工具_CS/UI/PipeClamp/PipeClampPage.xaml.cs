using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 放置管夹：一个入口承载四种管夹（A2 / E1 / K1 / T4）。顶部下拉切换类型，
    /// 参数区按类型切换可见性；四种都是「点选管道 / 直线，在点击处沿其轴线生成整组」。
    /// </summary>
    internal partial class PipeClampPage : UserControl,IWorkspacePage
    {
        private readonly PipeClampPreviewSession preview=new PipeClampPreviewSession();
        private PipeClampSelection selection;
        /// <summary>点选参考文件元素时，按参考管轴物化出来的临时辅助线 id；0 表示没有。</summary>
        private ulong tempAxisLineId;
        private bool active,ready,locating,settingDn;

        public string PageId { get { return "pipe-clamp"; } }
        public string PageTitle { get { return "放置管夹"; } }
        public string PageSubtitle { get { return "A2 标准型 · E1 导向架 · K1 限位架 · T4 高温隔热管托"; } }
        public FrameworkElement View { get { return this; } }

        internal PipeClampPage()
        {
            InitializeComponent();
            PipeClampLocateTool.Picked+=OnPicked;
            PipeClampLocateTool.Ended+=OnEnded;

            KindCombo.ItemsSource=PipeClampCatalog.All.Select(x=>x.Label).ToArray();
            A2DnCombo.ItemsSource=A2ClampCatalog.All
                .Select(row=>"DN"+row.Dn+"  |  "+row.Nps).ToArray();
            E1DnCombo.ItemsSource=E1GuideCatalog.Dns.Select(dn=>"DN"+dn).ToArray();
            E1ItemCombo.ItemsSource=new[]{"自动（按 DN）","A","B","C","D","E"};
            K1DnCombo.ItemsSource=K1LimitCatalog.DnChoices
                .Select(dn=>K1LimitCatalog.DnLabel(dn)).ToArray();
            K1SubitemCombo.ItemsSource=new[]{"自动（按 DN）"}.Concat(
                K1LimitCatalog.All.Select(x=>K1LimitCatalog.SubitemLabel(x.Key))).ToArray();
            T4DnCombo.ItemsSource=T4ShoeCatalog.DnChoices
                .Select(dn=>T4ShoeCatalog.DnLabel(dn)).ToArray();

            var last=PipeClampLastChoice.Load();
            KindCombo.SelectedIndex=Clamp(last.KindIndex,0,PipeClampCatalog.All.Length-1);
            A2DnCombo.SelectedIndex=Clamp(last.A2DnIndex,0,A2ClampCatalog.All.Length-1);
            E1DnCombo.SelectedIndex=Clamp(last.E1DnIndex,0,E1GuideCatalog.Dns.Length-1);
            E1ItemCombo.SelectedIndex=Clamp(last.E1ItemIndex,0,5);
            K1DnCombo.SelectedIndex=Clamp(last.K1DnIndex,0,K1LimitCatalog.DnChoices.Length-1);
            K1SubitemCombo.SelectedIndex=Clamp(last.K1SubitemIndex,0,K1LimitCatalog.All.Length);
            T4DnCombo.SelectedIndex=Clamp(last.T4DnIndex,0,T4ShoeCatalog.DnChoices.Length-1);
            A2InsulationText.Text=Space(last.A2Insulation);
            E1MaterialText.Text=last.E1Material;
            E1StainlessCheck.IsChecked=last.E1Stainless;
            K1WidthText.Text=Space(last.K1Width);
            K1MaterialText.Text=Space(last.K1Material);
            T4InsulationText.Text=Space(last.T4Insulation);
            T4LengthText.Text=Space(last.T4Length);
            T4NameText.Text=Space(last.T4Name);
            T4TempText.Text=last.T4Temp; T4MaterialText.Text=last.T4Material;
            T4FText.Text=last.T4F;
            T4PipeCheck.IsChecked=last.T4Pipe;
            T4InsulationCheck.IsChecked=last.T4InsulationBuild;

            ready=true;
            UpdatePanelVisibility();
            RefreshSpecification();
        }

        private static int Clamp(int value,int min,int max)
        { return value<min?min:(value>max?max:value); }
        private static string Space(string value)
        { return string.IsNullOrEmpty(value)?"":value; }

        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            active=false; locating=false; PipeClampLocateTool.End();
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            TryDeleteTempAxisLine();
            selection=null; ConfirmButton.IsEnabled=false;
            PreviewText.Text="尚未选取源元素。";
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            PipeClampLocateTool.Picked-=OnPicked;
            PipeClampLocateTool.Ended-=OnEnded;
        }

        // -- 类型与参数 -------------------------------------------------------

        private PipeClampType CurrentType()
        {
            int index=KindCombo.SelectedIndex;
            if(index<0 || index>=PipeClampCatalog.All.Length) index=0;
            return PipeClampCatalog.All[index];
        }
        private PipeClampKind CurrentKind() { return CurrentType().Kind; }

        private void UpdatePanelVisibility()
        {
            var kind=CurrentKind();
            A2Panel.Visibility=kind==PipeClampKind.A2StandardTwoBolt?Visibility.Visible:Visibility.Collapsed;
            E1Panel.Visibility=kind==PipeClampKind.E1Guide?Visibility.Visible:Visibility.Collapsed;
            K1Panel.Visibility=kind==PipeClampKind.K1Limit?Visibility.Visible:Visibility.Collapsed;
            T4Panel.Visibility=kind==PipeClampKind.T4Insulated?Visibility.Visible:Visibility.Collapsed;
            KindHintText.Text=CurrentType().Hint;
        }

        private static double Number(string value,string label)
        {
            string text=(value??"").Trim();
            if(text.Length==0) throw new InvalidOperationException(label+"不能为空。");
            double parsed;
            if(!double.TryParse(text,NumberStyles.Float,CultureInfo.CurrentCulture,out parsed) &&
                !double.TryParse(text,NumberStyles.Float,CultureInfo.InvariantCulture,out parsed))
                throw new InvalidOperationException(label+"必须是有效数字。");
            return parsed;
        }

        /// <summary>
        /// 刷新当前类型的规格行。参数来源与 <see cref="Regenerate"/> 完全一致：
        /// 有点选结果时按管道信息（公称直径 / 保温厚度），否则按面板值 —— 避免
        /// “面板显示一套、模型里是另一套”。
        /// </summary>
        private void RefreshSpecification()
        {
            bool isPipe=selection!=null && selection.IsPipe;
            double? nominal=selection==null?null:selection.NominalMm;
            double? insulation=selection==null?null:selection.InsulationMm;
            try
            {
                switch(CurrentKind())
                {
                    case PipeClampKind.A2StandardTwoBolt:
                        A2SpecText.Text=A2ClampCalculator.Describe(
                            A2ClampCalculator.Calculate(A2Parameters(),isPipe,nominal,insulation))+
                            SourceNote(isPipe,nominal,insulation);
                        break;
                    case PipeClampKind.E1Guide:
                        E1SpecText.Text="E1 导向架：DN"+E1Dn(selection)+" · 子项 "+
                            (E1ItemKey()??"自动")+" · 材料 "+(E1MaterialText.Text??"")+
                            " · 编号 E1-…"+SourceNote(isPipe,nominal,null);
                        break;
                    case PipeClampKind.K1Limit:
                        K1SpecText.Text=K1LimitCalculator.Describe(K1LimitCalculator.Calculate(
                            K1Parameters(),isPipe,nominal))+SourceNote(isPipe,nominal,null);
                        break;
                    case PipeClampKind.T4Insulated:
                    {
                        var layout=T4ShoeCalculator.BuildLayout(T4Parameters(),isPipe,nominal,
                            insulation);
                        T4SpecText.Text=T4ShoeCalculator.Describe(layout,
                            T4ShoeCalculator.BuildBooleanLayout(layout))+
                            SourceNote(isPipe,nominal,insulation);
                        break;
                    }
                }
            }
            catch(Exception ex)
            {
                string message="参数有误："+ex.Message;
                A2SpecText.Text=message; E1SpecText.Text=message;
                K1SpecText.Text=message; T4SpecText.Text=message;
            }
        }

        private A2ClampParameters A2Parameters()
        {
            return new A2ClampParameters {
                FallbackDn=A2ClampCatalog.All[Clamp(A2DnCombo.SelectedIndex,0,
                    A2ClampCatalog.All.Length-1)].Dn,
                FallbackInsulationMm=Number(A2InsulationText.Text,"保温厚度") };
        }
        private int E1Dn(PipeClampSelection current)
        {
            int panel=E1GuideCatalog.Dns[Clamp(E1DnCombo.SelectedIndex,0,
                E1GuideCatalog.Dns.Length-1)];
            if(current==null || !current.IsPipe || !current.NominalMm.HasValue) return panel;
            var matched=E1GuideCatalog.MatchDn(current.NominalMm.Value);
            return matched.HasValue?matched.Value:panel;
        }
        private string E1ItemKey()
        { return E1ItemCombo.SelectedIndex<=0?null:E1ItemCombo.SelectedItem as string; }

        private K1LimitParameters K1Parameters()
        {
            return new K1LimitParameters {
                Dn=K1LimitCatalog.DnChoices[Clamp(K1DnCombo.SelectedIndex,0,
                    K1LimitCatalog.DnChoices.Length-1)],
                SubitemKey=K1SubitemCombo.SelectedIndex<=0?null:
                    K1LimitCatalog.All[K1SubitemCombo.SelectedIndex-1].Key,
                ExistingWidthMm=Number(K1WidthText.Text,"底部已有钢构宽度 W"),
                Material=K1MaterialText.Text };
        }
        private T4ShoeParameters T4Parameters()
        {
            return new T4ShoeParameters {
                Dn=T4ShoeCatalog.DnChoices[Clamp(T4DnCombo.SelectedIndex,0,
                    T4ShoeCatalog.DnChoices.Length-1)],
                InsulationMm=Number(T4InsulationText.Text,"隔热层厚度 B"),
                LengthMm=Number(T4LengthText.Text,"管托沿管轴总长 L"),
                Name=T4NameText.Text,TemperatureCode=T4TempText.Text,
                MaterialCode=T4MaterialText.Text,FCode=T4FText.Text,
                BuildPipe=T4PipeCheck.IsChecked==true,
                BuildInsulation=T4InsulationCheck.IsChecked==true };
        }

        /// <summary>说明本次尺寸的来源：按管道信息（并列出读到的值）还是按面板参数。</summary>
        private string SourceNote(bool isPipe,double? nominal,double? insulation)
        {
            if(selection==null) return "";
            if(!isPipe) return "　本次按面板参数生成。";
            var parts=new System.Collections.Generic.List<string>();
            parts.Add(nominal.HasValue
                ?"管道公称直径 "+nominal.Value.ToString("0.#",CultureInfo.InvariantCulture)+" mm"
                :"未读到公称直径（用面板 DN）");
            if(insulation.HasValue)
                parts.Add("保温厚度 "+insulation.Value.ToString("0.#",CultureInfo.InvariantCulture)+" mm");
            return "　本次按管道"+(selection.IsFromReference?"（参考文件）":"")+"："+
                string.Join("、",parts.ToArray())+"。";
        }

        private void SaveLastChoice()
        {
            try
            {
                PipeClampLastChoice.Save(new PipeClampLastChoice.Data {
                    KindIndex=Math.Max(0,KindCombo.SelectedIndex),
                    A2DnIndex=Math.Max(0,A2DnCombo.SelectedIndex),
                    E1DnIndex=Math.Max(0,E1DnCombo.SelectedIndex),
                    E1ItemIndex=Math.Max(0,E1ItemCombo.SelectedIndex),
                    K1DnIndex=Math.Max(0,K1DnCombo.SelectedIndex),
                    K1SubitemIndex=Math.Max(0,K1SubitemCombo.SelectedIndex),
                    T4DnIndex=Math.Max(0,T4DnCombo.SelectedIndex),
                    A2Insulation=A2InsulationText.Text??"0",
                    E1Material=E1MaterialText.Text??"",
                    K1Width=K1WidthText.Text??"100",
                    K1Material=K1MaterialText.Text??"Q235B",
                    T4Insulation=T4InsulationText.Text??"50",
                    T4Length=T4LengthText.Text??"300",
                    T4Name=T4NameText.Text??"T4",
                    T4Temp=T4TempText.Text??"",
                    T4Material=T4MaterialText.Text??"",
                    T4F=T4FText.Text??"",
                    E1Stainless=E1StainlessCheck.IsChecked==true,
                    T4Pipe=T4PipeCheck.IsChecked==true,
                    T4InsulationBuild=T4InsulationCheck.IsChecked==true });
            }
            catch { }
        }

        private void Kind_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            TryDeleteTempAxisLine();
            selection=null; ConfirmButton.IsEnabled=false;
            PreviewText.Text="尚未选取源元素。";
            ResetAuxiliaryLineOption();
            UpdatePanelVisibility();
            RefreshSpecification();
            SaveLastChoice();
        }
        private void K1Dn_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            settingDn=true;
            try { K1SubitemCombo.SelectedIndex=0; }
            finally { settingDn=false; }
            Parameter_Changed(sender,e);
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready || settingDn) return;
            RefreshSpecification();
            SaveLastChoice();
            if(preview.HasPreview) Regenerate();
        }
        private void ResetAuxiliaryLineOption()
        {
            E1DeleteLineCheck.IsChecked=false;
            E1DeleteLineCheck.IsEnabled=false;
        }

        // -- 点取与预览 -------------------------------------------------------

        private void Frame(PipeClampSelection current,out DPoint3d center,out DVector3d axis)
        {
            var model=Session.Instance.GetActiveDgnModel();
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            double[] projected=current.ProjectedCenter();
            center=new DPoint3d(projected[0]*scale,projected[1]*scale,projected[2]*scale);
            axis=new DVector3d(current.AxisX,current.AxisY,current.AxisZ);
        }

        private void Regenerate()
        {
            if(selection==null) return;
            try
            {
                var kind=CurrentKind();
                if(kind==PipeClampKind.E1Guide)
                {
                    var plan=E1GuideCalculator.Calculate(E1Dn(selection),E1ItemKey(),
                        E1StainlessCheck.IsChecked==true,E1MaterialText.Text,
                        selection.StartX,selection.StartY,selection.StartZ,
                        selection.EndX,selection.EndY,selection.EndZ,
                        selection.ClickX,selection.ClickY,selection.ClickZ,
                        selection.PipeNumber,selection.ElementId,selection.IsAuxiliaryLine);
                    preview.ShowE1(plan);
                    // 参考文件里的直线不参与"删除辅助线"：它的 ID 属于参考文件的 ID 空间，
                    // 在活动模型里删不掉，只能由用户在源文件里处理。
                    E1DeleteLineCheck.IsEnabled=selection.IsAuxiliaryLine&&!selection.IsPipe&&
                        !selection.IsFromReference;
                    PreviewText.Text="预览已生成："+plan.Number+"，DN"+plan.Dn+"。"+
                        (E1DeleteLineCheck.IsEnabled?"勾选「确认后删除辅助线」可删除所选直线。":"");
                }
                else
                {
                    DPoint3d center; DVector3d axis;
                    Frame(selection,out center,out axis);
                    if(kind==PipeClampKind.A2StandardTwoBolt)
                    {
                        var plan=A2ClampCalculator.Calculate(A2Parameters(),selection.IsPipe,
                            selection.NominalMm,selection.InsulationMm);
                        preview.ShowA2(plan,center,axis);
                        PreviewText.Text="预览已生成："+plan.AssemblyTag+"，"+
                            A2ClampCalculator.Describe(plan);
                    }
                    else if(kind==PipeClampKind.K1Limit)
                    {
                        var plan=K1LimitCalculator.Calculate(K1Parameters(),selection.IsPipe,
                            selection.NominalMm);
                        preview.ShowK1(plan,center,axis);
                        PreviewText.Text="预览已生成："+plan.Number+"，"+K1LimitCalculator.Describe(plan);
                    }
                    else
                    {
                        var parameters=T4Parameters();
                        var layout=T4ShoeCalculator.BuildLayout(parameters,selection.IsPipe,
                            selection.NominalMm,selection.InsulationMm);
                        var boolean=T4ShoeCalculator.BuildBooleanLayout(layout);
                        preview.ShowT4(layout,boolean,center,axis,parameters.BuildPipe,
                            parameters.BuildInsulation);
                        PreviewText.Text="预览已生成："+
                            (layout.Number.Length>0?layout.Number:"（未编号）")+"，"+
                            T4ShoeCalculator.Describe(layout,boolean)+
                            SourceNote(selection.IsPipe,selection.NominalMm,selection.InsulationMm);
                    }
                }
                if(selection!=null && !string.IsNullOrEmpty(selection.AxisNote))
                    PreviewText.Text+="　"+selection.AxisNote;
                ConfirmButton.IsEnabled=true;
                Status("管夹预览已生成；确定后写入支吊架材料清单。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                Status("预览失败："+ex.Message,true);
            }
        }

        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null || !model.Is3d) throw new InvalidOperationException("请先打开三维模型。");
                if(PipeClampLocateTool.IsActive)
                {
                    // 工具还装着（例如刚"确定生成"过）：只恢复页面状态，**不要重新安装** ——
                    // 重装会先"结束再安装"，白丢一次状态，也容易踩到延迟清理的竞态。
                    locating=true;
                    Status("已在点取中：直接在模型里点取下一处即可；要停止请点「结束点取」。",false);
                    return;
                }
                RefreshSpecification();
                PipeClampLocateTool.Begin(); locating=true;
                Status("悬停选择管道、直线或多段线，左键在点击处生成管夹预览；右键结束。",false);
            }
            catch(Exception ex) { Status("无法开始点取："+ex.Message,true); }
        }
        /// <summary>
        /// 读取点选结果。点选的是**参考文件**里的元素时，把管轴物化成活动文件里的一条
        /// 临时辅助线（<see cref="TempAxisLine"/>），再用已验证的"按线读取"路径读一遍，
        /// 并把参考元素读到的管道属性（公称直径 / 保温 / 管道号）并到这条线上 ——
        /// 生成路径因此完全不接触参考文件，用完即删这条辅助线。
        /// </summary>
        private PipeClampSelection ReadSelection(LocatedElement located)
        {
            TryDeleteTempAxisLine();   // 上一次点选留下的临时线先清掉
            var reference=PipeClampReader.Read(located.ModelRef,located.ElementId,
                located.ClickX,located.ClickY,located.ClickZ);
            if(!located.IsFromReference() || reference==null) return reference;
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null) return reference;
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            ulong lineId;
            try
            {
                lineId=TempAxisLine.Create(
                    new DPoint3d(reference.StartX*scale,reference.StartY*scale,reference.StartZ*scale),
                    new DPoint3d(reference.EndX*scale,reference.EndY*scale,reference.EndZ*scale));
            }
            catch(Exception ex)
            {
                // 建不出临时线就退回直接读取的结果 —— 不能因为辅助线失败就挡住生成。
                Status("临时辅助线未生成，改用直接读取的管轴："+ex.Message,true);
                return reference;
            }
            tempAxisLineId=lineId;
            var line=PipeClampReader.Read(lineId,located.ClickX,located.ClickY,located.ClickZ);
            line.IsPipe=reference.IsPipe;
            line.NominalMm=reference.NominalMm;
            line.OutsideMm=reference.OutsideMm;
            line.InsulationMm=reference.InsulationMm;
            line.PipeNumber=reference.PipeNumber;
            line.IsFromReference=true;
            line.IsAuxiliaryLine=false;   // 临时线由插件自己清理，不交给"删除辅助线"选项
            line.AxisNote=string.IsNullOrEmpty(reference.AxisNote)
                ?"已按参考管轴在活动文件中生成临时辅助线，确认或取消后自动删除。"
                :reference.AxisNote+"　已按参考管轴生成临时辅助线，确认或取消后自动删除。";
            return line;
        }

        /// <summary>删除物化出来的临时辅助线（异常向上抛，由调用方决定怎么提示）。</summary>
        private void DeleteTempAxisLine()
        {
            var id=tempAxisLineId;
            tempAxisLineId=0;
            if(id==0) return;
            TempAxisLine.Delete(id);
        }

        /// <summary>删除临时辅助线；删除失败只提示，不影响已经生成的东西。</summary>
        private void TryDeleteTempAxisLine()
        {
            try { DeleteTempAxisLine(); }
            catch(Exception ex)
            {
                Status("临时辅助线未自动删除（可在模型中手动删除）："+ex.Message,true);
            }
        }

        private void OnPicked(LocatedElement located)
        {
            if(!active || !locating || located==null) return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if(!active || !locating) return;
                try
                {
                    ResetAuxiliaryLineOption();
                    selection=ReadSelection(located);
                    RefreshSpecification();   // 规格行与预览用同一套参数来源
                    Regenerate();
                }
                catch(Exception ex)
                {
                    selection=null; ConfirmButton.IsEnabled=false;
                    // 诊断尾巴较长，状态栏一行会截断 —— 同时写进可换行的预览行。
                    PreviewText.Text="点取失败："+ex.Message;
                    Status("点取失败："+ex.Message,true);
                }
            }),DispatcherPriority.Background);
        }
        private void OnEnded()
        {
            if(!active) return;
            locating=false;
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            TryDeleteTempAxisLine();
            selection=null; ConfirmButton.IsEnabled=false;
            ResetAuxiliaryLineOption();
            PreviewText.Text="已结束点取。";
            Status("已结束点取并取消未确认预览。",false);
        }
        private void End_Click(object sender,RoutedEventArgs e) { PipeClampLocateTool.End(); }
        private void Update_Click(object sender,RoutedEventArgs e) { Regenerate(); }
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                preview.Cancel(); selection=null; ConfirmButton.IsEnabled=false;
                TryDeleteTempAxisLine();
                ResetAuxiliaryLineOption();
                PreviewText.Text="预览已取消。"; Status("预览已取消。",false);
            }
            catch(Exception ex) { Status(ex.Message,true); }
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            try
            {
                bool deleteAuxiliary=E1DeleteLineCheck.IsChecked==true && selection!=null &&
                    selection.IsAuxiliaryLine && !selection.IsPipe && !selection.IsFromReference;
                var kind=CurrentKind();
                var current=selection;
                preview.Confirm();
                // 临时辅助线的使命到此结束：管夹已经生成，把它删掉。
                TryDeleteTempAxisLine();
                if(kind==PipeClampKind.E1Guide && deleteAuxiliary && current!=null)
                    DeleteElement(current.ElementId);
                selection=null; ConfirmButton.IsEnabled=false;
                ResetAuxiliaryLineOption();
                PreviewText.Text="已确认生成并写入支吊架材料清单。点取仍在进行中，可直接点取下一处（无需再点「开始点取」）；要停止请点「结束点取」。";
                Status("管夹已生成；可继续点取下一处。",false);
            }
            catch(Exception ex) { Status("确认失败："+ex.Message,true); }
        }

        /// <summary>删除所选辅助线；删除前核对它仍是普通直线，避免误删管道或多段线。</summary>
        private static void DeleteElement(ulong id)
        {
            var model=Session.Instance.GetActiveDgnModel();
            var element=model==null?null:model.FindElementById(new ElementId(ref id));
            if(element==null || !element.IsValid) return;
            var com=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference
                .GetElementByID64(checked((long)id));
            if(com==null || com.Type!=Bentley.Interop.MicroStationDGN.MsdElementType.Line)
                throw new InvalidOperationException("所选辅助线已不是普通直线，未执行删除。");
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success) throw new InvalidOperationException("辅助线删除失败："+status);
        }

        private static void Status(string message,bool error)
        { if(MainWindow.Current!=null) MainWindow.Current.SetStatus(message,error); }
    }
}
