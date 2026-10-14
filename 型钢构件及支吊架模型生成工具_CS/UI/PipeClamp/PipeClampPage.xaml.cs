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
    /// 放置管夹：一个入口承载 A1 / A2 / A22 / A24 / E1 / K1 / T4 / L2。A1 点位与开口方向分两步确定。
    /// </summary>
    internal partial class PipeClampPage : UserControl,IWorkspacePage
    {
        private readonly PipeClampPreviewSession preview=new PipeClampPreviewSession();
        private PipeClampSelection selection;
        /// <summary>点选参考文件元素时，按参考管轴物化出来的临时辅助线 id；0 表示没有。</summary>
        private ulong tempAxisLineId;
        private bool active,ready,locating,settingDn,orientationFinishing;
        private double a1AngleDeg;
        private double axisOffsetMm, slideAnchorOffsetMm;
        private bool sliding;
        private int slideRevision;
        private bool syncingOffset, offsetPending;


        public string PageId { get { return "pipe-clamp"; } }
        public string PageTitle { get { return "放置管夹"; } }
        public string PageSubtitle { get { return "A1 · U3 · A2 · A22 · A24 管夹 · E1 · K1 导向限位 · T4 · L2 管托"; } }
        public FrameworkElement View { get { return this; } }

        internal PipeClampPage()
        {
            InitializeComponent();
            PipeClampLocateTool.Picked+=OnPicked;
            PipeClampLocateTool.Ended+=OnEnded;
            A1ClampOrientationTool.Oriented+=OnA1Oriented;
            A1ClampOrientationTool.Ended+=OnA1Ended;
            AxisSlideTool.Locked+=OnSlideLocked;
            AxisSlideTool.Ended+=OnSlideEnded;
            AxisSlideTool.Moved+=OnSlideMoved;

            KindCombo.ItemsSource=PipeClampCatalog.All.Select(x=>x.Label).ToArray();
            A1DnCombo.ItemsSource=A1ClampCatalog.All
                .Select(row=>"DN"+row.Dn+"  |  "+row.Nps).ToArray();
            A2DnCombo.ItemsSource=A2ClampCatalog.All
                .Select(row=>"DN"+row.Dn+"  |  "+row.Nps).ToArray();
            A22DnCombo.ItemsSource=E1GuideCatalog.Dns.Select(dn=>"DN"+dn).ToArray();
            A24DnCombo.ItemsSource=E1GuideCatalog.Dns.Select(dn=>"DN"+dn).ToArray();
            E1DnCombo.ItemsSource=E1GuideCatalog.Dns.Select(dn=>"DN"+dn).ToArray();
            E1ItemCombo.ItemsSource=new[]{"自动（按 DN）","A","B","C","D","E"};
            K1DnCombo.ItemsSource=K1LimitCatalog.DnChoices
                .Select(dn=>K1LimitCatalog.DnLabel(dn)).ToArray();
            K1SubitemCombo.ItemsSource=new[]{"自动（按 DN）"}.Concat(
                K1LimitCatalog.All.Select(x=>K1LimitCatalog.SubitemLabel(x.Key))).ToArray();
            T4DnCombo.ItemsSource=T4ShoeCatalog.DnChoices
                .Select(dn=>T4ShoeCatalog.DnLabel(dn)).ToArray();
            L2DnCombo.ItemsSource=L2ShoeCatalog.DnChoices
                .Select(dn=>T4ShoeCatalog.DnLabel(dn)).ToArray();

            U3DnCombo.ItemsSource=U3ClampCatalog.Rows.Select(row=>"DN"+row.Dn+"  |  "+row.Nps).ToArray();
            U3ItemCombo.ItemsSource=new[]{"A · 承重/固定 · 两螺母在同一外侧","G · 承重/导向 · 两螺母一边一个"};
            U3MaterialCombo.ItemsSource=new[]{"C1 · 碳钢管","S · 不锈钢管 / 不锈钢螺栓","S1 · 不锈钢管 / EPDM · ≤120°C"};
            var last=PipeClampLastChoice.Load();
            U3DnCombo.SelectedIndex=Clamp(last.U3DnIndex,0,U3ClampCatalog.Rows.Length-1);
            U3ItemCombo.SelectedIndex=Clamp(last.U3ItemIndex,0,1);
            U3MaterialCombo.SelectedIndex=Clamp(last.U3MaterialIndex,0,2);
            U3SteelText.Text=last.U3Steel;U3TopText.Text=last.U3Top;
            U3RubberText.Text=last.U3Rubber;U3WallText.Text=last.U3Wall;
            KindCombo.SelectedIndex=Clamp(last.KindIndex,0,PipeClampCatalog.All.Length-1);
            A1DnCombo.SelectedIndex=Clamp(last.A1DnIndex,0,A1ClampCatalog.All.Length-1);
            A2DnCombo.SelectedIndex=Clamp(last.A2DnIndex,0,A2ClampCatalog.All.Length-1);
            A22DnCombo.SelectedIndex=Clamp(last.A22DnIndex,0,E1GuideCatalog.Dns.Length-1);
            A24DnCombo.SelectedIndex=Clamp(last.A24DnIndex,0,E1GuideCatalog.Dns.Length-1);
            E1DnCombo.SelectedIndex=Clamp(last.E1DnIndex,0,E1GuideCatalog.Dns.Length-1);
            E1ItemCombo.SelectedIndex=Clamp(last.E1ItemIndex,0,5);
            K1DnCombo.SelectedIndex=Clamp(last.K1DnIndex,0,K1LimitCatalog.DnChoices.Length-1);
            K1SubitemCombo.SelectedIndex=Clamp(last.K1SubitemIndex,0,K1LimitCatalog.All.Length);
            int t4Index=last.T4Dn.HasValue?
                Array.IndexOf(T4ShoeCatalog.DnChoices,last.T4Dn.Value):
                Clamp(last.T4DnIndex,0,12)+5;
            T4DnCombo.SelectedIndex=t4Index>=0?t4Index:5;
            L2DnCombo.SelectedIndex=Clamp(last.L2DnIndex,0,L2ShoeCatalog.DnChoices.Length-1);
            A2InsulationText.Text=Space(last.A2Insulation);
            A22ColdText.Text=Space(last.A22Cold);
            A22NameText.Text=Space(last.A22Name);
            A24ColdText.Text=Space(last.A24Cold);
            A24NameText.Text=Space(last.A24Name);
            E1MaterialText.Text=last.E1Material;
            E1StainlessCheck.IsChecked=last.E1Stainless;
            K1WidthText.Text=Space(last.K1Width);
            K1MaterialText.Text=Space(last.K1Material);
            T4InsulationText.Text=Space(last.T4Insulation);
            T4LengthText.Text=Space(last.T4Length);
            T4NameText.Text=Space(last.T4Name);
            SelectCode(T4TempCombo,last.T4Temp,"A");
            SelectCode(T4MaterialCombo,last.T4Material,"C1");
            SelectCode(T4FCombo,last.T4F,"");
            T4PipeCheck.IsChecked=last.T4Pipe;
            T4InsulationCheck.IsChecked=last.T4InsulationBuild;
            L2ColdText.Text=Space(last.L2Cold);
            L2FCodeText.Text=Space(last.L2FCode);
            L2PipeCheck.IsChecked=last.L2Pipe;
            L2InsulationCheck.IsChecked=last.L2InsulationBuild;

            ready=true;
            UpdatePanelVisibility();
            RefreshSpecification();
        }

        private static void SelectCode(ComboBox combo,string saved,string defaultCode)
        {
            string code=(saved??"").Trim().ToUpperInvariant();
            bool valid=combo.Items.Cast<ComboBoxItem>().Any(item=>(string)item.Tag==code);
            combo.SelectedValue=valid?code:defaultCode;
        }

        private static int Clamp(int value,int min,int max)
        { return value<min?min:(value>max?max:value); }
        private static string Space(string value)
        { return string.IsNullOrEmpty(value)?"":value; }

        public void OnActivated() { active=true; }
        public void OnDeactivated()
        {
            StopSlide();
            active=false; locating=false; PipeClampLocateTool.End();A1ClampOrientationTool.End();
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            TryDeleteTempAxisLine();
            selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
            PreviewText.Text="尚未选取源元素。";
        }
        public void OnWorkspaceClosing()
        {
            OnDeactivated();
            PipeClampLocateTool.Picked-=OnPicked;
            PipeClampLocateTool.Ended-=OnEnded;
            A1ClampOrientationTool.Oriented-=OnA1Oriented;
            A1ClampOrientationTool.Ended-=OnA1Ended;
            AxisSlideTool.Locked-=OnSlideLocked;
            AxisSlideTool.Ended-=OnSlideEnded;
            AxisSlideTool.Moved-=OnSlideMoved;
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
            U3Panel.Visibility=kind==PipeClampKind.U3BearingUBolt?Visibility.Visible:Visibility.Collapsed;
            A1Panel.Visibility=kind==PipeClampKind.A1UBolt?Visibility.Visible:Visibility.Collapsed;
            A2Panel.Visibility=kind==PipeClampKind.A2StandardTwoBolt?Visibility.Visible:Visibility.Collapsed;
            A22Panel.Visibility=kind==PipeClampKind.A22ColdTwoBolt?Visibility.Visible:Visibility.Collapsed;
            A24Panel.Visibility=kind==PipeClampKind.A24ColdFourBolt?Visibility.Visible:Visibility.Collapsed;
            E1Panel.Visibility=kind==PipeClampKind.E1Guide?Visibility.Visible:Visibility.Collapsed;
            K1Panel.Visibility=kind==PipeClampKind.K1Limit?Visibility.Visible:Visibility.Collapsed;
            T4Panel.Visibility=kind==PipeClampKind.T4Insulated?Visibility.Visible:Visibility.Collapsed;
            L2Panel.Visibility=kind==PipeClampKind.L2ColdShoe?Visibility.Visible:Visibility.Collapsed;
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
                    case PipeClampKind.U3BearingUBolt:
                        U3RubberText.IsEnabled=U3MaterialCombo.SelectedIndex==2;
                        U3SpecText.Text=U3Parameters(0).Specification;
                        break;
                    case PipeClampKind.A1UBolt:
                        A1SpecText.Text="当前规格：DN"+A1Parameters(0).Row.Dn;
                        break;
                    case PipeClampKind.A2StandardTwoBolt:
                    {
                        var plan=A2ClampCalculator.Calculate(A2Parameters(),isPipe,nominal,insulation);
                        A2SpecText.Text=CompactSpecification(plan.Dn,"保温",plan.InsulationMm);
                        break;
                    }
                    case PipeClampKind.A22ColdTwoBolt:
                    case PipeClampKind.A24ColdFourBolt:
                    {
                        bool four=CurrentKind()==PipeClampKind.A24ColdFourBolt;
                        var plan=A22ClampCalculator.Calculate(four?A24Parameters():A22Parameters(),
                            isPipe,nominal,selection==null?null:selection.OutsideMm,insulation,four);
                        (four?A24SpecText:A22SpecText).Text=CompactSpecification(plan.Dn,"保冷",plan.ColdThicknessMm);
                        break;
                    }
                    case PipeClampKind.E1Guide:
                        E1SpecText.Text="当前规格：DN"+E1Dn(selection)+" · 子项 "+(E1ItemKey()??"自动");
                        break;
                    case PipeClampKind.K1Limit:
                    {
                        var plan=K1LimitCalculator.Calculate(K1Parameters(),isPipe,nominal);
                        K1SpecText.Text="当前规格：DN"+plan.Dn+" · 编号 "+plan.Number;
                        break;
                    }
                    case PipeClampKind.T4Insulated:
                    {
                        var layout=T4ShoeCalculator.BuildLayout(T4Parameters(),isPipe,nominal,insulation);
                        T4ShoeCalculator.BuildBooleanLayout(layout);
                        T4SpecText.Text=CompactSpecification(layout.Dn,"隔热",layout.InsulationMm)+
                            " · 长度 "+layout.ShoeLengthMm.ToString("0.###",CultureInfo.InvariantCulture)+" mm";
                        bool pipeDn=isPipe && T4ShoeCatalog.MatchDn(nominal).HasValue;
                        bool pipeThickness=isPipe && insulation.HasValue;
                        T4SourceText.Text=pipeDn && pipeThickness?"已读取管道管径和隔热厚度。":
                            pipeDn?"管径来自管道；隔热厚度使用输入值。":
                            pipeThickness?"隔热厚度来自管道；管径使用所选值。":
                            "使用输入参数；点取管道后自动匹配。";
                        break;
                    }
                    case PipeClampKind.L2ColdShoe:
                    {
                        var layout=L2ShoeCalculator.BuildLayout(L2Parameters(),isPipe,nominal,insulation);
                        T4ShoeCalculator.BuildBooleanLayout(layout);
                        L2SpecText.Text=CompactSpecification(layout.Dn,"保冷",layout.InsulationMm);
                        break;
                    }
                }
            }
            catch(Exception ex)
            {
                string message="参数有误："+ex.Message;
                U3SpecText.Text=message;A1SpecText.Text=message;A2SpecText.Text=message;A22SpecText.Text=message;
                A24SpecText.Text=message;E1SpecText.Text=message;
                K1SpecText.Text=message;T4SpecText.Text=message;L2SpecText.Text=message;
                T4SourceText.Text="请检查输入参数。";
            }
        }

        private static string CompactSpecification(int dn,string thicknessLabel,double thickness)
        {
            return "当前规格：DN"+dn+" · "+thicknessLabel+" "+
                thickness.ToString("0.###",CultureInfo.InvariantCulture)+" mm";
        }

        private bool UsesOpeningDirection()
        {return CurrentKind()==PipeClampKind.A1UBolt||CurrentKind()==PipeClampKind.U3BearingUBolt;}
        private U3ClampPlan U3Parameters(double angle)
        {
            if(selection!=null)U3ClampCalculator.ValidateAxis(selection.AxisX,selection.AxisY,selection.AxisZ);
            return U3ClampCalculator.Calculate(U3ClampCatalog.Rows[Clamp(U3DnCombo.SelectedIndex,0,U3ClampCatalog.Rows.Length-1)].Dn,
                selection!=null&&selection.IsPipe,selection==null?null:selection.NominalMm,
                selection==null?null:selection.OutsideMm,selection==null?null:selection.InsulationMm,
                U3ItemCombo.SelectedIndex==1?"G":"A",new[]{"C1","S","S1"}[Clamp(U3MaterialCombo.SelectedIndex,0,2)],
                Number(U3SteelText.Text,"已有钢构厚度"),Number(U3TopText.Text,"钢构顶面高差"),
                U3MaterialCombo.SelectedIndex==2?Number(U3RubberText.Text,"EPDM厚度"):0,
                Number(U3WallText.Text,"管壁厚度"),angle,selection==null?"":selection.PipeNumber);
        }
        private A1ClampPlan A1Parameters(double angle)
        {return A1ClampCalculator.Calculate(A1ClampCatalog.All[Clamp(A1DnCombo.SelectedIndex,0,
            A1ClampCatalog.All.Length-1)].Dn,selection!=null&&selection.IsPipe,
            selection==null?null:selection.NominalMm,angle,
            selection==null?"":selection.PipeNumber);}
        private A2ClampParameters A2Parameters()
        {
            return new A2ClampParameters {
                FallbackDn=A2ClampCatalog.All[Clamp(A2DnCombo.SelectedIndex,0,
                    A2ClampCatalog.All.Length-1)].Dn,
                FallbackInsulationMm=Number(A2InsulationText.Text,"保温厚度") };
        }
        private A22ClampParameters A22Parameters()
        {
            return new A22ClampParameters {
                FallbackDn=E1GuideCatalog.Dns[Clamp(A22DnCombo.SelectedIndex,0,
                    E1GuideCatalog.Dns.Length-1)],
                FallbackColdThicknessMm=Number(A22ColdText.Text,"保冷厚度"),
                Name=A22NameText.Text };
        }
        private A22ClampParameters A24Parameters()
        {
            return new A22ClampParameters {
                FallbackDn=E1GuideCatalog.Dns[Clamp(A24DnCombo.SelectedIndex,0,
                    E1GuideCatalog.Dns.Length-1)],
                FallbackColdThicknessMm=Number(A24ColdText.Text,"保冷厚度"),
                Name=A24NameText.Text };
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
                Name=T4NameText.Text,TemperatureCode=(T4TempCombo.SelectedValue as string),
                MaterialCode=(T4MaterialCombo.SelectedValue as string),FCode=(T4FCombo.SelectedValue as string),
                BuildPipe=T4PipeCheck.IsChecked==true,
                BuildInsulation=T4InsulationCheck.IsChecked==true };
        }
        private L2ShoeParameters L2Parameters()
        {
            return new L2ShoeParameters {
                Dn=L2ShoeCatalog.DnChoices[Clamp(L2DnCombo.SelectedIndex,0,
                    L2ShoeCatalog.DnChoices.Length-1)],
                ColdMm=Number(L2ColdText.Text,"保冷厚度"),FCode=L2FCodeText.Text,
                BuildPipe=L2PipeCheck.IsChecked==true,
                BuildInsulation=L2InsulationCheck.IsChecked==true };
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
                parts.Add((CurrentKind()==PipeClampKind.L2ColdShoe ||
                    CurrentKind()==PipeClampKind.A22ColdTwoBolt ||
                    CurrentKind()==PipeClampKind.A24ColdFourBolt?"保冷厚度 ":"保温厚度 ")+
                    insulation.Value.ToString("0.#",CultureInfo.InvariantCulture)+" mm");
            return "　本次按管道"+(selection.IsFromReference?"（参考文件）":"")+"："+
                string.Join("、",parts.ToArray())+"。";
        }

        private void SaveLastChoice()
        {
            try
            {
                PipeClampLastChoice.Save(new PipeClampLastChoice.Data {
                    U3DnIndex=Math.Max(0,U3DnCombo.SelectedIndex),U3ItemIndex=Math.Max(0,U3ItemCombo.SelectedIndex),
                    U3MaterialIndex=Math.Max(0,U3MaterialCombo.SelectedIndex),
                    U3Steel=U3SteelText.Text,U3Top=U3TopText.Text,U3Rubber=U3RubberText.Text,U3Wall=U3WallText.Text,
                    KindIndex=Math.Max(0,KindCombo.SelectedIndex),
                    A1DnIndex=Math.Max(0,A1DnCombo.SelectedIndex),
                    A2DnIndex=Math.Max(0,A2DnCombo.SelectedIndex),
                    A22DnIndex=Math.Max(0,A22DnCombo.SelectedIndex),
                    A24DnIndex=Math.Max(0,A24DnCombo.SelectedIndex),
                    E1DnIndex=Math.Max(0,E1DnCombo.SelectedIndex),
                    E1ItemIndex=Math.Max(0,E1ItemCombo.SelectedIndex),
                    K1DnIndex=Math.Max(0,K1DnCombo.SelectedIndex),
                    K1SubitemIndex=Math.Max(0,K1SubitemCombo.SelectedIndex),
                    T4DnIndex=Math.Max(0,T4DnCombo.SelectedIndex),
                    T4Dn=T4ShoeCatalog.DnChoices[Clamp(T4DnCombo.SelectedIndex,0,
                        T4ShoeCatalog.DnChoices.Length-1)],
                    L2DnIndex=Math.Max(0,L2DnCombo.SelectedIndex),
                    A2Insulation=A2InsulationText.Text??"0",
                    A22Cold=A22ColdText.Text??"50",
                    A22Name=A22NameText.Text??"A22",
                    A24Cold=A24ColdText.Text??"50",
                    A24Name=A24NameText.Text??"A24",
                    E1Material=E1MaterialText.Text??"",
                    K1Width=K1WidthText.Text??"100",
                    K1Material=K1MaterialText.Text??"Q235B",
                    T4Insulation=T4InsulationText.Text??"50",
                    T4Length=T4LengthText.Text??"300",
                    T4Name=T4NameText.Text??"T4",
                    T4Temp=(T4TempCombo.SelectedValue as string)??"",
                    T4Material=(T4MaterialCombo.SelectedValue as string)??"",
                    T4F=(T4FCombo.SelectedValue as string)??"",
                    L2Cold=L2ColdText.Text??"50",
                    L2FCode=L2FCodeText.Text??"",
                    E1Stainless=E1StainlessCheck.IsChecked==true,
                    T4Pipe=T4PipeCheck.IsChecked==true,
                    T4InsulationBuild=T4InsulationCheck.IsChecked==true,
                    L2Pipe=L2PipeCheck.IsChecked==true,
                    L2InsulationBuild=L2InsulationCheck.IsChecked==true });
            }
            catch { }
        }

        private void Kind_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready) return;
            StopSlide();
            A1ClampOrientationTool.End();
            try { preview.Cancel(); } catch(Exception ex) { Status(ex.Message,true); }
            TryDeleteTempAxisLine();
            selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
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
            if(sliding){StopSlide();Regenerate();}
            RefreshSpecification();
            SaveLastChoice();
            if(A1ClampOrientationTool.IsActive)A1ClampOrientationTool.InvalidatePrototype();
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
            double[] projected=PlacementPoint(axisOffsetMm);
            center=new DPoint3d(projected[0]*scale,projected[1]*scale,projected[2]*scale);
            axis=new DVector3d(current.AxisX,current.AxisY,current.AxisZ);
        }

        private void A1Frame(PipeClampSelection current,out DPoint3d center,out DVector3d axis)
        {
            Frame(current,out center,out axis);
        }

        private Bentley.DgnPlatformNET.Elements.Element A1Prototype(double angle)
        {
            DPoint3d center;DVector3d axis;A1Frame(selection,out center,out axis);
            var parts=CurrentKind()==PipeClampKind.U3BearingUBolt?U3ClampBuilder.Build(U3Parameters(angle),center,axis):A1ClampBuilder.Build(A1Parameters(angle),center,axis);
            return new Bentley.DgnPlatformNET.Elements.CellHeaderElement(
                Session.Instance.GetActiveDgnModel(),CurrentType().CellName,
                DPoint3d.Zero,DMatrix3d.Identity,parts);
        }

        private void OnA1Oriented(double angle)
        {
            if(!active||selection==null)return;
            orientationFinishing=true;a1AngleDeg=angle;
            Dispatcher.BeginInvoke(new Action(delegate
            {if(!active||selection==null)return;RefreshSpecification();Regenerate();}),
                DispatcherPriority.Background);
        }
        private void OnA1Ended()
        {
            if(!active)return;
            if(orientationFinishing){orientationFinishing=false;return;}
            try{preview.Cancel();}catch(Exception ex){Status("管卡预览清理失败："+ex.Message,true);}
            selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false);ConfirmButton.IsEnabled=false;TryDeleteTempAxisLine();
            PreviewText.Text="已取消管卡开口方向调整。";
            Status("管卡方向调整已取消。",false);
        }

        private void Regenerate()
        {
            if(selection==null) return;
            PreviewUpdateHint.Set(UpdateButton,true);
            try
            {
                if(offsetPending)
                {
                    double value=ReadAxisOffset();
                    PlacementPoint(value);
                    axisOffsetMm=value;offsetPending=false;
                }
                var kind=CurrentKind();
                if(kind==PipeClampKind.U3BearingUBolt)
                {
                    DPoint3d center;DVector3d axis;A1Frame(selection,out center,out axis);
                    var plan=U3Parameters(a1AngleDeg);preview.ShowU3(plan,center,axis);
                    PreviewText.Text="预览："+plan.Number+" · 开口 "+a1AngleDeg.ToString("0.#",CultureInfo.InvariantCulture)+"°";
                }
                else if(kind==PipeClampKind.A1UBolt)
                {
                    DPoint3d center;DVector3d axis;A1Frame(selection,out center,out axis);
                    var plan=A1Parameters(a1AngleDeg);
                    preview.ShowA1(plan,center,axis);
                    PreviewText.Text="预览："+plan.AssemblyTag+" · 开口 "+a1AngleDeg.ToString("0.#",CultureInfo.InvariantCulture)+"°";
                }
                else if(kind==PipeClampKind.E1Guide)
                {
                    var plan=E1GuideCalculator.Calculate(E1Dn(selection),E1ItemKey(),
                        E1StainlessCheck.IsChecked==true,E1MaterialText.Text,
                        selection.StartX,selection.StartY,selection.StartZ,
                        selection.EndX,selection.EndY,selection.EndZ,
                        PlacementPoint(axisOffsetMm)[0],PlacementPoint(axisOffsetMm)[1],PlacementPoint(axisOffsetMm)[2],
                        selection.PipeNumber,selection.ElementId,selection.IsAuxiliaryLine);
                    preview.ShowE1(plan);
                    // 参考文件里的直线不参与"删除辅助线"：它的 ID 属于参考文件的 ID 空间，
                    // 在活动模型里删不掉，只能由用户在源文件里处理。
                    E1DeleteLineCheck.IsEnabled=selection.IsAuxiliaryLine&&!selection.IsPipe&&
                        !selection.IsFromReference;
                    PreviewText.Text="预览："+plan.Number;
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
                        PreviewText.Text="预览："+plan.AssemblyTag;
                    }
                    else if(kind==PipeClampKind.A22ColdTwoBolt)
                    {
                        var plan=A22ClampCalculator.Calculate(A22Parameters(),selection.IsPipe,
                            selection.NominalMm,selection.OutsideMm,selection.InsulationMm);
                        preview.ShowA22(plan,center,axis);
                        PreviewText.Text="预览："+plan.Number;
                    }
                    else if(kind==PipeClampKind.A24ColdFourBolt)
                    {
                        var plan=A22ClampCalculator.Calculate(A24Parameters(),selection.IsPipe,
                            selection.NominalMm,selection.OutsideMm,selection.InsulationMm,true);
                        preview.ShowA24(plan,center,axis);
                        PreviewText.Text="预览："+plan.Number;
                    }
                    else if(kind==PipeClampKind.K1Limit)
                    {
                        var plan=K1LimitCalculator.Calculate(K1Parameters(),selection.IsPipe,
                            selection.NominalMm);
                        preview.ShowK1(plan,center,axis);
                        PreviewText.Text="预览："+plan.Number;
                    }
                    else if(kind==PipeClampKind.L2ColdShoe)
                    {
                        var parameters=L2Parameters();
                        var layout=L2ShoeCalculator.BuildLayout(parameters,selection.IsPipe,
                            selection.NominalMm,selection.InsulationMm);
                        var boolean=T4ShoeCalculator.BuildBooleanLayout(layout);
                        preview.ShowL2(layout,boolean,center,axis,parameters.BuildPipe,
                            parameters.BuildInsulation);
                        PreviewText.Text="预览："+(string.IsNullOrEmpty(layout.Number)?"未编号":layout.Number);
                    }
                    else
                    {
                        var parameters=T4Parameters();
                        var layout=T4ShoeCalculator.BuildLayout(parameters,selection.IsPipe,
                            selection.NominalMm,selection.InsulationMm);
                        var boolean=T4ShoeCalculator.BuildBooleanLayout(layout);
                        preview.ShowT4(layout,boolean,center,axis,parameters.BuildPipe,
                            parameters.BuildInsulation);
                        PreviewText.Text="预览："+(string.IsNullOrEmpty(layout.Number)?"未编号":layout.Number);
                    }
                }
                if(selection!=null && !string.IsNullOrEmpty(selection.AxisNote))
                    PreviewText.ToolTip=selection.AxisNote;
                preview.BindSource(selection);
                UpdatePositionReadout();
                ConfirmButton.IsEnabled=true;PreviewUpdateHint.Set(UpdateButton,false);
                Status(selection.IsPipe&&!selection.IsFromReference?
                    "管夹预览已生成；确定后写入材料清单，并关联管道供轴测图提取。":
                    "管夹预览已生成；辅助线或参考来源仅写入本地材料清单，不建立轴测图关联。",false);
            }
            catch(Exception ex)
            {
                ConfirmButton.IsEnabled=false;
                Status("预览失败："+ex.Message,true);
            }
        }

        private void Pick_Click(object sender,RoutedEventArgs e)
        {
            if(sliding){StopSlide();Regenerate();}
            try
            {
                var model=Session.Instance.GetActiveDgnModel();
                if(model==null || !model.Is3d) throw new InvalidOperationException("请先打开三维模型。");
                if(A1ClampOrientationTool.IsActive)A1ClampOrientationTool.End();
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
                Status("点选管道或辅助线；A1 随后移动光标调整开口方向。",false);
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
                    StopSlide();axisOffsetMm=0;
                    selection=ReadSelection(located);UpdatePositionReadout();
                    RefreshSpecification();   // 规格行与预览用同一套参数来源
                    if(UsesOpeningDirection())
                    {
                        preview.Cancel();ConfirmButton.IsEnabled=false;
                        // 元素定位工具与动态绘制工具不能同时装载。交接用"静默退役"：
                        // 若在此调 End()（内部 ExitTool 挂起退出），紧随其后安装的方向工具
                        // 会在下一个原生事件被挂起退出误杀并触发一次伪 Ended，表现为
                        // "刚选中方向就提示已取消 A1 开口方向调整"。
                        PipeClampLocateTool.RetireForHandoff();
                        locating=false;
                        DPoint3d center;DVector3d axis;A1Frame(selection,out center,out axis);
                        if(CurrentKind()==PipeClampKind.U3BearingUBolt)U3Parameters(0);
                        A1ClampOrientationTool.Begin(center,axis,A1Prototype,CurrentType().Code+" 开口方向");
                        PreviewText.Text="位置已确定：移动光标调整开口方向，左键锁定并生成预览。";
                        Status("移动光标调整 "+CurrentType().Code+" 开口方向，左键锁定。",false);
                    }
                    else Regenerate();
                }
                catch(Exception ex)
                {
                    selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
                    TryDeleteTempAxisLine();
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
            selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
            ResetAuxiliaryLineOption();
            PreviewText.Text="已结束点取。";
            Status("已结束点取并取消未确认预览。",false);
        }
        private void End_Click(object sender,RoutedEventArgs e)
        {StopSlide();PipeClampLocateTool.End();A1ClampOrientationTool.End();Cancel_Click(sender,e);}
        private void Update_Click(object sender,RoutedEventArgs e)
        {if(sliding){Status("请先锁定或取消沿轴滑动。",false);return;}
            if(A1ClampOrientationTool.IsActive)
            {Status("请先在模型中左键锁定 A1 开口方向。",false);return;}
            Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {
            StopSlide();
            A1ClampOrientationTool.End();
            try
            {
                preview.Cancel(); selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
                TryDeleteTempAxisLine();
                ResetAuxiliaryLineOption();
                PreviewText.Text="预览已取消。"; Status("预览已取消。",false);
            }
            catch(Exception ex) { Status(ex.Message,true); }
        }
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {
            if(sliding||!ConfirmButton.IsEnabled){Status("请先完成定位并成功更新预览。",true);return;}

            try
            {
                bool deleteAuxiliary=E1DeleteLineCheck.IsChecked==true && selection!=null &&
                    selection.IsAuxiliaryLine && !selection.IsPipe && !selection.IsFromReference;
                var kind=CurrentKind();
                var current=selection;
                string writeElapsed=WriteDuration.Measure(preview.Confirm);
                // 临时辅助线的使命到此结束：管夹已经生成，把它删掉。
                TryDeleteTempAxisLine();
                if(kind==PipeClampKind.E1Guide && deleteAuxiliary && current!=null)
                    DeleteElement(current.ElementId);
                selection=null;axisOffsetMm=0;UpdatePositionReadout();PreviewUpdateHint.Set(UpdateButton,false); ConfirmButton.IsEnabled=false;
                ResetAuxiliaryLineOption();

                PreviewText.Text=(preview.LastConfirmedNative?"已生成原生支吊架并关联管道，可重新提取轴测图。":"已生成普通管夹并写入本地材料清单。")+(!locating?"点【开始点取】可放置下一处。":
                    "点取仍在进行中，可直接点取下一处。");
                PreviewText.Text += " 写入耗时 "+writeElapsed+"。";
                Status("管夹已生成；写入耗时 "+writeElapsed+"。",false);
            }
            catch(Exception ex) { Status("确认失败："+ex.Message,true); }
        }

        private double[] PlacementOrigin()
        {
            if(selection==null)throw new InvalidOperationException("请先点取管道或辅助线。");
            return UsesOpeningDirection()&&!selection.IsPipe?
                new[]{selection.ClickX,selection.ClickY,selection.ClickZ}:selection.ProjectedCenter();
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
            AxisPositionText.Text="基点："+(UsesOpeningDirection()&&!selection.IsPipe?"管卡辅助线点击点":"管轴上的构件定位截面")+
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
            if(sliding||A1ClampOrientationTool.IsActive){Status("请先完成鼠标定位。",true);return;}
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
            if(A1ClampOrientationTool.IsActive){Status("请先左键锁定 A1 开口方向。",true);return;}
            try
            {
                if(selection==null||!preview.HasPreview||!ConfirmButton.IsEnabled)
                    throw new InvalidOperationException("请先成功更新预览，再沿轴滑动。");
                var prototype=preview.CreatePrototype();
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
