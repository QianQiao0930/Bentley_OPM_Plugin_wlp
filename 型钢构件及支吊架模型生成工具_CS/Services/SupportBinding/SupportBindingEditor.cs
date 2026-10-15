using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    /// <summary>只改ALIAS和组合附加项；保留原生配方、父管、位置与全部材料记录。</summary>
    internal static class SupportBindingEditor
    {
        internal static void SynchronizeAllMaterials()
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销或重做，请稍后操作。");
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d || model.IsReadOnly || model.GetDgnFile().IsReadOnly)
                throw new InvalidOperationException("请打开可写的三维活动模型。");
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销事务。");
            TransactionManager.CloseCurrentTransaction(true);
            var mark = TransactionManager.CurrentTransactionPosition;
            bool deferred = BMECApi.Instance.DeferCommits;
            var materials = new SupportBindingMaterials();
            try
            {
                BMECApi.Instance.DeferCommits = false;
                materials.SynchronizeAll();
                TransactionManager.CloseCurrentTransaction(true);
            }
            catch (Exception error)
            {
                try
                {
                    if (TransactionManager.CancelToPosition(mark, false) != StatusInt.Success)
                        throw new InvalidOperationException("材料同步回滚失败。");
                    materials.Rollback();
                }
                catch (Exception rollbackError)
                { materials.Retain(); throw new AggregateException("材料同步失败且恢复未完成，请检查模型。", error, rollbackError); }
                throw new InvalidOperationException("材料同步失败，已回滚：" + error.Message, error);
            }
            finally { BMECApi.Instance.DeferCommits = deferred; }
        }
        internal static SupportBindingTarget Apply(SupportBindingTarget before, SupportBindingRecord draft)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销或重做，请稍后操作。");
            if (before == null || NativeSupportElements.ActiveModelToken() != before.ModelToken ||
                Session.Instance.GetActiveDgnFile().GetFileName() != before.FileName)
                throw new InvalidOperationException("活动模型已改变，请重新点取管夹。");
            var record = SupportBindingComposer.Copy(draft);
            if (record.SupportInstanceId != before.InstanceId || record.BaseTag != before.BaseTag)
                throw new InvalidOperationException("绑定草稿不属于所选管夹。");
            var located = new LocatedElement { ModelRef = Session.Instance.GetActiveDgnModel(), ElementId = before.ElementId };
            var current = SupportBindingReader.ReadTarget(located);
            SupportBindingComposer.ValidateUnchanged(before, current);
            string modelId = Session.Instance.GetActiveDgnModel().GetModelId().ToString();
            foreach (var member in record.Members)
            {
                if (member.ModelId != modelId || member.ElementId == before.ElementId)
                    throw new InvalidOperationException("承重支架模型不一致，或错误关联到管夹自身。");
                var actual = SupportBindingReader.ReadMember(new LocatedElement { ModelRef = located.ModelRef, ElementId = member.ElementId });
                if (!SupportBindingComposer.SameMember(member, actual))
                    throw new InvalidOperationException("承重支架编号或身份已改变，请重新点取：" + member.Tag);
            }
            string iso = SupportBindingComposer.Compose(record, true);
            string material = SupportBindingComposer.ComposeMaterial(record);
            var instance = DgnUtilities.GetInstanceByInstanceId(before.InstanceId);
            using (var acquired = PipeAlignment.OpenPlantObjectFactory.Acquire(before.InstanceId, instance))
            {
                var support = acquired.Object;
                if (support == null || !support.IsValid || acquired.OwnsObject)
                    throw new InvalidOperationException("无法取得可写的原生支架文档对象。");
                if (SupportBindingReader.Text(support.Instance, "ALIAS") != before.Alias)
                    throw new InvalidOperationException("原生支架缓存与文档引注不一致，请重新读取。");
                if (!TransactionManager.IsActive) TransactionManager.Activate();
                if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销事务。");
                TransactionManager.CloseCurrentTransaction(true);
                var mark = TransactionManager.CurrentTransactionPosition;
                var api = BMECApi.Instance;
                bool deferred = api.DeferCommits;
                var materials = new SupportBindingMaterials();
                try
                {
                    api.DeferCommits = false;
                    string currentDescription = SupportBindingReader.Text(support.Instance, "DESCRIPTION");
                    if (record.Members.Count > 0)
                    {
                        if (record.OriginalDescription == null) record.OriginalDescription = currentDescription ?? "";
                        support.Instance["DESCRIPTION"].StringValue = material;
                    }
                    else if (record.OriginalDescription != null)
                    {
                        support.Instance["DESCRIPTION"].StringValue = record.OriginalDescription;
                        record.OriginalDescription = null;
                    }
                    string payload = SupportBindingStore.Encode(record);
                    support.Instance["ALIAS"].StringValue = iso;
                    if (!new BMECObjectWriter(support).Serialize())
                        throw new InvalidOperationException("组合ISO引注保存失败。");
                    using (var element = NativeSupportElements.Get(support.Instance, true))
                    {
                        if ((ulong)element.ElementId != before.ElementId)
                            throw new InvalidOperationException("保存后管夹元素身份改变。");
                        SupportBindingStore.Write(element, record);
                    }
                    materials.Synchronize(before.Binding, record);
                    var result = SupportBindingReader.ReadTarget(located);
                    if (result.InstanceId != before.InstanceId || result.BaseTag != before.BaseTag || result.NativePayload != before.NativePayload)
                        throw new InvalidOperationException("保存后原生支架身份或原始编号记录发生改变。");
                    if (result.Alias != iso) throw new InvalidOperationException("组合ISO引注未完整保存。");
                    if (record.Members.Count > 0 && SupportBindingReader.Text(support.Instance, "DESCRIPTION") != material)
                        throw new InvalidOperationException("组合材料描述未完整保存。");
                    if (result.BindingPayload != payload) throw new InvalidOperationException("组合绑定附加项未完整保存。");
                    TransactionManager.CloseCurrentTransaction(true);
                    return result;
                }
                catch (Exception error)
                {
                    try
                    {
                        var rollback = TransactionManager.CancelToPosition(mark, false);
                        if (rollback != StatusInt.Success) throw new InvalidOperationException("回滚状态：" + rollback);
                        materials.Rollback();
                        // API所有的对象不Dispose；回滚后刷新缓存，防止后续写回失败草稿。
                        support.Refresh(); support.Resync();
                    }
                    catch (Exception rollbackError)
                    { materials.Retain(); throw new AggregateException("绑定失败且恢复未完成，请检查模型并重新读取。", error, rollbackError); }
                    throw new InvalidOperationException("绑定失败，已回滚本次写入：" + error.Message, error);
                }
                finally { api.DeferCommits = deferred; }
            }
        }
    }
}
