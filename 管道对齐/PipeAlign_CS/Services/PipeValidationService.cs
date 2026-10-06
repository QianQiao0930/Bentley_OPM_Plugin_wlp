using System;
using System.Collections.Generic;
using System.Globalization;

namespace PipeAlign
{
    /// <summary>校验结论：通过 / 不通过 + 中文原因。</summary>
    internal sealed class ValidationOutcome
    {
        private ValidationOutcome(bool isValid, string reason)
        {
            IsValid = isValid;
            Reason = reason;
        }

        internal bool IsValid { get; private set; }

        /// <summary>不通过的原因（中文，直接展示给用户）。通过时为 <c>null</c>。</summary>
        internal string Reason { get; private set; }

        internal static ValidationOutcome Valid()
        {
            return new ValidationOutcome(true, null);
        }

        internal static ValidationOutcome Invalid(string reason)
        {
            return new ValidationOutcome(false, reason);
        }
    }

    /// <summary>
    /// 管道校验（开发指南 §11、§12、§14、§15、§21、§22、§27）。
    /// <para>
    /// 所有判定都建立在一份**已读取完成的 <see cref="PipeInfo"/> 快照**上，不再回元素读 EC
    /// —— 这既是指南 §37 的性能要求，也避免 Bentley 实例跨回调失效导致崩溃。
    /// </para>
    /// </summary>
    internal static class PipeValidationService
    {
        /// <summary>
        /// 校验基准管（指南 §14）：必须有中心线、必须是水平直管、必须有可用外径。
        /// </summary>
        internal static ValidationOutcome ValidateReferencePipe(PipeInfo pipe, SurfaceMode surfaceMode,
            PipeAlignOptions options)
        {
            if (pipe == null) return ValidationOutcome.Invalid("尚未选择基准管。");
            ValidationOutcome basic = ValidateCommon(pipe, options);
            if (!basic.IsValid) return basic;

            if (!pipe.HasOutsideDiameter)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "基准管 {0} 没有外径（OUTSIDE_DIAMETER），无法计算管底 / 管顶标高。",
                    pipe.DisplayName));

            if (surfaceMode == SurfaceMode.Insulation && pipe.LacksInsulationThickness)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "基准管 {0} 没有保温厚度（INSULATION_THICKNESS），无法按保温层外表面计算。",
                    pipe.DisplayName));

            return ValidationOutcome.Valid();
        }

        /// <summary>
        /// 校验目标管（指南 §15、§27 第 3～8 步）。
        /// </summary>
        internal static ValidationOutcome ValidateTargetPipe(PipeInfo pipe, AlignmentMode mode,
            SurfaceMode surfaceMode, PipeAlignOptions options)
        {
            if (pipe == null) return ValidationOutcome.Invalid("对象为空。");
            ValidationOutcome basic = ValidateCommon(pipe, options);
            if (!basic.IsValid) return basic;

            // Center 模式只比较中心线，不需要外径；Bottom / Top 必须要有外径。
            if (mode != AlignmentMode.Center && !pipe.HasOutsideDiameter)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 没有外径（OUTSIDE_DIAMETER），无法计算管底 / 管顶标高。",
                    pipe.DisplayName));

            if (surfaceMode == SurfaceMode.Insulation && pipe.LacksInsulationThickness)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 没有保温厚度（INSULATION_THICKNESS），无法按保温层外表面计算。",
                    pipe.DisplayName));

            return ValidationOutcome.Valid();
        }

        /// <summary>与模式无关的公共校验：类型、中心线、水平、可写性。</summary>
        private static ValidationOutcome ValidateCommon(PipeInfo pipe, PipeAlignOptions options)
        {
            // 指南 §2.1：必须确认对象属于 PIPE 类或其有效派生类。
            // ⚠️ 不能只判"类名里含 PIPE"：OpenPlant 里 PIPE_ELBOW / PIPE_TEE / PIPE_FLANGE /
            // PIPE_VALVE / PIPE_REDUCER / PIPE_OLET / PIPE_COUPLING 都是**兄弟类**而不是 PIPE 的派生类，
            // 它们的类名同样含 PIPE。用连接对象分类器把这类构件认出来并明确拒绝，
            // 否则"点了一个弯头"会被当成直管、按弯头的一条腿去算标高。
            PipeConnectionKind kind = PipeConnectionClassifier.Classify(pipe.ClassName);
            if (kind != PipeConnectionKind.Pipe)
            {
                string kindText = PipeConnectionClassifier.Chinese(kind);
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 不是直管（EC 类为 {1}{2}），本命令只处理水平直管。",
                    pipe.DisplayName,
                    string.IsNullOrEmpty(pipe.ClassName) ? "未知" : pipe.ClassName,
                    string.IsNullOrEmpty(kindText) ? "" : "，" + kindText + "类构件"));
            }

            if (pipe.Axis == null)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 取不到中心线，无法确定标高。", pipe.DisplayName));

            if (pipe.Axis.IsDegenerate)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 的中心线长度为零，几何无效。", pipe.DisplayName));

            // 指南 §11 / §12：V1 只处理水平直管，斜管必须明确拒绝而不是用包围盒凑合。
            double tolerance = options == null ? 1.0 : options.HorizontalToleranceMm;
            if (!pipe.Axis.IsHorizontal(tolerance))
            {
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 不是水平管（中心线两端高差 {1:F3} mm，容差 {2:F3} mm），本次未移动该管道。",
                    pipe.DisplayName, pipe.Axis.DeltaZmm, tolerance));
            }

            if (pipe.IsFromReference)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 位于参考文件中，参考文件不可修改。", pipe.DisplayName));

            if (pipe.IsReadOnly)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 是只读元素，未移动。", pipe.DisplayName));

            if (pipe.IsLocked)
                return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                    "{0} 已被锁定，未移动。", pipe.DisplayName));

            return ValidationOutcome.Valid();
        }

        /// <summary>
        /// Safe Mode 拓扑校验（指南 §22）：目标管如果连到"本批不会一起移动的对象"，
        /// 就必须停止该管并说明原因，否则会产生隐藏断口。
        /// </summary>
        /// <param name="movingInstanceIds">本批要一起移动的 EC 实例 ID 集合。</param>
        /// <param name="checkMode">拓扑校验模式（指南 §21 Safe Mode 的严格程度）。</param>
        internal static ValidationOutcome ValidateTopology(PipeInfo pipe, ICollection<string> movingInstanceIds,
            PipeTopologyCheckMode checkMode)
        {
            if (pipe == null) return ValidationOutcome.Invalid("对象为空。");
            if (checkMode == PipeTopologyCheckMode.Off) return ValidationOutcome.Valid();

            PipeTopology topology = pipe.Topology;
            if (topology == null) return ValidationOutcome.Valid();

            if (!topology.IsKnown)
            {
                // 读不到连接关系时按"未知"处理。严格模式拒绝，其余模式放行。
                if (checkMode == PipeTopologyCheckMode.Strict)
                {
                    return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                        "{0} 的连接关系读取失败，无法确认移动是否安全，本次未移动该管道。{1}",
                        pipe.DisplayName,
                        string.IsNullOrEmpty(topology.ReadWarning) ? "" : "（" + topology.ReadWarning + "）"));
                }
                return ValidationOutcome.Valid();
            }

            if (!topology.HasConnection) return ValidationOutcome.Valid();

            PipeConnection blocking = topology.FindBlockingConnection(movingInstanceIds);
            if (blocking == null) return ValidationOutcome.Valid();

            string kind = PipeConnectionClassifier.Chinese(blocking.Kind);
            string port = blocking.PortIndex >= 0
                ? (blocking.PortIndex + 1).ToString(CultureInfo.InvariantCulture) + " 口"
                : "某口";
            return ValidationOutcome.Invalid(string.Format(CultureInfo.InvariantCulture,
                "{0} 存在固定连接（{1} 连接 {2}{3}），本次未移动该管道。",
                pipe.DisplayName, port, blocking.DisplayName,
                string.IsNullOrEmpty(kind) ? "" : "（" + kind + "）"));
        }
    }
}
