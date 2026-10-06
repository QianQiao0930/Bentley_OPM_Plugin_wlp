// API 探针 2：验证「改完之后怎么让修改落地」这一组候选成员能不能被 C# 消费。
//
// 背景（OPM 2024 真机实测）：BMECObject.SetLinearPoints / Transform3d 的 setter 调用后
// 没有任何异常，但元素几何与读数都不变，Refresh()/Resync() 也没用。
// 怀疑"设置"只改了内存副本，需要一个显式的同步 / 提交步骤。
//
// BMECObject 上有几个名字正好对得上这个症状的成员：
//   SetTransform / SyncTransform / GetTransform / GetOrigin   ← Sync 才是"写出去"
//   AllowGraphicsUpdate                                        ← 不允许更新图形时改了也看不见
//   DiscoverConnectionsEx / UpdateConnections                  ← 移动后重建连接
// 另有 BMECObjectWriter.Serialize()、BMECApi.Persistence.CommitChangeSet(...) 等持久化入口。
//
// 本文件只做编译期可用性验证，不执行任何逻辑。

using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace PipeAlignApiProbe
{
    internal static class WriteBackProbe
    {
        internal static void Touch(IECInstance instance, Element element)
        {
            BMECObject obj = new BMECObject(instance);

            // ---- 图形更新开关 ----
            bool allow = obj.AllowGraphicsUpdate;
            obj.AllowGraphicsUpdate = true;
            Console.WriteLine(allow);

            // ---- 同步 / 提交候选 ----
            obj.Refresh();
            obj.Resync();
            obj.DiscoverConnections();
            obj.DiscoverConnectionsEx();
            obj.UpdateConnections();
            obj.UpdateConnections(true, 0UL);
            obj.UpdateConnectionAtPort(0, false, 0UL);

            // ---- 写回器 ----
            var writer = new BMECObjectWriter(obj);
            bool serialized = writer.Serialize();
            Console.WriteLine(serialized);

            // ---- 延迟提交 ----
            BMECApi api = BMECApi.Instance;
            bool defer = api.DeferCommits;
            api.DeferCommits = true;
            ChangeSet deferred = api.DeferedChangeSet;
            if (deferred != null) api.Persistence.CommitChangeSet(deferred);
            api.DeferCommits = defer;
            bool inAgenda = api.InAgendaOperation;
            Console.WriteLine(inAgenda);

            // ---- 元素侧：强制图形重建 ----
            StatusInt replaced = element.ReplaceInModel(element);
            Console.WriteLine(replaced);
        }

        /// <summary>
        /// 单独一个方法：`Bentley.Transform` 这个非托管类型到底能不能在 C# 里命名。
        /// 如果能，SetTransform / SyncTransform / GetTransform / GetOrigin 就可以直接调。
        /// 这个方法能否编译，就是答案。
        /// </summary>
        internal static unsafe void TouchNativeTransform(BMECObject obj)
        {
            Bentley.Transform native = default(Bentley.Transform);
            obj.GetTransform(&native);
            obj.SetTransform(&native);
            obj.SyncTransform(&native);
            Bentley.DPoint3d origin;
            obj.GetOrigin(&origin);
            Console.WriteLine(origin.X);
        }
    }
}
