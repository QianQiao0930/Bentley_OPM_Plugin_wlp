// API 探针：只用于编译期验证「C# 到底能消费 Bentley.OpenPlant.Modeler.Api 的哪些成员」。
// Bentley.OpenPlant.Modeler.Api.dll 是混合模式（C++/CLI）程序集，公开签名里混有原生指针类型
// （Bentley.DgnPlatform.EditElementHandle* 之类），C# 无法命名这些类型。
// 本文件不做任何运行逻辑，只把候选 API 逐个写出来，让编译器回答"能不能用"。
//
// 用法：dotnet build Development/ApiProbe/ApiProbe.csproj -c Release
// 结论（哪些成员可用 / 哪些不可用）记录在同目录 README.md。

using System;
using System.Collections.Generic;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace PipeAlignApiProbe
{
    internal static class Probe
    {
        internal static void Touch(IECInstance instance)
        {
            // ---- 构造：只看托管重载 ----
            BMECObject obj = new BMECObject(instance);

            // ---- 位置读取 / 写入（托管重载）----
            DTransform3d t = obj.Transform3d;
            obj.Transform3d = t;
            DPoint3d p0 = obj.GetNthPoint(0);
            DPoint3d p1 = obj.GetNthPoint(1);
            obj.SetLinearPoints(p0, p1);

            // ---- 状态与拓扑 ----
            bool valid = obj.IsValid;
            bool readOnly = obj.IsReadOnly;
            string className = obj.ClassName;
            List<BMECObject> connected = obj.ConnectedComponents;
            List<Bentley.Building.Mechanical.Components.Port> ports = obj.Ports;
            IECInstance ec = obj.Instance;

            // ---- 刷新 / 撤销 ----
            obj.Refresh();
            obj.Resync();
            obj.InitTransform();
            obj.UpdateTransform();
            obj.CreateMark();
            obj.Undo();
            obj.ClearMark();

            // ---- 全局 API ----
            BMECApi api = BMECApi.Instance;
            api.StartUndoGroup();
            api.EndUndoGroup();
            api.SaveAndCleanUpUndo();

            // ---- SDK 辅助 ----
            Bentley.OpenPlantModeler.SDK.Utilities.SchemaUtilities.IsPipingComponent(instance);
            Bentley.OpenPlantModeler.SDK.Utilities.SchemaUtilities.IsComponentOfType(instance, "PIPE");
            ECInstanceList allPipes = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities
                .GetInstancesFromDgn("PIPE");
            double uorPerSub = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities
                .GetUORPerSubForCurrentDgn();

            Console.WriteLine(valid && !readOnly && className != null && connected != null
                && ports != null && ec != null && allPipes != null && uorPerSub > 0 && api != null);
        }
    }
}
