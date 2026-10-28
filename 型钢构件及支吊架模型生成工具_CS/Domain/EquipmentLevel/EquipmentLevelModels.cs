using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>
    /// 选中元素在"设备图层批量修改"里的判定结果。
    /// <para>
    /// 本功能只处理 <b>设备</b>：普通单元（NormalCell），且 EC 属性
    /// <c>DgnElementSchema.NormalCellElement.ElementType</c> 的值为 <c>Equipment</c>。
    /// 管道、管件、支吊架、参考文件、共享单元与参数化单元一律不动。
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

        /// <summary>计划修改的图元数（写入前的快照）。</summary>
        internal int PlannedElementCount;

        /// <summary>实际写入并校验通过的图元数。</summary>
        internal int ChangedElementCount;

        /// <summary>被拒绝的选中元素数。</summary>
        internal int RejectedCount;

        /// <summary>是否成功；失败时模型已回滚。</summary>
        internal bool Succeeded;

        /// <summary>一句话结论，用于状态栏。</summary>
        internal string Summary = string.Empty;

        /// <summary>失败原因；成功时为空。</summary>
        internal string Failure = string.Empty;

        /// <summary>实际生效的写入方式（逐个子元素 / 整台单元），用于沉淀宿主行为。</summary>
        internal string Method = string.Empty;

        /// <summary>逐台设备的明细文字。</summary>
        internal readonly List<string> Details = new List<string>();

        /// <summary>写入过程中遇到的问题（已限长）。</summary>
        internal readonly List<string> Problems = new List<string>();
    }
}
