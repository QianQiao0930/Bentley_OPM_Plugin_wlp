using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class A1NativeTrialCommands
    {
        internal static string LogPath { get { return Path.Combine(Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData), "SteelSectionProbe", "logs", "A1NativeSupport", "latest.log"); } }

        internal static void Run(string arguments)
        {
            string[] parts = (arguments ?? "").Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            string action = parts.Length == 0 ? "HELP" : parts[0].ToUpperInvariant();
            if (action == "LOG")
            {
                try
                {
                    if (File.Exists(LogPath)) Process.Start(new ProcessStartInfo(LogPath) { UseShellExecute = true });
                    else NotificationManager.OutputPrompt("还没有A1原生关联试验日志。");
                }
                catch (Exception ex) { NotificationManager.OutputPrompt("打开日志失败：" + ex.Message + "；路径=" + LogPath); }
                return;
            }
            if (action != "PLACE" && action != "CHECK")
            {
                NotificationManager.OutputPrompt("选一根水平裸直管：STEELPROBE A1TEST PLACE [距起点mm] [开口角度]；选试验A1后用CHECK检查，用LOG查看日志。");
                return;
            }
            var log = new StringBuilder();
            log.AppendLine(DateTimeOffset.Now.ToString("o") + " A1TEST " + arguments);
            var assembly = typeof(A1NativeTrialCommands).Assembly;
            log.AppendLine("DLL=" + assembly.Location + "；模块标识=" + assembly.ManifestModule.ModuleVersionId);
            bool failed = false;
            try
            {
                if (action == "PLACE")
                {
                    if (parts.Length > 3) throw new InvalidOperationException("PLACE最多接受距起点mm、开口角度两个参数。");
                    double? station = parts.Length > 1 ? A1NativeTrialCalculator.Parse(parts[1]) : (double?)null;
                    double angle = parts.Length > 2 ? A1NativeTrialCalculator.Parse(parts[2]) : 0;
                    A1NativeTrialAdapter.Place(station, angle, text => log.AppendLine(text));
                }
                else
                {
                    if (parts.Length != 1) throw new InvalidOperationException("CHECK不接受额外参数，请先选中一个试验A1。");
                    failed = !A1NativeTrialAdapter.CheckSelected(text => log.AppendLine(text));
                }
            }
            catch (Exception ex) { failed = true; log.AppendLine("失败：" + ex); }
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(LogPath));
                File.WriteAllText(LogPath, log.ToString(), new UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                NotificationManager.OutputPrompt("A1试验日志保存失败：" + ex.Message);
                MainWindow.Current?.SetStatus(log.ToString(), true); return;
            }
            string message = failed ? "A1试验未通过，请用STEELPROBE A1TEST LOG查看日志。"
                : action == "PLACE" ? "试验A1已生成；请提取单线图，并移动管道后选中该A1运行CHECK。"
                : "检查已记录（包含位置通过/不通过结果），请用STEELPROBE A1TEST LOG查看。";
            NotificationManager.OutputPrompt(message);
            MainWindow.Current?.SetStatus(message, failed);
        }
    }
}
