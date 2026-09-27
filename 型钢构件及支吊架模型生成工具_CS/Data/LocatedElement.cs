using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>
    /// 定位回调上报的元素。
    /// <para>
    /// **ElementId 只在它自己所属文件的 ID 空间里有效**：活动文件与参考文件（reference）
    /// 各自维护自己的元素编号。所以点选结果必须连同 <see cref="ModelRef"/> 一起传下去，
    /// 否则按 ID 去活动模型里查不到参考元素 —— 这正是"点不到参考文件里的管道"的根因。
    /// </para>
    /// </summary>
    internal sealed class LocatedElement
    {
        /// <summary>元素所属的模型引用。用 <c>ModelRef.GetDgnModel()</c> 取回模型。</summary>
        internal DgnModelRef ModelRef;
        internal ulong ElementId;
        /// <summary>点击点（UOR）；只有需要"在点击处放置"的工具会填。</summary>
        internal double ClickX,ClickY,ClickZ;

        /// <summary>从定位回调拿到元素后立即构造（Bentley 的 Element 不宜带出回调）。</summary>
        internal static LocatedElement From(Element element)
        {
            if(element==null) return null;
            return new LocatedElement {
                ModelRef=element.DgnModelRef,
                ElementId=(ulong)element.ElementId
            };
        }

        /// <summary>该元素是否来自参考文件（不属于活动模型）。</summary>
        internal bool IsFromReference()
        {
            var model=ModelRef==null?null:ModelRef.GetDgnModel();
            var active=Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel();
            return model!=null && active!=null && !ReferenceEquals(model,active);
        }
    }
}
