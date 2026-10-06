using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace PipeAlign
{
    /// <summary>
    /// 定位回调上报的元素。
    /// <para>
    /// **ElementId 只在它自己所属文件的 ID 空间里有效**：活动文件与参考文件（reference）
    /// 各自维护自己的元素编号，所以点选结果必须连同 <see cref="ModelRef"/> 一起传下去。
    /// 否则按 ID 去活动模型里查会命中**另一个同号元素**（表现为"读出来的构件完全不对"），
    /// 或者干脆查不到。
    /// </para>
    /// <para>
    /// PipeAlign 的 V1 只允许改活动模型里的管道（参考文件永远不可编辑），但读取阶段仍要
    /// 正确区分两者，才能给出"该管道位于参考文件中"这句明确提示，而不是抛一个莫名的异常。
    /// </para>
    /// </summary>
    internal sealed class LocatedElement
    {
        internal DgnModelRef ModelRef;
        internal ulong ElementId;

        /// <summary>从定位回调拿到元素后立即构造（Bentley 的 Element 不宜带出回调）。</summary>
        internal static LocatedElement From(Element element)
        {
            if (element == null) return null;
            return new LocatedElement
            {
                ModelRef = element.DgnModelRef,
                ElementId = (ulong)element.ElementId
            };
        }

        internal bool IsFromReference()
        {
            return IsReference(ModelRef);
        }

        /// <summary>判断某个模型引用是不是参考文件（不是活动模型）。</summary>
        internal static bool IsReference(DgnModelRef modelRef)
        {
            var model = modelRef == null ? null : modelRef.GetDgnModel();
            var active = Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel();
            return model != null && active != null && !ReferenceEquals(model, active);
        }

        /// <summary>
        /// 判断任意元素是否来自参考文件。参考元素在 MicroStation 里默认不可定位
        /// （报"元素位于只读参考文件之中"），需要由 <c>OnPostLocate</c> 显式放行才能读到。
        /// </summary>
        internal static bool IsReference(Element element)
        {
            return element != null && IsReference(element.DgnModelRef);
        }
    }
}
