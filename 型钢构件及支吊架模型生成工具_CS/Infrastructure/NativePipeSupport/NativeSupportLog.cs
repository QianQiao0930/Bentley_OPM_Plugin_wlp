using System;
using System.IO;
using System.Text;

namespace SteelSectionProbe
{
    internal static class NativeSupportLog
    {
        internal static void Run(Action<Action<string>> work)
        {
            var log = new StringBuilder(DateTimeOffset.Now.ToString("o") + " 支吊架原生ISO确认\r\n");
            log.AppendLine("DLL=" + typeof(NativeSupportLog).Assembly.Location + "；MVID=" + typeof(NativeSupportLog).Assembly.ManifestModule.ModuleVersionId);
            try { work(text => log.AppendLine(text)); }
            catch (Exception ex) { log.AppendLine(ex.ToString()); throw; }
            finally
            {
                try
                {
                    string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SteelSectionProbe", "logs", "NativePipeSupport");
                    Directory.CreateDirectory(folder);
                    File.WriteAllText(Path.Combine(folder, "latest.log"), log.ToString(), new UTF8Encoding(false));
                }
                catch (Exception ex) { Bentley.DgnPlatformNET.NotificationManager.OutputPrompt("管夹日志保存失败：" + ex.Message); }
            }
        }
    }
}
