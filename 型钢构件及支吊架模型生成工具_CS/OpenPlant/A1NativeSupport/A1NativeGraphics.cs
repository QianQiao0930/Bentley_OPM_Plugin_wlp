extern alias NativeOPM;
using System;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static class A1NativeGraphics
    {
        internal static unsafe void Create(BMECObject support, Element graphics, DTransform3d placement, Action<string> log, Action finish)
        {
            fixed (byte* handle = graphics.ElementHandle)
            {
                log("阶段=绑定A1非参数化几何");
                support.SetNonParametricElement((NativeOPM::Bentley.DgnPlatform.EditElementHandle*)handle);
                int status = support.Create();
                log("阶段=Create；返回=" + status + "；实例=" + support.Instance.InstanceId + "; DeferCommits=" + BMECApi.Instance.DeferCommits);
                if (status != 0) throw new InvalidOperationException("原生支吊架Create失败：" + status);
                support.Transform3d = placement;
                if (!new BMECObjectWriter(support).Serialize())
                    throw new InvalidOperationException("A1原生几何写入失败。");
                log("阶段=几何及位置序列化完成；实例=" + support.Instance.InstanceId);
                // Keep the native edit handle pinned through all subsequent serialization.
                finish();
            }
        }
    }
}
