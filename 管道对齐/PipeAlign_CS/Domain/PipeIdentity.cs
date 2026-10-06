namespace PipeAlign
{
    /// <summary>
    /// 管道身份的**判等键**。
    /// <para>
    /// 单用 <c>ElementId</c> 判等是不安全的：ElementId 只在**它自己那个文件的 ID 空间**里有效，
    /// 参考文件里的管道与活动模型里的某个元素完全可能同号。若只按 ElementId 去重，
    /// 二者会被当成"同一根管重复选中"而**静默丢掉一个**（用户看到的行数比选中的少，也不知道为什么）。
    /// </para>
    /// <para>纯计算，无 Bentley 依赖。</para>
    /// </summary>
    internal static class PipeIdentity
    {
        internal static string Key(PipeInfo pipe)
        {
            if (pipe == null) return string.Empty;
            return pipe.ElementId.ToString("X")
                + (pipe.IsFromReference ? "@ref" : "@active");
        }

        internal static bool SamePipe(PipeInfo left, PipeInfo right)
        {
            if (left == null || right == null) return false;
            return string.Equals(Key(left), Key(right), System.StringComparison.Ordinal);
        }
    }
}
