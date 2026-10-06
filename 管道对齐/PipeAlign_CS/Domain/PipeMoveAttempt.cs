using System.Collections.Generic;
using System.Globalization;

namespace PipeAlign
{
    /// <summary>
    /// 一次管道移动尝试的结果（开发指南 §18 的三级策略、§19 的禁止做法）。
    /// </summary>
    internal sealed class PipeMoveAttempt
    {
        /// <summary>接口调用是否成功（**不代表已复核**，复核由 <c>PipeMoveService</c> 负责）。</summary>
        internal bool Succeeded { get; set; }

        /// <summary>实际使用的层级代号（Level 1 / 2 / 3 与中文说明）。</summary>
        internal string Level { get; set; }

        /// <summary>失败原因（中文，直接给用户看）。</summary>
        internal string FailureReason { get; set; }

        /// <summary>逐级尝试的过程记录（进日志，便于在 OPM 里定位到底哪一级不生效）。</summary>
        internal List<string> Traces { get; private set; }

        /// <summary>本次是否只改了 DGN 图形（指南 §19 明确禁止作为正式实现）。</summary>
        internal bool GraphicsOnly { get; set; }

        internal PipeMoveAttempt()
        {
            Traces = new List<string>();
        }

        internal void Trace(string message)
        {
            if (!string.IsNullOrEmpty(message)) Traces.Add(message);
        }

        internal static PipeMoveAttempt Fail(string reason, IEnumerable<string> traces)
        {
            PipeMoveAttempt attempt = new PipeMoveAttempt();
            attempt.Succeeded = false;
            attempt.FailureReason = reason;
            if (traces != null) attempt.Traces.AddRange(traces);
            return attempt;
        }

        internal string Describe()
        {
            if (Succeeded) return "成功（" + Level + "）";
            return "失败（" + FailureReason + "）";
        }

        internal string DescribeTraces()
        {
            if (Traces.Count == 0) return "（无尝试记录）";
            return string.Join("；", Traces.ToArray());
        }
    }

    /// <summary>三级修改策略的层级定义（开发指南 §18）。</summary>
    internal enum PipeMoveLevel
    {
        /// <summary>Level 1：用 OpenPlant SDK 的业务对象接口改位置（按管轴端点）。推荐。</summary>
        ObjectLinearPoints = 1,

        /// <summary>Level 2：用 OpenPlant SDK 改对象变换信息，随后执行 OpenPlant 更新。</summary>
        ObjectTransform = 2,

        /// <summary>
        /// Level 2b：直接改 EC 变换矩阵并 <c>WriteChanges()</c> 提交。
        /// <para>
        /// 实测（OPM 2024）表明 Level 1 / 2 只改**内存副本**：改动进去后
        /// <c>Refresh</c> 一读回就没了，数据模型里始终是旧值。而"写 EC 值之后必须
        /// <c>WriteChanges()</c>"是本仓库另一侧（ItemType 写入）踩过的同一个坑。
        /// </para>
        /// <para>
        /// 它与 Level 2 **必须是两级、不能合成一条链**：合成之后若 Level 2 其实已经写成功，
        /// 后面的直写会把位移**叠加两次**。分成两级、中间隔着复核与回退，结构上就不可能叠加。
        /// </para>
        /// </summary>
        ObjectEcTransform = 4,

        /// <summary>Level 3：DGN 图形变换。只有验证 OpenPlant 数据同步后才能用。</summary>
        GraphicsTransform = 3
    }

    internal static class PipeMoveLevels
    {
        internal static string Chinese(PipeMoveLevel level)
        {
            switch (level)
            {
                case PipeMoveLevel.ObjectLinearPoints: return "Level 1 · OpenPlant 对象管轴端点";
                case PipeMoveLevel.ObjectTransform: return "Level 2 · OpenPlant 对象变换";
                case PipeMoveLevel.ObjectEcTransform: return "Level 2b · 直接提交 EC 变换";
                default: return "Level 3 · DGN 图形变换";
            }
        }

        internal static string Code(PipeMoveLevel level)
        {
            if (level == PipeMoveLevel.ObjectEcTransform) return "L2b";
            return "L" + ((int)level).ToString(CultureInfo.InvariantCulture);
        }
    }
}
