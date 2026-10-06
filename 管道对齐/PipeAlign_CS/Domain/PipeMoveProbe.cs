namespace PipeAlign
{
    /// <summary>
    /// 在**单个元素**上探测出来的"能不能改、怎么改"的结论（开发指南 §18、§40 Phase 1）。
    /// <para>
    /// 为什么要在运行时探测而不是写死常量：OpenPlant 的几何 API 返回 / 接受什么单位，
    /// 官方文档没有明确保证（<c>GetNthPoint</c> 的指针重载参数名是 <c>pPointInGlobalUors</c>，
    /// 但托管重载与 <c>Transform3d</c> 的平移分量是否同一个单位体系只能实测）。
    /// **猜错单位的后果不是失败而是把管道挪到几百米之外**，所以本插件坚持：
    /// 只用在这个元素上**已经被几何数据证实**的单位与接口；证实不了就拒绝移动并说明原因。
    /// </para>
    /// <para>纯数据，不持有任何 Bentley 对象。</para>
    /// </summary>
    internal sealed class PipeMoveProbe
    {
        /// <summary>每毫米多少 API 单位：毫米 → API 乘该值，API → 毫米除该值。</summary>
        internal double ApiUnitsPerMillimeter { get; set; }

        /// <summary>
        /// <c>BMECObject.GetNthPoint</c> / <c>SetLinearPoints</c> 这一对接口的单位已被证实，
        /// 可以用它按管轴两端点直接改位置（开发指南 §18 的 Level 1）。
        /// </summary>
        internal bool LinearPointsUsable { get; set; }

        /// <summary>
        /// <c>BMECObject.Transform3d</c> 的平移分量已被证实与几何一致，
        /// 可以用它整体沿 Z 平移（开发指南 §18 的 Level 2）。
        /// </summary>
        internal bool TransformUsable { get; set; }

        /// <summary>探测失败原因 / 过程说明（中文，进日志与提示）。</summary>
        internal string Detail { get; set; }

        /// <summary>有没有任何一级可用。</summary>
        internal bool AnyUsable
        {
            get { return LinearPointsUsable || TransformUsable; }
        }

        internal string Describe()
        {
            if (!AnyUsable) return "不可用（" + (Detail ?? "未探测") + "）";
            return string.Format(System.Globalization.CultureInfo.InvariantCulture,
                "{0} 单位/毫米；Level 1 管轴端点={1}；Level 2 变换={2}",
                ApiUnitsPerMillimeter,
                LinearPointsUsable ? "可用" : "不可用",
                TransformUsable ? "可用" : "不可用");
        }
    }
}
