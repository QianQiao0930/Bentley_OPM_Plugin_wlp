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
    /// 这里记录的是"宿主到底走通了哪一条写入路径"这种只能实测才知道的事实：
    /// 逐个子元素替换是否成功、是否必须退回到整台单元替换、校验时读到多少个图元。
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
