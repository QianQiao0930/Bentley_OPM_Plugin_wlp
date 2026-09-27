using System;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>记住上次选择的 G2 锚板参数（跨会话，存 %LOCALAPPDATA%\SteelSectionProbe）。</summary>
    internal static class G2AnchorLastChoice
    {
        internal sealed class Data
        {
            // 默认子项 A / 安装面竖直墙面 / 朝 0；间距留空表示取该子项 MIN.S。
            public int SubtypeIndex=0, MountIndex=0;
            public string Spacing="";
            public string Heading="0";
        }
        private static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe","g2_anchor_last.json");
            }
        }
        internal static Data Load()
        {
            try
            {
                if(!File.Exists(FilePath)) return new Data();
                string json;
                using(var reader=new StreamReader(FilePath)) json=reader.ReadToEnd();
                return new JavaScriptSerializer().Deserialize<Data>(json) ?? new Data();
            }
            catch { return new Data(); }
        }
        internal static void Save(Data data)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
                File.WriteAllText(FilePath,new JavaScriptSerializer().Serialize(data));
            }
            catch { /* 记不住就记不住，别影响建模 */ }
        }
    }
}
