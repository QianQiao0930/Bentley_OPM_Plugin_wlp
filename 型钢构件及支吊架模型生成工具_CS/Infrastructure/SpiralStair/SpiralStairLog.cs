using System;
using System.IO;
using System.Text;
using System.Globalization;
namespace SteelSectionProbe
{
    internal sealed class SpiralStairLog:IDisposable
    {
        private StreamWriter writer;
        internal string FilePath {get;private set;}
        internal SpiralStairLog(string folder=null)
        {
            folder=folder??Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"SteelSectionProbe","logs","SpiralStair");
            try{
                Directory.CreateDirectory(folder);FilePath=Path.Combine(folder,"spiral_latest.log");
                writer=new StreamWriter(FilePath,false,new UTF8Encoding(true)){AutoFlush=true};Write("初始化","程序集："+typeof(SpiralStairLog).Assembly.FullName);
            }catch(Exception ex){FilePath="日志创建失败："+ex.Message;}
        }
        internal void Write(string stage,string message)
        {
            if(writer==null)return;
            try{if(writer.BaseStream.Length>2*1024*1024){writer.BaseStream.SetLength(0);writer.BaseStream.Position=0;writer.WriteLine("日志达到2MB，已清空早期记录；后续保留最新阶段及异常。");}writer.WriteLine("["+DateTime.Now.ToString("HH:mm:ss.fff")+"] ["+stage+"] "+message);}
            catch(Exception ex){FilePath="日志写入失败："+ex.Message;try{writer.Dispose();}catch{}writer=null;}
        }
        internal void Parameters(SpiralStairParameters parameters)
        {
            foreach(var field in typeof(SpiralStairParameters).GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic))
                Write("参数",field.Name+"="+Convert.ToString(field.GetValue(parameters),CultureInfo.InvariantCulture));
        }
        internal static void Append(string file,string stage,string message)
        {
            if(string.IsNullOrEmpty(file)||!File.Exists(file))return;
            try{using(var w=new StreamWriter(file,true,new UTF8Encoding(true)))w.WriteLine("["+DateTime.Now.ToString("HH:mm:ss.fff")+"] ["+stage+"] "+message);}
            catch{} // 记录确认/清理失败时，不得用日志异常覆盖原来的宿主错误。
        }
        public void Dispose(){if(writer!=null){try{writer.Dispose();}catch{}writer=null;}}
    }
}
