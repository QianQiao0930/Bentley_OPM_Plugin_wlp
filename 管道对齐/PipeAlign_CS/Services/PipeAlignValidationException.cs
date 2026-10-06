using System;

namespace PipeAlign
{
    /// <summary>
    /// 校验失败：消息是**面向用户的中文文案**，可直接显示在状态栏或对话框上
    /// （开发指南 §12、§22 要求"程序必须给出明确的信息"）。
    /// </summary>
    internal sealed class PipeAlignValidationException : Exception
    {
        internal PipeAlignValidationException(string message) : base(message)
        {
        }

        internal PipeAlignValidationException(string message, Exception inner) : base(message, inner)
        {
        }
    }
}
