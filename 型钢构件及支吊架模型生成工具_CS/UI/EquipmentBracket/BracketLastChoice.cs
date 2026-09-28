using System;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>记住上次选择的三角架参数（跨会话，存 %LOCALAPPDATA%\SteelSectionProbe）。</summary>
    /// <remarks>
    /// N3 单三角架与 N4 双三角架<b>共用</b> <c>BracketPage</c>（两个子类只差 <c>isDouble</c>），
    /// 但却是两个独立页面实例，因此两套字段必须分开存 —— 否则进了 N3 再进 N4 会互相覆盖。
    /// 这与 <c>PipeClampLastChoice</c> 用一个扁平类同时存 A2/E1/K1/T4 四种管夹是同一种做法。
    /// </remarks>
    internal static class BracketLastChoice
    {
        internal sealed class Data
        {
            // N3：只有类型 / 子项 / H / 反向 / 保留辅助线（双三角架面板不显示）。
            public int N3TypeIndex=0,N3SubtypeIndex=0;
            public string N3Height="";
            public bool N3Reverse=false,N3KeepLine=true;
            // N4：额外有 L2 / L3 / L4 / 设备外径 / 预焊件长度 / 显示预焊件。
            public int N4TypeIndex=0,N4SubtypeIndex=0;
            public string N4Height="",N4L2="",N4L3="",N4L4="",N4Od="",N4Preweld="0";
            public bool N4Reverse=false,N4KeepLine=true,N4ShowPreweld=false;
        }
        private static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe","bracket_last.json");
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
