using System;
using Bentley.ECObjects.Instance;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 取"挂到文档上"的 OpenPlant 业务对象（实测教训，见 <see cref="OpenPlant2024PipeAdapter"/> 类注释）。
    /// <para>
    /// 顺序：API 对象缓存 → <c>BMECApi.CreateBMECObjectForInstance</c>（API 创建 + 入缓存）→
    /// <c>new BMECObject(instance)</c> 兜底。**读**用哪条都行（游离副本读得也对），
    /// **写**必须走前两条 —— 第三种的改动不会落到模型上。
    /// </para>
    /// <para>
    /// ⚠️ 从缓存 / API 工厂拿到的对象**归 API 所有，绝不能 Dispose** —— 那会把 API 手里的
    /// 活对象销毁掉。<see cref="Acquired"/> 用 <c>OwnsObject</c> 把这件事收在一处，
    /// 调用方一律 <c>using</c> 即可。
    /// </para>
    /// </summary>
    internal static class OpenPlantObjectFactory
    {
        internal static IECInstance ResolveInstance(string instanceId)
        {
            if (string.IsNullOrEmpty(instanceId)) return null;
            try
            {
                IECInstance instance = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities.GetInstanceByInstanceId(instanceId);
                if (instance != null) return instance;
            }
            catch { }
            try
            {
                BMECObject cached = BMECApi.Instance.ObjectCache.FindByInstanceId(instanceId);
                return cached != null && cached.IsValid ? cached.Instance : null;
            }
            catch { return null; }
        }

        internal sealed class Acquired : IDisposable
        {
            internal BMECObject Object;
            internal bool OwnsObject;
            internal string Source;

            public void Dispose()
            {
                if (!OwnsObject || Object == null) return;
                try { Object.Dispose(); }
                catch { }
            }
        }

        internal static Acquired Acquire(string instanceId, IECInstance instance)
        {
            Acquired acquired = new Acquired();

            if (!string.IsNullOrEmpty(instanceId))
            {
                try
                {
                    BMECObject cached = BMECApi.Instance.ObjectCache.FindByInstanceId(instanceId);
                    if (cached != null && cached.IsValid)
                    {
                        // 原生 Undo/Redo 之后缓存坐标可能过期，读取前从持久化模型刷新。
                        cached.Refresh();
                        cached.Resync();
                        acquired.Object = cached;
                        acquired.Source = "API 对象缓存（已挂到文档）";
                        return acquired;
                    }
                }
                catch
                {
                    // 缓存不可用不是错误，继续走工厂。
                }
            }

            if (instance == null) return acquired;

            try
            {
                BMECObject created = BMECApi.Instance.CreateBMECObjectForInstance(instance);
                if (created != null && created.IsValid)
                {
                    acquired.Object = created;
                    acquired.Source = "BMECApi.CreateBMECObjectForInstance（API 创建）";
                    try { BMECApi.Instance.ObjectCache.Add(created); }
                    catch { }
                    return acquired;
                }
            }
            catch
            {
                // 落到最后的兜底。
            }

            acquired.Object = new BMECObject(instance);
            acquired.OwnsObject = true;
            acquired.Source = "new BMECObject(instance) —— ⚠️ 游离副本，改动不会写回模型";
            return acquired;
        }
    }
}
