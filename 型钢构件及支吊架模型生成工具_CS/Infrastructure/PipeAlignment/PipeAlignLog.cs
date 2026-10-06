using System;
using System.Globalization;
using System.IO;
using System.Text;
using Bentley.OpenPlantModeler.SDK;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 插件日志（开发指南 §30）。
    /// <para>
    /// **正式日志只写简短摘要**，不给 Message Center 刷屏；EC 全量转储只在
    /// <c>PIPEALIGN DEBUG DUMP</c> 下发生。详细数据写进
    /// <c>%LOCALAPPDATA%\PipeAlign\PipeAlign_debug_log.txt</c>，出问题时看那个文件。
    /// </para>
    /// <para>
    /// 安全约定：日志本身的任何异常一律吞掉 —— 日志失败绝不允许影响对齐流程。
    /// </para>
    /// </summary>
    internal sealed class PipeAlignLog
    {
        private readonly bool _verbose;
        private readonly StringBuilder _buffer = new StringBuilder();

        /// <param name="verbose">是否把逐根管道的明细也交给 Message Center（Debug 模式）。</param>
        internal PipeAlignLog(bool verbose)
        {
            _verbose = verbose;
        }

        /// <summary>用户可见的短信息（Message Center 信息栏 + 日志文件）。</summary>
        internal void Info(string message)
        {
            Write("INFO", message);
            if (_verbose) Send(0, message);
        }

        /// <summary>需要用户注意的警告（Message Center 警告栏 + 日志文件）。</summary>
        internal void Warn(string message)
        {
            Write("WARN", message);
            Send(1, message);
        }

        /// <summary>错误（Message Center 错误栏 + 日志文件）。</summary>
        internal void Error(string message)
        {
            Write("ERROR", message);
            Send(2, message);
        }

        /// <summary>只进日志文件，不进 Message Center（逐根管的明细走这里）。</summary>
        internal void Detail(string message)
        {
            Write("DEBUG", message);
        }

        /// <summary>整段文本（例如 <see cref="AlignmentResult.BuildLog"/> 的结果）按行写入日志文件。</summary>
        internal void Block(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            string[] lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            foreach (string line in lines)
            {
                if (line.Length == 0) continue;
                Write("DEBUG", line);
            }
        }

        private static void Send(int severity, string message)
        {
            try
            {
                switch (severity)
                {
                    case 1:
                        MessageCenter.SendWarningMessage("PIPEALIGN：" + message);
                        break;
                    case 2:
                        MessageCenter.SendErrorMessage("PIPEALIGN：" + message);
                        break;
                    default:
                        MessageCenter.SendInfoMessage("PIPEALIGN：" + message);
                        break;
                }
            }
            catch
            {
                // Message Center 不可用（例如不在 OPM 宿主里）时静默。
            }
        }

        private void Write(string level, string message)
        {
            try
            {
                _buffer.Append('[').Append(DateTime.Now.ToString("HH:mm:ss.fff",
                    CultureInfo.InvariantCulture)).Append("] [").Append(level).Append("] ")
                    .Append(message).AppendLine();
            }
            catch
            {
            }
        }

        /// <summary>把本次会话累积的日志落盘。失败静默。</summary>
        internal void Flush()
        {
            try
            {
                if (_buffer.Length == 0) return;
                string directory = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PipeAlign");
                if (!Directory.Exists(directory)) Directory.CreateDirectory(directory);
                File.AppendAllText(Path.Combine(directory, "PipeAlign_debug_log.txt"),
                    _buffer.ToString(), Encoding.UTF8);
                _buffer.Clear();
            }
            catch
            {
            }
        }
    }
}
