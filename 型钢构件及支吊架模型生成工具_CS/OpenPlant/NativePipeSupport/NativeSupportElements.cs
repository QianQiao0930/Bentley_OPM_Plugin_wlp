using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static class NativeSupportElements
    {
        internal static unsafe long ActiveModelToken()
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("请先打开活动三维模型。");
            return ((IntPtr)DgnModelRef.GetNativeDgnModelRefP(model, false)).ToInt64();
        }

        internal static unsafe Element Get(IECInstance instance, bool writable)
        {
            var api = BMECApi.Instance;
            var elementRef = api.GetElementRef(instance);
            if (elementRef == null) throw new InvalidOperationException("业务对象没有有效的图形元素。");
            var element = Element.GetFromElementRef((IntPtr)elementRef);
            var active = Session.Instance.GetActiveDgnModel();
            if (element == null || !element.IsValid || active == null || !active.Is3d
                || element.GetNativeDgnModelRef().ToInt64() != ActiveModelToken())
            {
                element?.Dispose();
                throw new InvalidOperationException("原生支吊架仅支持活动三维模型，不支持参考文件。");
            }
            if (writable && (element.IsEffectivelyLocked(true, true) || !api.IsInstanceModifiable(instance)))
            {
                element.Dispose();
                throw new InvalidOperationException("所选对象被锁定或不可写。");
            }
            return element;
        }
    }
}
