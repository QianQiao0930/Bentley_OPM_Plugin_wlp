using System;
using System.Globalization;
using System.IO;

namespace SteelSectionProbe
{
    internal static class SupportExportName
    {
        internal static string Suggest(string activeDgnPath,DateTime savedAt)
        {
            string name=Path.GetFileNameWithoutExtension(activeDgnPath ?? "");
            if (string.IsNullOrWhiteSpace(name)) name="当前文档";
            foreach(char invalid in Path.GetInvalidFileNameChars())
                name=name.Replace(invalid,'_');
            name=name.Trim().TrimEnd('.');
            if (name.Length==0) name="当前文档";
            return name+"_支吊架材料表_"+
                savedAt.ToString("yyyyMMddHHmmss",CultureInfo.InvariantCulture);
        }
    }
}
