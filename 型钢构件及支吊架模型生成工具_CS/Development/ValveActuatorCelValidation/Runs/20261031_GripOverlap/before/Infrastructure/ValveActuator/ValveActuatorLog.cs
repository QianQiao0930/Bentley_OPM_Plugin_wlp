using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    internal static class ValveActuatorLog
    {
        private static readonly HashSet<string> callbacks = new HashSet<string>();
        internal static void Callback(ActuatorCelAsset asset, string instanceId)
        {
            // Dynamic callbacks repeat rapidly. Log a bounded set of resource/instance identities once.
            string key = instanceId + ":" + asset.Hash + ":" + asset.CellName;
            if (callbacks.Count >= 256 || !callbacks.Add(key)) return;
            Write("callback", "Instance=" + instanceId + "; Cell=" + asset.CellName + "; ResourceSha256=" + asset.Hash
                + "; Bytes=" + asset.ByteCount + "; Resource=instance SSP_CEL_DATA; NativeGearboxMarker=true");
        }
        internal static void Write(string stage, string text)
        {
            try
            {
                string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SteelSectionProbe", "logs", "ValveActuator");
                Directory.CreateDirectory(root);
                File.WriteAllText(Path.Combine(root, DateTime.Now.ToString("yyyyMMdd_HHmmss_fff") + "_" + stage + "_" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".log"),
                    DateTimeOffset.Now.ToString("o") + "\r\nRoute=selected CEL / native gearbox / official StartPlacement\r\nAssembly="
                    + typeof(ValveActuatorLog).Assembly.Location + "; MVID=" + typeof(ValveActuatorLog).Assembly.ManifestModule.ModuleVersionId + "\r\n" + text, new UTF8Encoding(false));
            }
            catch (Exception error) { NotificationManager.OutputPrompt("执行机构日志保存失败：" + error.Message); }
        }
    }
}
