using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>
    /// 九种管夹共用暂态预览生命周期：先显示新版、成功后再释放旧版；
    /// 确认时真实管道创建原生支吊架，其他来源创建普通Cell，并写原材料契约。
    /// </summary>
    internal sealed class PipeClampPreviewSession
    {
        private Element preview;
        private PipeClampTransientPreview display;
        private readonly List<PipeClampTransientPreview> pendingDisplays=new List<PipeClampTransientPreview>();
        private DPoint3d center;
        private DVector3d axis;
        private PipeClampKind kind;
        private string cellName;
        private PipeClampSelection sourceBinding;
        internal bool LastConfirmedNative { get; private set; }
        internal void BindSource(PipeClampSelection source)
        {
            sourceBinding=source==null?null:new PipeClampSelection {
                ElementId=source.ElementId,IsPipe=source.IsPipe,IsFromReference=source.IsFromReference,
                NativePipeInstanceId=source.NativePipeInstanceId,NativeModelToken=source.NativeModelToken,SourceUorPerMm=source.SourceUorPerMm,
                StartX=source.StartX,StartY=source.StartY,StartZ=source.StartZ,EndX=source.EndX,EndY=source.EndY,EndZ=source.EndZ,
                NominalMm=source.NominalMm,OutsideMm=source.OutsideMm,InsulationMm=source.InsulationMm };
        }

        private A2ClampPlan a2Plan;
        private A22ClampPlan a22Plan;
        private A1ClampPlan a1Plan;
        private U3ClampPlan u3Plan;
        private E1GuidePlan e1Plan;
        private K1LimitPlan k1Plan;
        private T4ShoeLayout t4Layout;
        private T4ShoeBooleanLayout t4Boolean;
        private bool t4BuildPipe,t4BuildInsulation;

        internal bool HasPreview { get { return preview!=null; } }
        internal PipeClampKind Kind { get { return kind; } }
        internal T4ShoeLayout T4Layout { get { return t4Layout; } }
        internal T4ShoeBooleanLayout T4Boolean { get { return t4Boolean; } }

        internal void ShowA2(A2ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(A2ClampBuilder.Build(plan,center,axis),A2ClampCatalog.CellName,
                PipeClampKind.A2StandardTwoBolt);
            a2Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowA22(A22ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(A22ClampBuilder.Build(plan,center,axis),A22ClampCatalog.CellName,
                PipeClampKind.A22ColdTwoBolt);
            a22Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowA24(A22ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(A22ClampBuilder.Build(plan,center,axis),A24ClampCatalog.CellName,
                PipeClampKind.A24ColdFourBolt);
            a22Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowA1(A1ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(A1ClampBuilder.Build(plan,center,axis),A1ClampCatalog.CellName,
                PipeClampKind.A1UBolt);
            a1Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowU3(U3ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(U3ClampBuilder.Build(plan,center,axis),U3ClampCatalog.CellName,PipeClampKind.U3BearingUBolt);
            u3Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowE1(E1GuidePlan plan)
        {
            Replace(E1GuideBuilder.Build(plan),E1GuideCatalog.SupportCode,
                PipeClampKind.E1Guide);
            e1Plan=plan;
            double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
            center=new DPoint3d(plan.CenterXmm*scale,plan.CenterYmm*scale,plan.CenterZmm*scale);
            axis=new DVector3d(plan.PipeX,plan.PipeY,0);
        }

        internal void ShowK1(K1LimitPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(K1LimitBuilder.Build(plan,center,axis),K1LimitCatalog.CellName,
                PipeClampKind.K1Limit);
            k1Plan=plan;this.center=center;this.axis=axis;
        }

        internal void ShowT4(T4ShoeLayout layout,T4ShoeBooleanLayout boolean,DPoint3d center,
            DVector3d axis,bool buildPipe,bool buildInsulation)
        {
            var parts=T4ShoeBuilder.Build(layout,boolean,center,axis,buildPipe,buildInsulation);
            Replace(parts,T4ShoeCatalog.CellName,PipeClampKind.T4Insulated);
            t4Layout=layout;this.center=center;this.axis=axis;
            t4Boolean=boolean;
            t4BuildPipe=buildPipe;
            t4BuildInsulation=buildInsulation;
        }

        internal void ShowL2(T4ShoeLayout layout,T4ShoeBooleanLayout boolean,DPoint3d center,
            DVector3d axis,bool buildPipe,bool buildInsulation)
        {
            var parts=T4ShoeBuilder.Build(layout,boolean,center,axis,buildPipe,buildInsulation);
            Replace(parts,L2ShoeCatalog.CellName,PipeClampKind.L2ColdShoe);
            t4Layout=layout;this.center=center;this.axis=axis;t4Boolean=boolean;
            t4BuildPipe=buildPipe;t4BuildInsulation=buildInsulation;
        }

        /// <summary>写入新版预览，成功后再删除旧版；删除失败则回滚新版，保证不残留。</summary>
        private void Replace(IList<Element> parts,string cellName,PipeClampKind newKind)
        {
            if(parts==null || parts.Count==0)
                throw new InvalidOperationException("管夹实体创建失败（无子元素）。");
            var model=Session.Instance.GetActiveDgnModel();
            var replacement=new CellHeaderElement(model,cellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            PipeClampTransientPreview replacementDisplay;
            try { replacementDisplay=PipeClampTransientPreview.Create(replacement); }
            catch { replacement.Dispose();throw; }
            try { ReleaseDisplay(); }
            catch
            {
                try { replacementDisplay.Close(); }
                catch { pendingDisplays.Add(replacementDisplay); }
                replacement.Dispose();
                throw;
            }
            preview?.Dispose();
            preview=replacement;
            display=replacementDisplay;
            kind=newKind;
            this.cellName=cellName;
        }

        /// <summary>使用当前已验证计划构建动态原型，不写模型或清单。</summary>
        internal Element CreatePrototype()
        { return BuildCell("AXIS_PLACEMENT_PREVIEW"); }

        private Element BuildCell(string name)
        {
            if(preview==null)throw new InvalidOperationException("请先成功生成预览。");
            IList<Element> parts;
            switch(kind)
            {
                case PipeClampKind.U3BearingUBolt:parts=U3ClampBuilder.Build(u3Plan,center,axis);break;
                case PipeClampKind.A1UBolt:parts=A1ClampBuilder.Build(a1Plan,center,axis);break;
                case PipeClampKind.A2StandardTwoBolt:parts=A2ClampBuilder.Build(a2Plan,center,axis);break;
                case PipeClampKind.A22ColdTwoBolt:
                case PipeClampKind.A24ColdFourBolt:parts=A22ClampBuilder.Build(a22Plan,center,axis);break;
                case PipeClampKind.E1Guide:parts=E1GuideBuilder.Build(e1Plan);break;
                case PipeClampKind.K1Limit:parts=K1LimitBuilder.Build(k1Plan,center,axis);break;
                case PipeClampKind.T4Insulated:
                case PipeClampKind.L2ColdShoe:parts=T4ShoeBuilder.Build(t4Layout,t4Boolean,center,axis,t4BuildPipe,t4BuildInsulation);break;
                default:throw new InvalidOperationException("未知的管夹种类。");
            }
            return new CellHeaderElement(Session.Instance.GetActiveDgnModel(),name,DPoint3d.Zero,DMatrix3d.Identity,parts);
        }

        internal void Confirm()
        {
            if(!LicenseService.IsActivated)throw new InvalidOperationException("请先激活软件。");
            if(preview==null) throw new InvalidOperationException("当前没有可确认的管夹预览。");
            LastConfirmedNative=false;
            if(NativePipeSupportSource.Eligible(sourceBinding))
            {
                ConfirmNative();
                LastConfirmedNative=true;
            }
            else ConfirmOrdinary();
            preview?.Dispose();
            preview=null;
            ClearPlans();
        }

        private void AttachStatistics(Element element)
        {
            switch(kind)
            {
                case PipeClampKind.U3BearingUBolt:
                    Statistics.AttachU3Clamp(element,u3Plan);break;
                case PipeClampKind.A1UBolt:
                    Statistics.AttachA1Clamp(element,a1Plan);break;
                case PipeClampKind.A2StandardTwoBolt:
                    Statistics.AttachA2Clamp(element,a2Plan); break;
                case PipeClampKind.A22ColdTwoBolt:
                    Statistics.AttachA22Clamp(element,a22Plan); break;
                case PipeClampKind.A24ColdFourBolt:
                    Statistics.AttachA24Clamp(element,a22Plan); break;
                case PipeClampKind.E1Guide:
                    Statistics.AttachE1Guide(element,e1Plan); break;
                case PipeClampKind.K1Limit:
                    Statistics.AttachK1Limit(element,k1Plan); break;
                case PipeClampKind.T4Insulated:
                    Statistics.AttachT4Shoe(element,t4Layout,t4Boolean,t4BuildPipe,
                        t4BuildInsulation); break;
                case PipeClampKind.L2ColdShoe:
                    Statistics.AttachL2Shoe(element,t4Layout,t4Boolean,t4BuildPipe,
                        t4BuildInsulation); break;
                default:
                    throw new InvalidOperationException("未知的管夹种类。");
            }
        }

        private static string N(double value) { return value.ToString("0.###",CultureInfo.InvariantCulture); }

        private NativePipeSupportDefinition IsoDefinition()
        {
            switch(kind)
            {
                case PipeClampKind.A1UBolt:return NativePipeSupportDefinition.Create("A1",a1Plan.Row.Dn,a1Plan.AssemblyTag,"M"+N(a1Plan.Row.Bolt)+"-ANG"+N(a1Plan.AngleDeg));
                case PipeClampKind.U3BearingUBolt:return NativePipeSupportDefinition.Create("U3",u3Plan.Clamp.Row.Dn,u3Plan.Number,u3Plan.Subitem+"-"+u3Plan.MaterialCode+"-M"+N(u3Plan.Clamp.Row.Bolt));
                case PipeClampKind.A2StandardTwoBolt:return NativePipeSupportDefinition.Create("A2",a2Plan.Dn,a2Plan.AssemblyTag,"B"+N(a2Plan.InsulationMm)+"-M"+N(a2Plan.BoltDiameterMm));
                case PipeClampKind.A22ColdTwoBolt:
                case PipeClampKind.A24ColdFourBolt:return NativePipeSupportDefinition.Create(kind==PipeClampKind.A22ColdTwoBolt?"A22":"A24",a22Plan.Dn,a22Plan.Number,"B"+N(a22Plan.ColdThicknessMm)+"-M"+a22Plan.BoltDiameterMm);
                case PipeClampKind.E1Guide:return NativePipeSupportDefinition.Create("E1",e1Plan.Dn,e1Plan.Number,e1Plan.Item.Key+"-"+e1Plan.Item.ProfileName+"-H"+N(e1Plan.HeightMm));
                case PipeClampKind.K1Limit:return NativePipeSupportDefinition.Create("K1",k1Plan.Dn,k1Plan.Number,k1Plan.SubitemKey+"-W"+N(k1Plan.ExistingWidthMm));
                case PipeClampKind.T4Insulated:
                case PipeClampKind.L2ColdShoe:return NativePipeSupportDefinition.Create(kind==PipeClampKind.T4Insulated?"T4":"L2",t4Layout.Dn,t4Layout.Number,"L"+N(t4Layout.ShoeLengthMm)+"-B"+N(t4Layout.InsulationMm));
                default:throw new InvalidOperationException("未登记的管夹出图种类。");
            }
        }

        private static void Text(Bentley.ECObjects.Instance.IECInstance instance,string name,string value)
        {
            NativeSupportData.RequireProperty(instance,name);
            instance[name].StringValue=value;
        }

        private void ConfirmNative()
        {
            try
            {
                NativeSupportLog.Run(log=>
                {
                    var definition=IsoDefinition();
                    log("确认源元素="+sourceBinding.ElementId+"；原生身份="+sourceBinding.NativePipeInstanceId+"；类别="+definition.Code);
                    double scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0;
                    var point=new[]{center.X/scale,center.Y/scale,center.Z/scale};
                    var pipe=NativePipeSupportSource.Resolve(sourceBinding,point,definition.Dn);
                    DTransform3d placement,inverse;
                    NativePipeSupportSource.Frame(center,axis,out placement,out inverse);
                    var instance=BMECInstanceManager.Instance.CreateECInstance(NativePipeSupportDefinition.NativeClass,true);
                    if(instance==null)throw new InvalidOperationException("当前工作集没有SUPPORT_LOCATION类。");
                    Text(instance,"DEVICE_TYPE_CODE",NativePipeSupportDefinition.DeviceTypeCode);
                    Text(instance,"NAME",NativePipeSupportDefinition.DeviceTypeCode+"-"+Guid.NewGuid().ToString("N"));
                    Text(instance,"ALIAS",definition.Label);
                    Text(instance,"DESCRIPTION",definition.Description);
                    Text(instance,"SPECIFICATION",pipe["SPECIFICATION"].StringValue??"");
                    NativeSupportData.RequireProperty(instance,"NOMINAL_DIAMETER");
                    var nominal=instance.ClassDefinition.Properties(true).First(p=>p.Name=="NOMINAL_DIAMETER");
                    if(string.Equals(nominal.Type.Name,"string",StringComparison.OrdinalIgnoreCase))
                        instance["NOMINAL_DIAMETER"].StringValue=definition.Dn.ToString(CultureInfo.InvariantCulture);
                    else instance["NOMINAL_DIAMETER"].DoubleValue=pipe["NOMINAL_DIAMETER"].DoubleValue;
                    log("类别="+definition.Code+"；标注="+definition.Label+"；父管="+pipe.InstanceId);
                    log("目标位置(mm)="+N(point[0])+","+N(point[1])+","+N(point[2])+"；UOR/mm="+N(scale));
                    NativePipeSupportWriter.Create(instance,pipe,placement,point,
                        ()=>LocalGraphics(inverse),
                        (support,element)=>
                        {
                            ValidateIsoTag(support,definition.Label);
                            string tag=support.Instance["ALIAS"].StringValue;
                            AttachStatistics(element);
                            NativePipeSupportStore.Write(element,new NativePipeSupportRecord {
                                Code=definition.Code,Dn=definition.Dn,NativeClass=NativePipeSupportDefinition.NativeClass,
                                PipeInstanceId=pipe.InstanceId,SupportInstanceId=support.Instance.InstanceId,
                                IsoTag=tag,NativeName=support.Instance["NAME"].StringValue,Description=definition.Description,Xmm=point[0],Ymm=point[1],Zmm=point[2] });
                            log("ISO引注="+tag+"；原生实例编号="+support.Instance["NAME"].StringValue+"；描述="+definition.Description);
                            log("ISO提取要求：SUPPORT_LOCATION中SSPPC对象的IE_TAG读取ALIAS，见部署脚本Install-PipeClampIsoTag.ps1。");
                        },ReleaseDisplay,log,support=>ValidateIsoTag(support,definition.Label));
                });
            }
            catch(Exception error)
            {
                try { RestoreDisplay(); }
                catch(Exception restoreError) { throw new AggregateException("原生确认失败，预览恢复也失败；请取消后重新点取。",error,restoreError); }
                throw;
            }
        }

        private static void ValidateIsoTag(BMECObject support,string expected)
        {
            if(support.Instance["DEVICE_TYPE_CODE"].StringValue!=NativePipeSupportDefinition.DeviceTypeCode ||
                !string.Equals(support.Instance["ALIAS"].StringValue,expected,StringComparison.Ordinal))
                throw new InvalidOperationException("管架引注编号未正确保存，已拒绝本次写入。");
        }

        private void ConfirmOrdinary()
        {
            if(TransactionManager.IsUndoInProgress)throw new InvalidOperationException("撤销/重做期间不能确认。");
            if(!TransactionManager.IsActive)TransactionManager.Activate();
            TransactionManager.CloseCurrentTransaction(true);
            var mark=TransactionManager.CurrentTransactionPosition;
            try
            {
                using(var final=BuildCell(cellName))
                {
                    if(final.AddToModel()!=StatusInt.Success)throw new InvalidOperationException("管夹写入失败。");
                    AttachStatistics(final);
                    ReleaseDisplay();
                }
                TransactionManager.CloseCurrentTransaction(true);
            }
            catch(Exception error)
            {
                var rollback=TransactionManager.CancelToPosition(mark,false);
                if(rollback!=StatusInt.Success)throw new InvalidOperationException("管夹确认失败且回滚未完成，请检查模型。",error);
                try { RestoreDisplay(); }
                catch(Exception restoreError) { throw new AggregateException("管夹确认失败，预览恢复也失败；请取消后重新点取。",error,restoreError); }
                throw;
            }
        }

        private void RestoreDisplay()
        {
            if(display!=null)return;
            var graphics=BuildCell(cellName);
            try { display=PipeClampTransientPreview.Create(graphics); }
            catch { graphics.Dispose();throw; }
            preview?.Dispose();preview=graphics;
        }

        private Element LocalGraphics(DTransform3d inverse)
        {
            var graphics=BuildCell(cellName);
            try
            {
                if(graphics.ApplyTransform(new TransformInfo(inverse))!=0)
                    throw new InvalidOperationException("管夹局部几何变换失败。");
                return graphics;
            }
            catch { graphics.Dispose();throw; }
        }

        internal void Cancel()
        {
            ReleaseDisplay();
            preview?.Dispose();
            preview=null;
            ClearPlans();
        }

        private void ClearPlans()
        {
            u3Plan=null;a1Plan=null;a2Plan=null;a22Plan=null;e1Plan=null;k1Plan=null;t4Layout=null;t4Boolean=null;
            t4BuildPipe=false; t4BuildInsulation=false;
            sourceBinding=null;
        }

        private void ReleaseDisplay()
        {
            PipeClampTransientPreview.RetryPending();
            for(int i=pendingDisplays.Count-1;i>=0;i--){pendingDisplays[i].Close();pendingDisplays.RemoveAt(i);}
            if(display==null)return;
            display.Close();display=null;
        }
    }
}
