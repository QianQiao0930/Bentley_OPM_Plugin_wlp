using System;
using System.Globalization;
using System.IO;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 设备图层批量修改的诊断日志：固定写到
    /// <c>%LOCALAPPDATA%\SteelSectionProbe\logs\EquipmentLevel\latest.log</c>，
    /// 每次进程启动覆盖一次，超过 256 KB 自动截断。
    /// <para>
    /// 记录 COM 包含关系、修改前图层/颜色、重新读取的校验结果与回滚结果。
    /// 日志失败绝不影响业务。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelLog
    {
        private static readonly object Gate = new object();
        private static bool started;

        /// <summary>日志文件的完整路径（供错误提示引用）。</summary>
        internal static string FilePath
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "logs", "EquipmentLevel", "latest.log");
            }
        }

        /// <summary>
        /// 把图元树写进独立文件 <c>tree.log</c>（每次覆盖，不参与 latest.log 的滚动）。
        /// 只用于核对结构，失败同样不影响业务。
        /// </summary>
        internal static void WriteTree(string text)
        {
            try
            {
                string file = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "logs", "EquipmentLevel", "tree.log");
                string directory = Path.GetDirectoryName(file);
                if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
                File.WriteAllText(file, text, new UTF8Encoding(false));
            }
            catch
            {
                // 诊断文件写不进去不影响改层。
            }
        }

        internal static void Write(string message)
        {
            try
            {
                lock (Gate)
                {
                    string file = FilePath;
                    string directory = Path.GetDirectoryName(file);
                    if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
                    var info = new FileInfo(file);
                    if (!started || (info.Exists && info.Length > 256 * 1024))
                    {
                        started = true;
                        File.WriteAllText(file, "", new UTF8Encoding(false));
                    }
                    File.AppendAllText(file,
                        DateTime.Now.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture) + "  " + message +
                        Environment.NewLine, new UTF8Encoding(false));
                }
            }
            catch
            {
                // 日志是可选诊断，失败不得影响改层。
            }
        }
    }
}
