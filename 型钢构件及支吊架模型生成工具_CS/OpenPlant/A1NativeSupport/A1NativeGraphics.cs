extern alias NativeOPM;
using System;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static class A1NativeGraphics
    {
        internal static unsafe void Create(BMECObject support, Element graphics, DTransform3d placement, Action finish)
        {
            fixed (byte* handle = graphics.ElementHandle)
            {
                support.SetNonParametricElement((NativeOPM::Bentley.DgnPlatform.EditElementHandle*)handle);
                int status = support.Create();
                if (status != 0) throw new InvalidOperationException("原生支吊架Create失败：" + status);
                support.Transform3d = placement;
                if (!new BMECObjectWriter(support).Serialize())
                    throw new InvalidOperationException("A1原生几何写入失败。");
                // Keep the native edit handle pinned through all subsequent serialization.
                finish();
            }
        }
    }
}
