using System;
using System.Collections.Generic;
using System.Text;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 连接对象类别（开发指南 §21 要求识别的连接情形）。
    /// <para>分类只依据 EC 类名，不依据 DGN 图元类型（指南 §2.1）。</para>
    /// </summary>
    internal enum PipeConnectionKind
    {
        /// <summary>无法归类。</summary>
        Unknown = 0,

        /// <summary>另一端是管道（PIPE）。</summary>
        Pipe = 1,

        /// <summary>管件：弯头 / 三通 / 异径管 / 管箍 / 管嘴等。</summary>
        Fitting = 2,

        /// <summary>设备管口（NOZZLE）。</summary>
        EquipmentNozzle = 3,

        /// <summary>阀门。</summary>
        Valve = 4,

        /// <summary>法兰 / 垫片 / 螺栓等连接件。</summary>
        Flange = 5,

        /// <summary>支吊架。</summary>
        Support = 6,

        /// <summary>仪表。</summary>
        Instrument = 7
    }

    /// <summary>由 EC 类名判定连接对象类别。纯查表，可离线断言。</summary>
    internal static class PipeConnectionClassifier
    {
        /// <summary>
        /// 按类名关键字归类。判定**顺序敏感**：先认更具体的类
        /// （管口 → 仪表 → 支吊架 → 阀门 → 法兰 → 管件），最后才落到"管道"。
        /// 否则 <c>PIPE_NOZZLE</c> 会被当成管道、<c>PIPE_SUPPORT</c> 会被当成管道。
        /// </summary>
        internal static PipeConnectionKind Classify(string className)
        {
            if (string.IsNullOrWhiteSpace(className)) return PipeConnectionKind.Unknown;
            string name = className.Trim().ToUpperInvariant();

            if (name.IndexOf("NOZZLE", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.EquipmentNozzle;
            if (name.IndexOf("INSTRUMENT", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Instrument;
            if (name.IndexOf("SUPPORT", StringComparison.Ordinal) >= 0
                || name.IndexOf("HANGER", StringComparison.Ordinal) >= 0
                || name.IndexOf("CLAMP", StringComparison.Ordinal) >= 0
                || name.IndexOf("GUIDE", StringComparison.Ordinal) >= 0
                || name.IndexOf("ANCHOR", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Support;
            if (name.IndexOf("VALVE", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Valve;
            if (name.IndexOf("FLANGE", StringComparison.Ordinal) >= 0
                || name.IndexOf("GASKET", StringComparison.Ordinal) >= 0
                || name.IndexOf("BOLT", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Flange;
            if (name.IndexOf("ELBOW", StringComparison.Ordinal) >= 0
                || name.IndexOf("BEND", StringComparison.Ordinal) >= 0
                || name.IndexOf("TEE", StringComparison.Ordinal) >= 0
                || name.IndexOf("REDUCER", StringComparison.Ordinal) >= 0
                || name.IndexOf("COUPLING", StringComparison.Ordinal) >= 0
                || name.IndexOf("OLET", StringComparison.Ordinal) >= 0
                || name.IndexOf("NIPPLE", StringComparison.Ordinal) >= 0
                || name.IndexOf("CAP", StringComparison.Ordinal) >= 0
                || name.IndexOf("PLUG", StringComparison.Ordinal) >= 0
                || name.IndexOf("UNION", StringComparison.Ordinal) >= 0
                || name.IndexOf("CROSS", StringComparison.Ordinal) >= 0
                || name.IndexOf("FITTING", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Fitting;
            if (name.IndexOf("PIPE", StringComparison.Ordinal) >= 0)
                return PipeConnectionKind.Pipe;
            return PipeConnectionKind.Unknown;
        }

        /// <summary>类别的中文名；未知返回 <c>null</c>。</summary>
        internal static string Chinese(PipeConnectionKind kind)
        {
            switch (kind)
            {
                case PipeConnectionKind.Pipe: return "管道";
                case PipeConnectionKind.Fitting: return "管件";
                case PipeConnectionKind.EquipmentNozzle: return "设备管口";
                case PipeConnectionKind.Valve: return "阀门";
                case PipeConnectionKind.Flange: return "法兰";
                case PipeConnectionKind.Support: return "支吊架";
                case PipeConnectionKind.Instrument: return "仪表";
                default: return null;
            }
        }
    }

    /// <summary>
    /// 一个连接端点。
    /// <para>
    /// 对端用 **EC 实例 ID** 标识，而不是元素 ID：OpenPlant 的连接关系本来就建立在实例之间
    /// （<c>Port.ConnectedTo</c> 给的就是对端实例 ID），用实例 ID 判等不受"元素 ID 分属不同
    /// 文件 ID 空间"的影响，也不需要额外反查元素。
    /// </para>
    /// </summary>
    internal sealed class PipeConnection
    {
        internal PipeConnection(int portIndex, string otherInstanceId, string otherClassName,
            string otherPipeNumber)
        {
            PortIndex = portIndex;
            OtherInstanceId = otherInstanceId ?? string.Empty;
            OtherClassName = otherClassName;
            OtherPipeNumber = otherPipeNumber;
            Kind = PipeConnectionClassifier.Classify(otherClassName);
        }

        /// <summary>本管一侧的本口序号。取不到时为 <c>-1</c>（例如只从 ConnectedComponents 得到的信息）。</summary>
        internal int PortIndex { get; set; }

        /// <summary>对端 EC 实例 ID。</summary>
        internal string OtherInstanceId { get; private set; }

        /// <summary>对端 EC 类名（取不到时为 <c>null</c>）。</summary>
        internal string OtherClassName { get; set; }

        /// <summary>对端管线号（对端是管道时才有）。规划阶段会用已知管道反填，便于用户辨认。</summary>
        internal string OtherPipeNumber { get; set; }

        /// <summary>对端类别。</summary>
        internal PipeConnectionKind Kind { get; private set; }

        internal string DisplayName
        {
            get
            {
                if (!string.IsNullOrEmpty(OtherPipeNumber)) return OtherPipeNumber;
                if (!string.IsNullOrEmpty(OtherClassName)) return OtherClassName;
                if (string.IsNullOrEmpty(OtherInstanceId)) return "未知对象";
                return "实例 " + Shorten(OtherInstanceId);
            }
        }

        private static string Shorten(string value)
        {
            if (value.Length <= 12) return value;
            return value.Substring(0, 12) + "…";
        }

        internal string Describe()
        {
            string port = PortIndex >= 0 ? (PortIndex + 1).ToString() : "?";
            string kind = PipeConnectionClassifier.Chinese(Kind);
            return string.Format("{0} 口 → {1}{2}", port, DisplayName,
                string.IsNullOrEmpty(kind) ? "" : "（" + kind + "）");
        }
    }

    /// <summary>
    /// 管道的连接关系摘要（开发指南 §21）。
    /// <para>V1 采用 Safe Mode（§22）：只要存在连到"不会一起移动的对象"的连接，
    /// 这根目标管就必须被跳过，并把原因明确告诉用户。</para>
    /// </summary>
    internal sealed class PipeTopology
    {
        private readonly List<PipeConnection> _connections = new List<PipeConnection>();

        /// <summary>连接关系是否读取成功。读取失败时 <c>false</c>，Safe Mode 下按"未知"处理。</summary>
        internal bool IsKnown { get; set; }

        /// <summary>读取连接关系时的中文提示（失败原因），没有则为 <c>null</c>。</summary>
        internal string ReadWarning { get; set; }

        /// <summary>
        /// 连接关系的读取来源说明（对象来源、端口数、ConnectedComponents 数、合并后条数）。
        /// <para>
        /// 用来回答"到底是真的没有连接，还是我们没读到"—— 这个区分很要紧：
        /// Safe Mode 依赖它，而现场出现过"明显连着邻管却报无连接"。
        /// </para>
        /// </summary>
        internal string ReadSource { get; set; }

        internal PipeTopology()
        {
            IsKnown = true;
        }

        internal PipeTopology(IEnumerable<PipeConnection> connections)
        {
            IsKnown = true;
            if (connections != null) _connections.AddRange(connections);
        }

        internal IList<PipeConnection> Connections { get { return _connections; } }

        internal int ConnectionCount { get { return _connections.Count; } }

        internal bool HasConnection { get { return _connections.Count > 0; } }

        /// <summary>两端都有连接（§21 的 Two-end connection）。</summary>
        internal bool IsTwoEndConnected
        {
            get
            {
                bool first = false, second = false;
                foreach (PipeConnection connection in _connections)
                {
                    if (connection.PortIndex <= 0) first = true; else second = true;
                }
                return first && second;
            }
        }

        /// <summary>是否连到设备管口 —— §24 的边界连接，Safe Mode 下必须停止该管。</summary>
        internal bool HasBoundaryConnection
        {
            get
            {
                foreach (PipeConnection connection in _connections)
                    if (connection.Kind == PipeConnectionKind.EquipmentNozzle) return true;
                return false;
            }
        }

        /// <summary>连接情形的中文摘要（指南 §21 的分类文字）。</summary>
        internal string Summary()
        {
            if (!IsKnown) return "连接关系未知";
            if (_connections.Count == 0) return "无连接";
            if (_connections.Count == 1) return "单端连接（" + _connections[0].DisplayName + "）";
            StringBuilder builder = new StringBuilder();
            builder.Append("两端连接（");
            for (int index = 0; index < _connections.Count; index++)
            {
                if (index > 0) builder.Append("、");
                builder.Append(_connections[index].DisplayName);
            }
            builder.Append("）");
            return builder.ToString();
        }

        /// <summary>
        /// Safe Mode 判定：这些连接里是否有"不会被一起移动"的对象。
        /// </summary>
        /// <param name="movingInstanceIds">本批要一起移动的 EC 实例 ID 集合。</param>
        internal PipeConnection FindBlockingConnection(ICollection<string> movingInstanceIds)
        {
            foreach (PipeConnection connection in _connections)
            {
                if (movingInstanceIds != null
                    && !string.IsNullOrEmpty(connection.OtherInstanceId)
                    && movingInstanceIds.Contains(connection.OtherInstanceId))
                    continue;
                return connection;
            }
            return null;
        }
    }
}
