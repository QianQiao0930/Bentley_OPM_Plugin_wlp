using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace PipeAlign
{
    /// <summary>
    /// Move Group 的成员策略（开发指南 §23、§24）。
    /// <para>
    /// 沿连接关系展开整组时，每个遇到的对象按**类别**分成三种角色：
    /// </para>
    /// <list type="bullet">
    /// <item><description><b>可一起移动</b>：收进组里，用同一个 ΔZ 平移；</description></item>
    /// <item><description><b>边界</b>：不移动它，而且**整组拒绝** —— 等量平移必然在它那里产生断口（指南 §24）；</description></item>
    /// <item><description><b>未知</b>：默认当边界处理。宁可拒绝，也不要把不认识的构件拖着走。</description></item>
    /// </list>
    /// <para>
    /// 类别判定复用 <see cref="PipeConnectionClassifier"/> 的关键字表，所以全工程只有一份
    /// "类名 → 类别"的规则，不会两处漂移。
    /// </para>
    /// </summary>
    internal sealed class MoveGroupPolicy
    {
        /// <summary>可以一起平移的类别。</summary>
        internal PipeConnectionKind[] MovableKinds { get; private set; }

        /// <summary>视为边界、遇到即拒绝整组的类别。</summary>
        internal PipeConnectionKind[] BoundaryKinds { get; private set; }

        private MoveGroupPolicy(PipeConnectionKind[] movable, PipeConnectionKind[] boundary)
        {
            MovableKinds = movable;
            BoundaryKinds = boundary;
        }

        /// <summary>
        /// 默认策略：移动"管道 + 管件 + 法兰类 + 阀门"，在"设备管口 / 仪表 / 支吊架 / 未知类"处停下。
        /// <para>
        /// 支吊架默认**不**跟着走：管道挪了、支吊架跟着挪，等于把它从结构生根处拽下来。
        /// 项目若确认这里的支吊架应该随管移动，把配置项
        /// <c>MoveGroupMovableKinds</c> 加上 <c>SUPPORT</c> 即可。
        /// </para>
        /// </summary>
        internal static MoveGroupPolicy Default()
        {
            return new MoveGroupPolicy(
                new[]
                {
                    PipeConnectionKind.Pipe,
                    PipeConnectionKind.Fitting,
                    PipeConnectionKind.Flange,
                    PipeConnectionKind.Valve
                },
                new[]
                {
                    PipeConnectionKind.EquipmentNozzle,
                    PipeConnectionKind.Instrument,
                    PipeConnectionKind.Support,
                    PipeConnectionKind.Unknown
                });
        }

        /// <summary>用逗号分隔的类别名构造（配置项用）。无法识别的名字会被忽略。</summary>
        internal static MoveGroupPolicy Parse(string movableText, string boundaryText)
        {
            MoveGroupPolicy fallback = Default();
            PipeConnectionKind[] movable = ParseKinds(movableText);
            PipeConnectionKind[] boundary = ParseKinds(boundaryText);
            if (movable.Length == 0) movable = fallback.MovableKinds;
            if (boundary.Length == 0) boundary = fallback.BoundaryKinds;
            return new MoveGroupPolicy(movable, boundary);
        }

        private static PipeConnectionKind[] ParseKinds(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return new PipeConnectionKind[0];
            List<PipeConnectionKind> kinds = new List<PipeConnectionKind>();
            string[] parts = text.Split(new[] { ',', '，', ';', '；', ' ' },
                StringSplitOptions.RemoveEmptyEntries);
            foreach (string part in parts)
            {
                PipeConnectionKind kind;
                if (!TryParseKind(part.Trim(), out kind)) continue;
                if (!kinds.Contains(kind)) kinds.Add(kind);
            }
            return kinds.ToArray();
        }

        internal static bool TryParseKind(string text, out PipeConnectionKind kind)
        {
            kind = PipeConnectionKind.Unknown;
            if (string.IsNullOrWhiteSpace(text)) return false;
            switch (text.Trim().ToUpperInvariant())
            {
                case "PIPE": kind = PipeConnectionKind.Pipe; return true;
                case "FITTING":
                case "ELBOW":
                case "TEE":
                case "REDUCER": kind = PipeConnectionKind.Fitting; return true;
                case "FLANGE": kind = PipeConnectionKind.Flange; return true;
                case "VALVE": kind = PipeConnectionKind.Valve; return true;
                case "NOZZLE":
                case "EQUIPMENTNOZZLE": kind = PipeConnectionKind.EquipmentNozzle; return true;
                case "SUPPORT": kind = PipeConnectionKind.Support; return true;
                case "INSTRUMENT": kind = PipeConnectionKind.Instrument; return true;
                case "UNKNOWN": kind = PipeConnectionKind.Unknown; return true;
                default: return false;
            }
        }

        /// <summary>判定某个连接对象的类别在某组里是否存在。</summary>
        internal bool IsMovable(PipeConnectionKind kind)
        {
            return Array.IndexOf(MovableKinds, kind) >= 0;
        }

        internal bool IsBoundary(PipeConnectionKind kind)
        {
            return Array.IndexOf(BoundaryKinds, kind) >= 0;
        }

        /// <summary>按类名判定角色：<c>true</c> = 可一起移动。</summary>
        internal bool IsMovableClass(string className)
        {
            return IsMovable(PipeConnectionClassifier.Classify(className));
        }

        /// <summary>配置项用的类别名列表（写回配置文件时用）。</summary>
        internal static string FormatKinds(PipeConnectionKind[] kinds)
        {
            if (kinds == null || kinds.Length == 0) return string.Empty;
            StringBuilder builder = new StringBuilder();
            for (int index = 0; index < kinds.Length; index++)
            {
                if (index > 0) builder.Append(',');
                builder.Append(KindCode(kinds[index]));
            }
            return builder.ToString();
        }

        internal static string KindCode(PipeConnectionKind kind)
        {
            switch (kind)
            {
                case PipeConnectionKind.Pipe: return "PIPE";
                case PipeConnectionKind.Fitting: return "FITTING";
                case PipeConnectionKind.Flange: return "FLANGE";
                case PipeConnectionKind.Valve: return "VALVE";
                case PipeConnectionKind.EquipmentNozzle: return "NOZZLE";
                case PipeConnectionKind.Support: return "SUPPORT";
                case PipeConnectionKind.Instrument: return "INSTRUMENT";
                default: return "UNKNOWN";
            }
        }

        internal string DescribeMovable()
        {
            return Describe(MovableKinds);
        }

        internal string DescribeBoundary()
        {
            return Describe(BoundaryKinds);
        }

        private static string Describe(PipeConnectionKind[] kinds)
        {
            if (kinds == null || kinds.Length == 0) return "（无）";
            StringBuilder builder = new StringBuilder();
            for (int index = 0; index < kinds.Length; index++)
            {
                if (index > 0) builder.Append('、');
                string chinese = PipeConnectionClassifier.Chinese(kinds[index]);
                builder.Append(string.IsNullOrEmpty(chinese) ? KindCode(kinds[index]) : chinese);
            }
            return builder.ToString();
        }

        internal string Describe()
        {
            return string.Format(CultureInfo.InvariantCulture,
                "一起移动：{0}；边界：{1}", DescribeMovable(), DescribeBoundary());
        }
    }
}
