using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>Move Group 展开的结果（开发指南 §23、§24）。</summary>
    internal sealed class PipeGroupExpansion
    {
        internal PipeGroupExpansion()
        {
            Members = new List<PipeInfo>();
            BoundaryDescriptions = new List<string>();
            Traces = new List<string>();
        }

        /// <summary>组内成员（含用户选中的种子）。</summary>
        internal List<PipeInfo> Members { get; private set; }

        /// <summary>边界连接的中文说明（遇到即拒绝整组的那些）。</summary>
        internal List<string> BoundaryDescriptions { get; private set; }

        /// <summary>展开过程记录（进日志）。</summary>
        internal List<string> Traces { get; private set; }

        /// <summary>拒绝原因；<c>null</c> 表示这一组可以整体平移。</summary>
        internal string RefusalReason { get; set; }

        internal bool IsUsable { get { return string.IsNullOrEmpty(RefusalReason); } }

        internal string DescribeBoundaries()
        {
            if (BoundaryDescriptions.Count == 0) return "（无）";
            return string.Join("；", BoundaryDescriptions.ToArray());
        }

        internal string Describe()
        {
            StringBuilder builder = new StringBuilder();
            builder.AppendFormat(CultureInfo.InvariantCulture, "整组 {0} 个对象", Members.Count);
            int added = 0;
            foreach (PipeInfo member in Members)
                if (member != null) added++;
            if (added != Members.Count)
                builder.AppendFormat(CultureInfo.InvariantCulture, "（有效 {0}）", added);
            if (!IsUsable) builder.Append("；已拒绝：").Append(RefusalReason);
            return builder.ToString();
        }
    }

    /// <summary>
    /// 沿连接关系展开 Move Group（开发指南 §23、§24）。
    /// <para>
    /// 从用户选中的管道出发做广度优先遍历：可一起移动的连通对象收进组里，遇到边界连接
    /// （设备管口 / 支吊架 / 仪表 / 未知类）就**拒绝整组** —— 等量平移必然在那里产生断口，
    /// 而指南 §24 明确要求"如果会产生断开，程序停止操作"。
    /// </para>
    /// <para>
    /// 刻意**不做**"能移多少移多少"的裁剪：那会正好在边界处留下断口，比不移动更糟。
    /// 宁可给出一句明确的拒绝理由，让用户自己去改路由或先拆分。
    /// </para>
    /// <para>
    /// 读取成员由调用方注入 <c>readByInstanceId</c> 完成（本类保持可离线断言，不引用 Bentley）。
    /// 成员读不出来同样拒绝整组 —— 读不到就无法确认它能不能动。
    /// </para>
    /// </summary>
    internal static class PipeGroupExpander
    {
        internal static PipeGroupExpansion Expand(
            IList<PipeInfo> seeds,
            MoveGroupPolicy policy,
            int maxMembers,
            Func<string, PipeInfo> readByInstanceId,
            Action<string> log)
        {
            PipeGroupExpansion expansion = new PipeGroupExpansion();
            if (seeds == null || seeds.Count == 0)
            {
                expansion.RefusalReason = "没有起点管道，无法展开整组。";
                return expansion;
            }
            if (policy == null) policy = MoveGroupPolicy.Default();
            if (maxMembers <= 0) maxMembers = 200;

            Dictionary<string, PipeInfo> byInstanceId =
                new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            Queue<PipeInfo> pending = new Queue<PipeInfo>();

            foreach (PipeInfo seed in seeds)
            {
                if (seed == null || string.IsNullOrEmpty(seed.InstanceId)) continue;
                if (byInstanceId.ContainsKey(seed.InstanceId)) continue;
                byInstanceId[seed.InstanceId] = seed;
                expansion.Members.Add(seed);
                pending.Enqueue(seed);
            }

            if (expansion.Members.Count == 0)
            {
                expansion.RefusalReason = "起点管道没有可用的实例 ID，无法展开整组。";
                return expansion;
            }

            while (pending.Count > 0)
            {
                PipeInfo current = pending.Dequeue();
                PipeTopology topology = current.Topology;

                if (topology == null || !topology.IsKnown)
                {
                    // 连接关系读不到 = 无法确定移动范围。这里必须拒绝：猜错范围就是断口。
                    expansion.RefusalReason = string.Format(CultureInfo.InvariantCulture,
                        "{0} 的连接关系读取失败，无法确定要一起移动哪些对象，整组未移动。{1}",
                        current.DisplayName,
                        topology == null || string.IsNullOrEmpty(topology.ReadWarning)
                            ? "" : "（" + topology.ReadWarning + "）");
                    return expansion;
                }

                if (!string.IsNullOrEmpty(topology.ReadSource))
                    expansion.Traces.Add(current.DisplayName + " 连通性来源：" + topology.ReadSource);

                foreach (PipeConnection connection in topology.Connections)
                {
                    if (connection == null || string.IsNullOrEmpty(connection.OtherInstanceId)) continue;
                    if (byInstanceId.ContainsKey(connection.OtherInstanceId)) continue;

                    PipeConnectionKind kind = connection.Kind;
                    if (!policy.IsMovable(kind))
                    {
                        expansion.BoundaryDescriptions.Add(string.Format(CultureInfo.InvariantCulture,
                            "{0} 的 {1} 连到边界对象 {2}{3}",
                            current.DisplayName,
                            connection.PortIndex >= 0
                                ? (connection.PortIndex + 1).ToString(CultureInfo.InvariantCulture) + " 口"
                                : "某口",
                            connection.DisplayName,
                            string.IsNullOrEmpty(PipeConnectionClassifier.Chinese(kind))
                                ? "" : "（" + PipeConnectionClassifier.Chinese(kind) + "）"));
                        continue;
                    }

                    if (byInstanceId.Count >= maxMembers)
                    {
                        expansion.RefusalReason = string.Format(CultureInfo.InvariantCulture,
                            "整组已展开到 {0} 个对象（上限 MoveGroupMaxMembers = {1}）仍未走到边界，"
                            + "为避免误拖整张图，整组未移动。可以把上限调大，或先分段选择。",
                            byInstanceId.Count, maxMembers);
                        return expansion;
                    }

                    PipeInfo member;
                    try
                    {
                        member = readByInstanceId == null ? null : readByInstanceId(connection.OtherInstanceId);
                    }
                    catch (Exception ex)
                    {
                        expansion.RefusalReason = string.Format(CultureInfo.InvariantCulture,
                            "连通对象 {0} 读取失败（{1}），无法确认它能否一起移动，整组未移动。",
                            connection.DisplayName, ex.Message);
                        return expansion;
                    }

                    if (member == null)
                    {
                        expansion.RefusalReason = string.Format(CultureInfo.InvariantCulture,
                            "连通对象 {0} 读取不到，无法确认它能否一起移动，整组未移动。",
                            connection.DisplayName);
                        return expansion;
                    }

                    byInstanceId[connection.OtherInstanceId] = member;
                    expansion.Members.Add(member);
                    pending.Enqueue(member);
                }
            }

            if (expansion.BoundaryDescriptions.Count > 0)
            {
                expansion.RefusalReason = string.Format(CultureInfo.InvariantCulture,
                    "整组平移会在边界连接处产生断口（指南 §24），因此未移动。边界：{0}。"
                    + "若要移动，请先处理这些边界（拆开连接、或把边界对象也纳入允许一起移动的类别）。",
                    expansion.DescribeBoundaries());
                return expansion;
            }

            if (log != null)
            {
                log(string.Format(CultureInfo.InvariantCulture,
                    "Move Group 展开：{0} 个对象（用户选中 {1} 个）。", expansion.Members.Count, seeds.Count));
            }
            return expansion;
        }
    }
}
