using System;
using System.IO;
using System.Text;

namespace SteelSectionProbe
{
    internal static class CelLibraryLog
    {
        internal static void Write(string stage, string message)
        {
            try
            {
                var directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "logs", "CelLibrary");
                Directory.CreateDirectory(directory);
                File.AppendAllText(Path.Combine(directory, "latest.log"),
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " [" + stage + "] " + message + Environment.NewLine, new UTF8Encoding(false));
            }
            catch { }
        }
    }
}
