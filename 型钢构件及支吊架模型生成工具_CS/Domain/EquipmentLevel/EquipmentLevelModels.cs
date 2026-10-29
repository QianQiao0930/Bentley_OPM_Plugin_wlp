using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>
    /// 选中元素在"设备图层批量修改"里的判定结果。
    /// <para>
    /// 本功能只处理 <b>设备</b>：普通单元（NormalCell），且 EC 属性
    /// <c>DgnElementSchema.NormalCellElement.ElementType</c> 的值为 <c>Equipment</c>。
    /// 管道、管件、支吊架、参考文件、共享/参数化单元根不作为设备入口。
    /// 普通设备内部的共享单元通过实例层色覆盖处理，不改公共定义。
    /// </para>
    /// </summary>
    internal enum EquipmentLevelVerdict
    {
        /// <summary>普通单元且 ElementType 为 Equipment，可以处理。</summary>
        Equipment = 0,

        /// <summary>不是单元（直线、实体、文字等）。</summary>
        NotACell = 1,

        /// <summary>是单元，但 EC 属性 ElementType 不是 Equipment。</summary>
        NotEquipment = 2,

        /// <summary>元素位于参考文件，不能在活动模型里修改。</summary>
        FromReference = 3,

        /// <summary>元素在模型里已经不存在。</summary>
        Missing = 4,

        /// <summary>共享单元或参数化单元，本版本明确不处理。</summary>
        UnsupportedCell = 5
    }

    /// <summary>单个选中元素的判定结果。</summary>
    internal sealed class EquipmentLevelEntry
    {
        internal ulong ElementId;
        internal string Name = string.Empty;
        internal EquipmentLevelVerdict Verdict;
        internal string Reason = string.Empty;
    }

    /// <summary>一次批量改层的结果。</summary>
    internal sealed class EquipmentLevelReport
    {
        /// <summary>目标图层名。</summary>
        internal string TargetLevelName = string.Empty;

        /// <summary>判定为设备并参与处理的台数。</summary>
        internal int EquipmentCount;

        /// <summary>必须通过图层、颜色双重校验的图形数，不含可选的容器单元头。</summary>
        internal int PlannedElementCount;

        /// <summary>修改前不符合、修改后通过校验的唯一图形数。</summary>
        internal int ChangedElementCount;

        /// <summary>从宿主重新读取并通过图层、颜色双重校验的图形数量。</summary>
        internal int VerifiedElementCount;

        /// <summary>修改前已经满足所选图层和颜色条件的图形数量。</summary>
        internal int AlreadyOnTargetCount;

        /// <summary>被拒绝的选中元素数。</summary>
        internal int RejectedCount;

        /// <summary>属性未统一的容器单元头数量（内部图形已通过图层和颜色校验）。</summary>
        internal int ContainersNotChanged;

        /// <summary>是否成功；失败时回滚结果须看 Summary，不能假定回滚成功。</summary>
        internal bool Succeeded;

        /// <summary>一句话结论，用于状态栏。</summary>
        internal string Summary = string.Empty;

        /// <summary>失败原因；成功时为空。</summary>
        internal string Failure = string.Empty;

        /// <summary>实际使用的读取/写入方式。</summary>
        internal string Method = string.Empty;

        /// <summary>逐台设备的明细文字。</summary>
        internal readonly List<string> Details = new List<string>();

        /// <summary>写入过程中遇到的问题（已限长）。</summary>
        internal readonly List<string> Problems = new List<string>();
    }
}
