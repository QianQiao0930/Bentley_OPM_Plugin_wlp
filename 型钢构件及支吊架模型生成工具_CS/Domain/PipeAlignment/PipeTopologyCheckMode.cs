namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 拓扑校验模式（开发指南 §21、§22）。
    /// <para>
    /// Safe Mode 是默认行为：连到"不会一起移动的对象"就停止该管。但读取连接关系依赖
    /// OpenPlant 的对象模型，在个别模型 / 版本上可能失败；此时**必须由用户明确选择**
    /// 是"保守拒绝"还是"放行并承担风险"，不允许程序自己悄悄放宽。
    /// </para>
    /// </summary>
    internal enum PipeTopologyCheckMode
    {
        /// <summary>严格（默认）：连接关系读不到就拒绝该管。</summary>
        Strict = 0,

        /// <summary>尽力而为：连接关系读不到时放行，但会有明确警告。</summary>
        BestEffort = 1,

        /// <summary>关闭：不做任何连接校验。只有用户明确要求时才用。</summary>
        Off = 2
    }

    internal static class PipeTopologyCheckModes
    {
        internal static string Code(PipeTopologyCheckMode mode)
        {
            switch (mode)
            {
                case PipeTopologyCheckMode.BestEffort: return "BESTEFFORT";
                case PipeTopologyCheckMode.Off: return "OFF";
                default: return "STRICT";
            }
        }

        internal static string Chinese(PipeTopologyCheckMode mode)
        {
            switch (mode)
            {
                case PipeTopologyCheckMode.BestEffort: return "尽力而为（连接关系读不到时放行）";
                case PipeTopologyCheckMode.Off: return "关闭连接校验（危险）";
                default: return "严格（连接关系不确定就不移动）";
            }
        }

        internal static bool TryParse(string text, out PipeTopologyCheckMode mode)
        {
            mode = PipeTopologyCheckMode.Strict;
            if (string.IsNullOrWhiteSpace(text)) return false;
            switch (text.Trim().ToUpperInvariant())
            {
                case "STRICT":
                case "SAFE":
                case "严格":
                    mode = PipeTopologyCheckMode.Strict;
                    return true;
                case "BESTEFFORT":
                case "BEST_EFFORT":
                case "尽力而为":
                    mode = PipeTopologyCheckMode.BestEffort;
                    return true;
                case "OFF":
                case "NONE":
                case "关闭":
                    mode = PipeTopologyCheckMode.Off;
                    return true;
                default:
                    return false;
            }
        }
    }
}
