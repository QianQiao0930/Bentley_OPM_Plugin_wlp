using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace PipeAlign
{
    /// <summary>单根管道的执行结果。</summary>
    internal enum MoveOutcome
    {
        /// <summary>已成功移动。</summary>
        Moved = 0,

        /// <summary>本来就对齐，未移动。</summary>
        AlreadyAligned = 1,

        /// <summary>校验不通过，已跳过。</summary>
        Skipped = 2,

        /// <summary>移动失败（已回滚或已停止后续操作）。</summary>
        Failed = 3
    }

    /// <summary>
    /// 单根管道的执行结果，含开发指南 §29 要求的错误恢复数据
    /// （元素 ID、原中心标高、目标中心标高、ΔZ、对齐模式）。
    /// </summary>
    internal sealed class AlignmentItemResult
    {
        internal ulong ElementId { get; set; }

        internal string PipeName { get; set; }

        internal MoveOutcome Outcome { get; set; }

        internal double OriginalCenterElevationMm { get; set; }

        internal double TargetCenterElevationMm { get; set; }

        internal double DeltaZmm { get; set; }

        internal AlignmentMode Mode { get; set; }

        /// <summary>实际使用的修改层级（OpenPlant 对象 / 变换 / 图形变换），供日志与排查。</summary>
        internal string AppliedLevel { get; set; }

        /// <summary>针对用户的中文说明（失败原因、跳过原因）。</summary>
        internal string Message { get; set; }

        internal string Describe()
        {
            switch (Outcome)
            {
                case MoveOutcome.Moved:
                    return string.Format(CultureInfo.InvariantCulture,
                        "{0}：已移动 ΔZ = {1:+0.0;-0.0;0.0} mm（原 {2:F1} → 新 {3:F1}，{4}）",
                        PipeName, DeltaZmm, OriginalCenterElevationMm, TargetCenterElevationMm,
                        AppliedLevel);
                case MoveOutcome.AlreadyAligned:
                    return string.Format(CultureInfo.InvariantCulture,
                        "{0}：已对齐，未移动", PipeName);
                case MoveOutcome.Skipped:
                    return string.Format(CultureInfo.InvariantCulture,
                        "{0}：已跳过 —— {1}", PipeName, Message);
                default:
                    return string.Format(CultureInfo.InvariantCulture,
                        "{0}：移动失败 —— {1}", PipeName, Message);
            }
        }
    }

    /// <summary>整批操作的结果，用于状态栏、Message Center 与日志（开发指南 §30）。</summary>
    internal sealed class AlignmentResult
    {
        private readonly List<AlignmentItemResult> _items = new List<AlignmentItemResult>();

        internal AlignmentResult(AlignmentPlan plan)
        {
            Plan = plan;
        }

        internal AlignmentPlan Plan { get; private set; }

        internal IList<AlignmentItemResult> Items { get { return _items; } }

        /// <summary>是否因为失败而停了后续修改（指南 §29：修改失败必须停止后续修改）。</summary>
        internal bool StoppedEarly { get; set; }

        /// <summary>是否执行了事务回滚。</summary>
        internal bool RolledBack { get; set; }

        /// <summary>整批操作失败时的总体原因。</summary>
        internal string FailureMessage { get; set; }

        internal void Add(AlignmentItemResult item)
        {
            if (item != null) _items.Add(item);
        }

        internal int MovedCount { get { return Count(MoveOutcome.Moved); } }
        internal int SkippedCount { get { return Count(MoveOutcome.Skipped); } }
        internal int FailedCount { get { return Count(MoveOutcome.Failed); } }
        internal int AlreadyAlignedCount { get { return Count(MoveOutcome.AlreadyAligned); } }

        private int Count(MoveOutcome outcome)
        {
            int count = 0;
            foreach (AlignmentItemResult item in _items)
                if (item.Outcome == outcome) count++;
            return count;
        }

        /// <summary>开发指南 §30 的正式日志格式（短，不刷屏）。</summary>
        internal string BuildLog()
        {
            StringBuilder builder = new StringBuilder();
            builder.AppendLine("PipeAlign started.");
            if (Plan != null && Plan.ReferencePipe != null)
                builder.AppendLine("Reference pipe: " + Plan.ReferencePipe.DisplayName + ".");
            if (Plan != null)
            {
                builder.AppendLine("Alignment mode: " + AlignmentModes.Code(Plan.Mode) + ".");
                builder.AppendLine("Surface mode: " + SurfaceModes.Code(Plan.SurfaceMode) + ".");
                builder.AppendLine("Reference elevation: "
                    + Plan.ReferenceElevationMm.ToString("F3", CultureInfo.InvariantCulture) + " mm.");
                builder.AppendLine("Target pipes: " + Plan.Items.Count.ToString(CultureInfo.InvariantCulture) + ".");
            }
            builder.AppendLine("Moved pipes: " + MovedCount.ToString(CultureInfo.InvariantCulture) + ".");
            builder.AppendLine("Already aligned: " + AlreadyAlignedCount.ToString(CultureInfo.InvariantCulture) + ".");
            builder.AppendLine("Skipped pipes: " + SkippedCount.ToString(CultureInfo.InvariantCulture) + ".");
            builder.AppendLine("Failed pipes: " + FailedCount.ToString(CultureInfo.InvariantCulture) + ".");
            if (RolledBack) builder.AppendLine("Transaction rolled back.");
            if (!string.IsNullOrEmpty(FailureMessage))
                builder.AppendLine("Failure: " + FailureMessage);
            return builder.ToString();
        }
    }
}
