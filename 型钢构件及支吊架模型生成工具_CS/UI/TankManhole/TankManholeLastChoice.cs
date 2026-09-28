using System;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>记住上次选择的人孔参数（跨会话，存 %LOCALAPPDATA%\SteelSectionProbe）。</summary>
    internal static class TankManholeLastChoice
    {
        internal sealed class Data
        {
            // 默认 DN600 / ASA150 / 吊杆式 / 筒节 150 / 朝向 0，勾选螺栓与开盖机构。
            public int DnIndex=2, PressureIndex=0, ModeIndex=0;
            public string Neck="150", Heading="0";
            public bool Mirrored, Bolts=true, Lifting=true;
        }
        private static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe","tank_manhole_last.json");
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
