using System;

namespace PipeAlign
{
    /// <summary>
    /// 对齐基准（开发指南 §3.1 / §16）。
    /// <para>
    /// 三种模式都作用在管道**中心线标高**与**有效外径**上：
    /// Bottom = Zc − Deff/2、Center = Zc、Top = Zc + Deff/2。
    /// </para>
    /// </summary>
    internal enum AlignmentMode
    {
        /// <summary>管底：管道外表面最低点。</summary>
        Bottom = 0,

        /// <summary>管中心：管道中心线。</summary>
        Center = 1,

        /// <summary>管顶：管道外表面最高点。</summary>
        Top = 2
    }

    /// <summary>对齐模式的代号与中文名（界面文案、日志、Key-in 解析共用一份）。</summary>
    internal static class AlignmentModes
    {
        /// <summary>模式代号（英文，用于日志与 Key-in）。</summary>
        internal static string Code(AlignmentMode mode)
        {
            switch (mode)
            {
                case AlignmentMode.Bottom: return "BOTTOM";
                case AlignmentMode.Top: return "TOP";
                default: return "CENTER";
            }
        }

        /// <summary>模式中文名（界面文案）。</summary>
        internal static string Chinese(AlignmentMode mode)
        {
            switch (mode)
            {
                case AlignmentMode.Bottom: return "管底";
                case AlignmentMode.Top: return "管顶";
                default: return "管中心";
            }
        }

        /// <summary>
        /// 解析 Key-in 传来的模式文本（<c>BOTTOM</c> / <c>CENTER</c> / <c>TOP</c>，
        /// 也接受中文与 <c>B</c> / <c>C</c> / <c>T</c> 简写）。无法识别时返回 false，
        /// 由调用方决定是否回落默认模式。
        /// </summary>
        internal static bool TryParse(string text, out AlignmentMode mode)
        {
            mode = AlignmentMode.Center;
            if (string.IsNullOrWhiteSpace(text)) return false;
            switch (text.Trim().ToUpperInvariant())
            {
                case "B":
                case "BOTTOM":
                case "管底":
                    mode = AlignmentMode.Bottom;
                    return true;
                case "C":
                case "CENTER":
                case "CENTRE":
                case "管中心":
                    mode = AlignmentMode.Center;
                    return true;
                case "T":
                case "TOP":
                case "管顶":
                    mode = AlignmentMode.Top;
                    return true;
                default:
                    return false;
            }
        }
    }
}
