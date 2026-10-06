namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 移动范围（开发指南 §22 的 Safe Mode 与 §23 的 Move Group）。
    /// </summary>
    internal enum MoveScope
    {
        /// <summary>
        /// 只移动选中的管道。目标管如果连到"本批不会一起移动的对象"就跳过。
        /// <para>这是安全默认值，但它对真实管线很不好用：实际管道几乎没有孤立的。</para>
        /// </summary>
        SelectedOnly = 0,

        /// <summary>
        /// 连同**连通对象**一起等量平移（开发指南 §23 的 Move Group）。
        /// <para>
        /// 从选中的管道出发沿连接关系展开整组，组内所有对象使用同一个 ΔZ。
        /// 遇到边界连接（设备管口 / 支吊架 / 仪表 / 未知类）按指南 §24 **拒绝整组**，
        /// 因为等量平移会让那些连接产生断口。
        /// </para>
        /// </summary>
        ConnectedGroup = 1,
        ZStretch = 2
    }

    internal static class MoveScopes
    {
        internal static string Code(MoveScope scope)
        {
            return scope == MoveScope.ZStretch ? "ZSTRETCH" : scope == MoveScope.ConnectedGroup ? "GROUP" : "SINGLE";
        }

        internal static string Chinese(MoveScope scope)
        {
            return scope == MoveScope.ZStretch ? "锁 Z 轴移动（立管伸缩、另一端固定）" : scope == MoveScope.ConnectedGroup
                ? "连同连通对象一起移动（Move Group）"
                : "只移动选中的管道";
        }

        internal static bool TryParse(string text, out MoveScope scope)
        {
            scope = MoveScope.SelectedOnly;
            if (string.IsNullOrWhiteSpace(text)) return false;
            switch (text.Trim().ToUpperInvariant())
            {
                case "ZSTRETCH":
                case "锁Z":
                    scope = MoveScope.ZStretch;
                    return true;
                case "SINGLE":
                case "SELECTED":
                case "SELECTEDONLY":
                case "单个":
                case "只移动选中":
                    scope = MoveScope.SelectedOnly;
                    return true;
                case "GROUP":
                case "CONNECTEDGROUP":
                case "MOVEGROUP":
                case "整组":
                case "连通组":
                    scope = MoveScope.ConnectedGroup;
                    return true;
                default:
                    return false;
            }
        }
    }
}
