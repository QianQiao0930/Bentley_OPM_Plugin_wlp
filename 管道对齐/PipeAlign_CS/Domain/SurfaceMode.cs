namespace PipeAlign
{
    /// <summary>
    /// 表面对齐模式（开发指南 §10）。
    /// <para>
    /// 程序**不得自动猜测**用户需要哪一种表面，必须在界面上明确显示当前模式。
    /// </para>
    /// </summary>
    internal enum SurfaceMode
    {
        /// <summary>管道外表面：Deffective = Do。</summary>
        Pipe = 0,

        /// <summary>保温层外表面：Deffective = Do + 2 × Tinsulation。</summary>
        Insulation = 1
    }

    /// <summary>表面对齐模式的代号与中文名。</summary>
    internal static class SurfaceModes
    {
        /// <summary>模式代号（英文，用于日志）。</summary>
        internal static string Code(SurfaceMode mode)
        {
            return mode == SurfaceMode.Insulation ? "INSULATION" : "PIPE";
        }

        /// <summary>模式中文名（界面文案）。</summary>
        internal static string Chinese(SurfaceMode mode)
        {
            return mode == SurfaceMode.Insulation ? "保温层外表面" : "管道外表面";
        }

        /// <summary>解析 Key-in 传来的模式文本；无法识别时返回 false。</summary>
        internal static bool TryParse(string text, out SurfaceMode mode)
        {
            mode = SurfaceMode.Pipe;
            if (string.IsNullOrWhiteSpace(text)) return false;
            switch (text.Trim().ToUpperInvariant())
            {
                case "PIPE":
                case "管道":
                case "管道外表面":
                    mode = SurfaceMode.Pipe;
                    return true;
                case "INSULATION":
                case "INS":
                case "保温":
                case "保温层外表面":
                    mode = SurfaceMode.Insulation;
                    return true;
                default:
                    return false;
            }
        }
    }
}
