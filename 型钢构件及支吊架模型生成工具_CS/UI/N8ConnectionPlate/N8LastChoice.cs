using System;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>记住上次选择的 N8 连接板参数（跨会话，存 %LOCALAPPDATA%\SteelSectionProbe）。</summary>
    internal static class N8LastChoice
    {
        internal sealed class Data
        {
            // 默认类型 0 / 工况 H 保温 / 安装面竖直设备表面 / 朝向角 0。
            public int TypeIndex=0,ModeIndex=0,MountIndex=0;
            public string Heading="0";
        }
        private static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe","n8_last.json");
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
