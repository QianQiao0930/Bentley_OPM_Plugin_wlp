using System;
using System.IO;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>记住上次选择的管夹类型与各类型参数（跨会话，存 %LOCALAPPDATA%\SteelSectionProbe）。</summary>
    internal static class PipeClampLastChoice
    {
        internal sealed class Data
        {
            public int KindIndex;
            public int A2DnIndex,E1DnIndex,E1ItemIndex,K1DnIndex,K1SubitemIndex,T4DnIndex;
            public string A2Insulation="0",E1Material="",K1Width="100",K1Material="Q235B";
            public string T4Insulation="50",T4Length="300",T4Name="T4",T4Temp="",T4Material="",T4F="";
            public bool E1Stainless,T4Pipe,T4InsulationBuild;
        }
        private static string FilePath
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe","pipe_clamp_last.json");
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
