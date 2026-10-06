using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 插件运行参数（开发指南 §11：容差**必须写入配置，不得写死在业务代码中**）。
    /// <para>
    /// 配置以 <c>键=值</c> 文本保存，避免给纯计算层引入 JSON 依赖，也方便项目现场直接改。
    /// 读取与保存见 <see cref="PipeAlignOptionsStore"/>；本类型只负责默认值与解析（纯计算，可离线断言）。
    /// </para>
    /// </summary>
    internal sealed class PipeAlignOptions
    {
        /// <summary>水平判定容差（mm）。指南示例值 1 mm，项目可修改。</summary>
        internal double HorizontalToleranceMm { get; set; }

        /// <summary>
        /// 已对齐判定容差（mm）：位移的绝对值不大于该值即视为"本来就对齐，不移动"
        /// （开发指南 T05）。默认 0.001 mm —— 比任何工程标高精度都小。
        /// </summary>
        internal double AlignmentToleranceMm { get; set; }

        /// <summary>启动时的默认对齐模式（Key-in 未指定模式时使用）。</summary>
        internal AlignmentMode DefaultAlignmentMode { get; set; }

        /// <summary>启动时的默认表面模式。程序不得自动猜测，这里是**显式**的启动默认值。</summary>
        internal SurfaceMode DefaultSurfaceMode { get; set; }

        /// <summary>单次操作允许的最大目标管数量（防止误选整张图后长时间无响应）。</summary>
        internal int MaxTargetPipes { get; set; }

        /// <summary>
        /// 是否允许在 OpenPlant 对象接口失败时回落到 DGN 图形变换（指南 §18 Level 3）。
        /// <para>
        /// **默认关闭。** 只改图形会让 OpenPlant 数据与图形不一致（指南 §19），
        /// 打开它必须由用户明确承担风险。
        /// </para>
        /// </summary>
        internal bool AllowGraphicsTransformFallback { get; set; }

        /// <summary>是否把 EC 属性全量转储到 Message Center（指南 §30：只在 Debug 模式）。</summary>
        internal bool DumpEcProperties { get; set; }

        /// <summary>
        /// 拓扑校验严格程度（指南 §21）。默认 <see cref="PipeTopologyCheckMode.Strict"/> ——
        /// 连接关系读不到时拒绝移动，而不是悄悄放行。
        /// </summary>
        internal PipeTopologyCheckMode TopologyCheckMode { get; set; }

        /// <summary>移动范围（指南 §22 Safe Mode / §23 Move Group）。默认只移动选中的管道。</summary>
        internal MoveScope DefaultMoveScope { get; set; }

        /// <summary>Move Group 里允许一起平移的类别（逗号分隔的类别名）。</summary>
        internal string MoveGroupMovableKinds { get; set; }

        /// <summary>Move Group 里视为边界、遇到即拒绝整组的类别。</summary>
        internal string MoveGroupBoundaryKinds { get; set; }

        /// <summary>Move Group 一次最多展开多少个对象（防止沿连接关系把整张图都拖进来）。</summary>
        internal int MoveGroupMaxMembers { get; set; }
        internal double RouteEndpointToleranceMm { get; set; }
        internal double MinimumStretchLengthMm { get; set; }

        /// <summary>由当前配置构造 Move Group 成员策略。</summary>
        internal MoveGroupPolicy BuildGroupPolicy()
        {
            return MoveGroupPolicy.Parse(MoveGroupMovableKinds, MoveGroupBoundaryKinds);
        }

        internal PipeAlignOptions()
        {
            HorizontalToleranceMm = 1.0;
            AlignmentToleranceMm = 0.001;
            DefaultAlignmentMode = AlignmentMode.Bottom;
            DefaultSurfaceMode = SurfaceMode.Pipe;
            MaxTargetPipes = 200;
            AllowGraphicsTransformFallback = false;
            DumpEcProperties = false;
            TopologyCheckMode = PipeTopologyCheckMode.Strict;
            DefaultMoveScope = MoveScope.SelectedOnly;
            MoveGroupPolicy defaults = MoveGroupPolicy.Default();
            MoveGroupMovableKinds = MoveGroupPolicy.FormatKinds(defaults.MovableKinds);
            MoveGroupBoundaryKinds = MoveGroupPolicy.FormatKinds(defaults.BoundaryKinds);
            MoveGroupMaxMembers = 200;
            RouteEndpointToleranceMm = 1.0;
            MinimumStretchLengthMm = 10.0;
        }

        /// <summary>配置文件的默认文件名（放在 DLL 同目录或 <c>%LOCALAPPDATA%\PipeAlign\</c>）。</summary>
        internal const string FileName = "PipeAlign.options.txt";

        /// <summary>
        /// 解析配置文件文本。无法识别的行、无法解析的值一律**忽略并记入
        /// <paramref name="warnings"/>**，不抛异常 —— 配置写坏不能让插件打不开。
        /// </summary>
        internal static PipeAlignOptions Parse(string text, IList<string> warnings)
        {
            PipeAlignOptions options = new PipeAlignOptions();
            if (string.IsNullOrWhiteSpace(text)) return options;

            string[] lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            for (int index = 0; index < lines.Length; index++)
            {
                string line = lines[index];
                if (line == null) continue;
                string trimmed = line.Trim();
                if (trimmed.Length == 0) continue;
                if (trimmed.StartsWith("#", StringComparison.Ordinal)) continue;
                if (trimmed.StartsWith(";", StringComparison.Ordinal)) continue;

                int separator = trimmed.IndexOf('=');
                if (separator <= 0)
                {
                    Warn(warnings, index + 1, trimmed, "缺少 '='");
                    continue;
                }
                string key = trimmed.Substring(0, separator).Trim();
                string value = trimmed.Substring(separator + 1).Trim();
                Apply(options, key, value, index + 1, warnings);
            }
            return options;
        }

        private static void Apply(PipeAlignOptions options, string key, string value,
            int lineNumber, IList<string> warnings)
        {
            switch (key.ToLowerInvariant())
            {
                case "routeendpointtolerancemm":
                case "minimumstretchlengthmm":
                    double length;
                    if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out length)
                        && length > 0.0 && !double.IsInfinity(length) && !double.IsNaN(length))
                    {
                        if (key.Equals("routeendpointtolerancemm", StringComparison.OrdinalIgnoreCase))
                            options.RouteEndpointToleranceMm = length;
                        else options.MinimumStretchLengthMm = length;
                    }
                    else Warn(warnings, lineNumber, key, "需要有限的正数（mm）");
                    return;
                case "horizontaltolerancemm":
                case "horizontaltolerance":
                    {
                        double parsed;
                        if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out parsed)
                            && parsed >= 0.0 && !double.IsNaN(parsed) && !double.IsInfinity(parsed))
                            options.HorizontalToleranceMm = parsed;
                        else
                            Warn(warnings, lineNumber, key, "需要一个不小于 0 的数值（mm）");
                        return;
                    }
                case "alignmenttolerancemm":
                case "alignmenttolerance":
                    {
                        double parsed;
                        if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out parsed)
                            && parsed >= 0.0 && !double.IsNaN(parsed) && !double.IsInfinity(parsed))
                            options.AlignmentToleranceMm = parsed;
                        else
                            Warn(warnings, lineNumber, key, "需要一个不小于 0 的数值（mm）");
                        return;
                    }
                case "defaultalignmentmode":
                    {
                        AlignmentMode mode;
                        if (AlignmentModes.TryParse(value, out mode))
                            options.DefaultAlignmentMode = mode;
                        else
                            Warn(warnings, lineNumber, key, "可用 BOTTOM / CENTER / TOP");
                        return;
                    }
                case "defaultsurfacemode":
                    {
                        SurfaceMode mode;
                        if (SurfaceModes.TryParse(value, out mode))
                            options.DefaultSurfaceMode = mode;
                        else
                            Warn(warnings, lineNumber, key, "可用 PIPE / INSULATION");
                        return;
                    }
                case "maxtargetpipes":
                    {
                        int parsed;
                        if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed)
                            && parsed > 0)
                            options.MaxTargetPipes = parsed;
                        else
                            Warn(warnings, lineNumber, key, "需要一个正整数");
                        return;
                    }
                case "allowgraphicstransformfallback":
                    {
                        bool parsed;
                        if (TryParseBool(value, out parsed))
                            options.AllowGraphicsTransformFallback = parsed;
                        else
                            Warn(warnings, lineNumber, key, "可用 true / false");
                        return;
                    }
                case "movescope":
                case "defaultmovescope":
                    {
                        MoveScope parsed;
                        if (MoveScopes.TryParse(value, out parsed))
                            options.DefaultMoveScope = parsed;
                        else
                            Warn(warnings, lineNumber, key, "可用 SINGLE / GROUP");
                        return;
                    }
                case "movegroupmovablekinds":
                    options.MoveGroupMovableKinds = value;
                    return;
                case "movegroupboundarykinds":
                    options.MoveGroupBoundaryKinds = value;
                    return;
                case "movegroupmaxmembers":
                    {
                        int parsed;
                        if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed)
                            && parsed > 0)
                            options.MoveGroupMaxMembers = parsed;
                        else
                            Warn(warnings, lineNumber, key, "需要一个正整数");
                        return;
                    }
                case "topologycheckmode":
                    {
                        PipeTopologyCheckMode parsed;
                        if (PipeTopologyCheckModes.TryParse(value, out parsed))
                            options.TopologyCheckMode = parsed;
                        else
                            Warn(warnings, lineNumber, key, "可用 STRICT / BESTEFFORT / OFF");
                        return;
                    }
                case "dumpecproperties":
                    {
                        bool parsed;
                        if (TryParseBool(value, out parsed))
                            options.DumpEcProperties = parsed;
                        else
                            Warn(warnings, lineNumber, key, "可用 true / false");
                        return;
                    }
                default:
                    Warn(warnings, lineNumber, key, "未知配置项");
                    return;
            }
        }

        private static bool TryParseBool(string value, out bool result)
        {
            result = false;
            if (string.IsNullOrWhiteSpace(value)) return false;
            switch (value.Trim().ToLowerInvariant())
            {
                case "true":
                case "1":
                case "yes":
                case "on":
                case "是":
                    result = true;
                    return true;
                case "false":
                case "0":
                case "no":
                case "off":
                case "否":
                    result = false;
                    return true;
                default:
                    return false;
            }
        }

        private static void Warn(IList<string> warnings, int lineNumber, string text, string reason)
        {
            if (warnings == null) return;
            warnings.Add(string.Format(CultureInfo.InvariantCulture,
                "配置文件第 {0} 行「{1}」已忽略：{2}。", lineNumber, text, reason));
        }

        /// <summary>把当前设置序列化为配置文件文本（写回磁盘时用）。</summary>
        internal string Serialize()
        {
            System.Text.StringBuilder builder = new System.Text.StringBuilder();
            builder.AppendLine("# PipeAlign 管道标高对齐 · 运行参数");
            builder.AppendLine("# 长度单位一律为毫米。修改后重新执行 PIPEALIGN 生效。");
            builder.AppendLine();
            builder.AppendLine("# 水平管判定容差：中心线两端高差不大于该值即视为水平管。");
            builder.AppendLine("HorizontalToleranceMm=" + HorizontalToleranceMm.ToString("G17", CultureInfo.InvariantCulture));
            builder.AppendLine();
            builder.AppendLine("# 已对齐判定容差：|ΔZ| 不大于该值即视为本来就对齐、不移动。");
            builder.AppendLine("AlignmentToleranceMm=" + AlignmentToleranceMm.ToString("G17", CultureInfo.InvariantCulture));
            builder.AppendLine();
            builder.AppendLine("# Key-in 未指定模式时的默认值：BOTTOM / CENTER / TOP");
            builder.AppendLine("DefaultAlignmentMode=" + AlignmentModes.Code(DefaultAlignmentMode));
            builder.AppendLine();
            builder.AppendLine("# 启动时的默认表面模式：PIPE / INSULATION（程序不会自动猜测）");
            builder.AppendLine("DefaultSurfaceMode=" + SurfaceModes.Code(DefaultSurfaceMode));
            builder.AppendLine();
            builder.AppendLine("# 单次操作允许的最大目标管数量");
            builder.AppendLine("MaxTargetPipes=" + MaxTargetPipes.ToString(CultureInfo.InvariantCulture));
            builder.AppendLine();
            builder.AppendLine("# 是否允许回落到 DGN 图形变换（会让 OpenPlant 数据与图形不一致，默认关闭）");
            builder.AppendLine("AllowGraphicsTransformFallback=" + (AllowGraphicsTransformFallback ? "true" : "false"));
            builder.AppendLine();
            builder.AppendLine("# 是否把元素上的全部 EC 属性写入 Message Center（仅排查用）");
            builder.AppendLine("DumpEcProperties=" + (DumpEcProperties ? "true" : "false"));
            builder.AppendLine();
            builder.AppendLine("# 连接校验严格程度：STRICT / BESTEFFORT / OFF");
            builder.AppendLine("# STRICT：连接关系读不到就不移动（Safe Mode 默认）；");
            builder.AppendLine("# BESTEFFORT：读不到时放行；OFF：完全不校验连接（会产生隐藏断口）。");
            builder.AppendLine("TopologyCheckMode=" + PipeTopologyCheckModes.Code(TopologyCheckMode));
            builder.AppendLine();
            builder.AppendLine("# 移动范围：SINGLE（只移动选中的管道）/ GROUP（连同连通对象一起等量平移）");
            builder.AppendLine("# GROUP 遇到边界连接（设备管口 / 支吊架 / 仪表 / 未知类）会**拒绝整组**，");
            builder.AppendLine("# 因为等量平移会让那些连接产生断口。");
            builder.AppendLine("MoveScope=" + MoveScopes.Code(DefaultMoveScope));
            builder.AppendLine();
            builder.AppendLine("# GROUP 模式下允许一起平移的类别（逗号分隔）：PIPE,FITTING,FLANGE,VALVE,NOZZLE,SUPPORT,INSTRUMENT,UNKNOWN");
            builder.AppendLine("# 想让支吊架跟着管走就加 SUPPORT（默认不跟：那等于把支吊架从结构生根处拽下来）。");
            builder.AppendLine("MoveGroupMovableKinds=" + MoveGroupMovableKinds);
            builder.AppendLine();
            builder.AppendLine("# GROUP 模式下视为边界、遇到即拒绝整组的类别。");
            builder.AppendLine("MoveGroupBoundaryKinds=" + MoveGroupBoundaryKinds);
            builder.AppendLine();
            builder.AppendLine("# GROUP 一次最多展开多少个对象。");
            builder.AppendLine("MoveGroupMaxMembers=" + MoveGroupMaxMembers.ToString(CultureInfo.InvariantCulture));
            builder.AppendLine("RouteEndpointToleranceMm=" + RouteEndpointToleranceMm.ToString("G17", CultureInfo.InvariantCulture));
            builder.AppendLine("MinimumStretchLengthMm=" + MinimumStretchLengthMm.ToString("G17", CultureInfo.InvariantCulture));
            return builder.ToString();
        }
    }
}
