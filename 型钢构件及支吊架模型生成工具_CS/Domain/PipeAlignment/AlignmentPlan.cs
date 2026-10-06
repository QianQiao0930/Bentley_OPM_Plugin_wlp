using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>单根目标管的计划状态。</summary>
    internal enum PlanItemStatus
    {
        /// <summary>可以移动。</summary>
        Ready = 0,

        /// <summary>已跳过（有明确原因）。</summary>
        Skipped = 1,

        /// <summary>已经对齐，位移为 0，不需要移动。</summary>
        AlreadyAligned = 2
    }

    /// <summary>
    /// 单根目标管的对齐计划（纯计算产物，不涉及任何 Bentley 调用）。
    /// </summary>
    internal sealed class AlignmentPlanItem
    {
        internal AlignmentPlanItem(PipeInfo pipe, AlignmentMode mode, SurfaceMode surfaceMode)
        {
            Pipe = pipe;
            Mode = mode;
            SurfaceMode = surfaceMode;
            Status = PlanItemStatus.Ready;
        }

        internal PipeInfo Pipe { get; private set; }

        internal AlignmentMode Mode { get; private set; }

        internal SurfaceMode SurfaceMode { get; private set; }

        internal PlanItemStatus Status { get; set; }

        /// <summary>跳过原因（中文，直接展示给用户）。</summary>
        internal string SkipReason { get; set; }

        /// <summary>目标管当前的对齐标高（mm）。</summary>
        internal double CurrentElevationMm { get; set; }

        /// <summary>基准管的对齐标高（mm），即目标管要对齐到的标高。</summary>
        internal double ReferenceElevationMm { get; set; }

        /// <summary>位移 ΔZ = 基准标高 − 目标标高（mm）。</summary>
        internal double DeltaZmm { get; set; }

        /// <summary>该管使用的外径 Do（mm）。</summary>
        internal double OutsideDiameterMm { get; set; }

        /// <summary>
        /// 该管是不是 Move Group 沿连接关系**自动带进来**的（不是用户直接选中的）。
        /// <para>报告里要能区分"你选的"和"为了不断口一起拖走的"，否则用户会困惑于行数变多。</para>
        /// </summary>
        internal bool AddedByGroup { get; set; }

        internal PipeAxis AdjustedAxis { get; set; }
        internal bool IsStretch { get { return AdjustedAxis != null; } }

        /// <summary>该管使用的有效外径 Deff（mm）。</summary>
        internal double EffectiveDiameterMm { get; set; }

        /// <summary>移动后的中心线（预览与移动都用它）。</summary>
        internal PipeAxis TargetAxis
        {
            get
            {
                if (Pipe == null || Pipe.Axis == null) return null;
                return AdjustedAxis ?? Pipe.Axis.ShiftedByZ(DeltaZmm);
            }
        }

        internal bool WillMove
        {
            get { return Status == PlanItemStatus.Ready; }
        }

        /// <summary>一行中文摘要（预览表、日志共用）。</summary>
        internal string Describe()
        {
            if (Status == PlanItemStatus.Skipped)
                return string.Format(CultureInfo.InvariantCulture, "{0}：已跳过 —— {1}",
                    Pipe == null ? "?" : Pipe.DisplayName, SkipReason);
            return string.Format(CultureInfo.InvariantCulture,
                "{0}：当前 {1:F1}，目标 {2:F1}，ΔZ = {3:+0.0;-0.0;0.0} mm",
                Pipe == null ? "?" : Pipe.DisplayName,
                CurrentElevationMm, ReferenceElevationMm, DeltaZmm);
        }
    }

    /// <summary>
    /// 对齐计划：基准标高 + 每根目标管的位移与跳过原因（开发指南 §25 的预览数据源）。
    /// </summary>
    internal sealed class AlignmentPlan
    {
        private readonly List<AlignmentPlanItem> _items = new List<AlignmentPlanItem>();

        internal AlignmentPlan(PipeInfo referencePipe, AlignmentMode mode, SurfaceMode surfaceMode,
            double referenceElevationMm)
        {
            ReferencePipe = referencePipe;
            Mode = mode;
            SurfaceMode = surfaceMode;
            ReferenceElevationMm = referenceElevationMm;
        }

        internal PipeInfo ReferencePipe { get; private set; }

        internal AlignmentMode Mode { get; private set; }

        internal SurfaceMode SurfaceMode { get; private set; }

        /// <summary>基准管的对齐标高（mm）。</summary>
        internal double ReferenceElevationMm { get; private set; }

        internal IList<AlignmentPlanItem> Items { get { return _items; } }
        internal IList<PipeInfo> FixedPipes { get; private set; } = new List<PipeInfo>();
        internal bool IsZStretch { get; set; }

        internal void Add(AlignmentPlanItem item)
        {
            if (item != null) _items.Add(item);
        }

        internal int ReadyCount
        {
            get
            {
                int count = 0;
                foreach (AlignmentPlanItem item in _items)
                    if (item.Status == PlanItemStatus.Ready) count++;
                return count;
            }
        }

        internal int SkippedCount
        {
            get
            {
                int count = 0;
                foreach (AlignmentPlanItem item in _items)
                    if (item.Status == PlanItemStatus.Skipped) count++;
                return count;
            }
        }

        internal int AlreadyAlignedCount
        {
            get
            {
                int count = 0;
                foreach (AlignmentPlanItem item in _items)
                    if (item.Status == PlanItemStatus.AlreadyAligned) count++;
                return count;
            }
        }

        /// <summary>
        /// 本批要移动的 EC 实例 ID 集合（Safe Mode 的拓扑判定用它）。
        /// <para>用实例 ID 而不是元素 ID：OpenPlant 的连接关系建立在实例之间，见 <see cref="PipeConnection"/>。</para>
        /// </summary>
        internal List<string> ReadyInstanceIds()
        {
            List<string> ids = new List<string>();
            foreach (AlignmentPlanItem item in _items)
            {
                if (item.Status != PlanItemStatus.Ready || item.Pipe == null) continue;
                if (string.IsNullOrEmpty(item.Pipe.InstanceId)) continue;
                ids.Add(item.Pipe.InstanceId);
            }
            return ids;
        }
    }
}
