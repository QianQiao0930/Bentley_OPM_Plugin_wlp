using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>从离线局部几何创建带父管关系的原生支吊架；成功才替换预览，一次Undo事务。</summary>
    internal static class NativePipeSupportWriter
    {
        private static readonly List<BMECObject> unrecovered = new List<BMECObject>();

        internal static void Create(IECInstance instance, IECInstance pipe, DTransform3d placement,
            double[] pointMm, Func<Element> graphicsFactory, Action<BMECObject, Element> attach,
            Action complete, Action<string> log)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销/重做，请稍后再试。");
            if (instance == null || pipe == null || pipe.ClassDefinition.Name != "PIPE") throw new InvalidOperationException("原生支吊架需要真实直管。");
            using (var source = NativeSupportElements.Get(pipe, true)) { }
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            NativeSupportData.Finite(scale);
            if (scale <= 0 || pointMm == null || pointMm.Length != 3) throw new InvalidOperationException("模型单位或支撑点无效。");
            foreach (double value in pointMm) NativeSupportData.Finite(value);
            var api = BMECApi.Instance;
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销事务。");
            TransactionManager.CloseCurrentTransaction(true);
            var mark = TransactionManager.CurrentTransactionPosition;
            bool deferred = api.DeferCommits;
            BMECObject support = null;
            int cacheKey = -1;
            log("写入前DeferCommits=" + deferred + "；本次立即提交，不提交全局待处理集合。");
            try
            {
                api.DeferCommits = false;
                support = new BMECObject(instance, true);
                support.RelatedInstance = pipe;
                using (var graphics = graphicsFactory())
                    NativeSupportGraphics.Create(support, graphics, placement, log, () =>
                    {
                        log("原生实例=" + support.Instance.InstanceId);
                        if (!api.IsPersistentId(support.Instance.InstanceId)) throw new InvalidOperationException("原生实例仍未持久化。");
                        api.FindAllInformationOnInstance(support.Instance);
                        api.GetSectionalDataForSupport(support.Instance);
                        NativeSupportData.Write(support, pointMm);
                        if (!new BMECObjectWriter(support).Serialize()) throw new InvalidOperationException("原生支吊架业务数据写入失败。");
                        cacheKey = api.ObjectCache.Add(support);
                        if (cacheKey < 0) throw new InvalidOperationException("原生支吊架未能加入文档缓存。");
                        using (var element = NativeSupportElements.Get(support.Instance, true))
                        {
                            log("新元素=" + (ulong)element.ElementId);
                            attach(support, element);
                        }
                        using (var readback = PipeAlignment.OpenPlantObjectFactory.Acquire(support.Instance.InstanceId, support.Instance))
                        {
                            if (readback.Object == null || !readback.Object.IsValid) throw new InvalidOperationException("无法重读原生支吊架。");
                            if (readback.Object.Instance.InstanceId != support.Instance.InstanceId) throw new InvalidOperationException("重读的原生支吊架身份不一致。");
                            NativeSupportData.Validate(readback.Object, pipe.InstanceId, pointMm, scale, log);
                        }
                        complete();
                    });
                TransactionManager.CloseCurrentTransaction(true);
            }
            catch (Exception error)
            {
                StatusInt rollback;
                try { rollback = TransactionManager.CancelToPosition(mark, false); }
                catch (Exception rollbackError)
                {
                    Retain(support, cacheKey, log);
                    throw new AggregateException("支吊架写入失败且回滚未完成，请检查模型。", error, rollbackError);
                }
                if (rollback != StatusInt.Success)
                {
                    Retain(support, cacheKey, log);
                    throw new InvalidOperationException("支吊架写入失败且回滚未完成，请检查模型：" + rollback, error);
                }
                if (cacheKey >= 0) api.ObjectCache.Remove(cacheKey);
                support?.Dispose();
                throw new InvalidOperationException("支吊架写入失败，已回滚本次写入：" + error.Message, error);
            }
            finally { api.DeferCommits = deferred; log("已恢复DeferCommits=" + deferred); }
        }

        private static void Retain(BMECObject support, int cacheKey, Action<string> log)
        {
            if (support != null && cacheKey < 0) unrecovered.Add(support);
            log("回滚失败，保留对象所有权；请按上方实例/元素ID检查残留。");
        }
    }
}
