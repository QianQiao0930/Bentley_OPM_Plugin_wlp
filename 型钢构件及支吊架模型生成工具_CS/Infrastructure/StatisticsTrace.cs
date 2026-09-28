using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 临时性能埋点：记录每次“确认”写入附加项（ItemType）的耗时分布。
    /// <para>
    /// 用途：定位“确认写入慢”的瓶颈到底在 <c>FindByName</c> 全库加载、
    /// <c>library.Write()</c> 全库写盘，还是 <c>ApplyCustomItem</c> 逐条附加。
    /// 取数完成后会整体删除本文件及 <c>Statistics.cs</c> 里的调用。
    /// </para>
    /// <para>
    /// ⚠️ 安全约定：本类所有内部异常一律静默，绝不允许因为埋点失败而影响写入流程；
    /// 它不持有任何 Bentley 对象、不跨线程、不改动任何既有数据。
    /// </para>
    /// </summary>
    internal static class StatisticsTrace
    {
        /// <summary>埋点总开关。取数后改为 false 即可停写日志，或直接删除本文件与调用点。</summary>
        internal static readonly bool Enabled=true;

        [ThreadStatic] private static Measurement current;

        internal static IDisposable Scope(string context)
        {
            if(!Enabled) return Noop.Instance;
            try { var item=new Measurement(context); current=item; return item; }
            catch { return Noop.Instance; }
        }

        /// <summary>计时一段子步骤；结果累加到当前 <see cref="Scope"/>。</summary>
        internal static IDisposable Section(string label)
        {
            if(!Enabled || current==null) return Noop.Instance;
            try { return new Step(label,current); }
            catch { return Noop.Instance; }
        }

        /// <summary>附加一个说明项（如库内 ItemType 总数）。</summary>
        internal static void Note(string key,string value)
        {
            if(!Enabled || current==null) return;
            try { current.Notes.Add(key+"="+value); } catch { }
        }

        internal static void Increment(string key,int count)
        {
            if(!Enabled || current==null) return;
            try
            {
                int existing;
                current.Counts.TryGetValue(key,out existing);
                current.Counts[key]=existing+count;
            }
            catch { }
        }

        private sealed class Measurement : IDisposable
        {
            internal readonly string Context;
            internal readonly Stopwatch Watch=Stopwatch.StartNew();
            internal readonly Dictionary<string,double> Milliseconds=new Dictionary<string,double>();
            internal readonly Dictionary<string,int> Counts=new Dictionary<string,int>();
            internal readonly List<string> Notes=new List<string>();
            internal Measurement(string context) { Context=context; }
            public void Dispose()
            {
                try
                {
                    Watch.Stop();
                    if(ReferenceEquals(current,this)) current=null;
                    Write(Summary());
                }
                catch { }
            }
            private string Summary()
            {
                var text=new StringBuilder();
                text.Append('[').Append(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff",
                    CultureInfo.InvariantCulture)).Append("] ").Append(Context);
                text.Append(" | 总计 ").Append(Watch.Elapsed.TotalMilliseconds.ToString("0.0",
                    CultureInfo.InvariantCulture)).Append(" ms");
                foreach(var note in Notes) text.Append(" | ").Append(note);
                foreach(var pair in Counts)
                {
                    if(pair.Key.EndsWith("@调用",StringComparison.Ordinal)) continue;
                    text.Append(" | ").Append(pair.Key).Append(' ')
                        .Append(pair.Value.ToString(CultureInfo.InvariantCulture));
                }
                foreach(var pair in Milliseconds)
                {
                    int calls;
                    Counts.TryGetValue(pair.Key+"@调用",out calls);
                    text.Append(" | ").Append(pair.Key).Append(' ')
                        .Append(pair.Value.ToString("0.0",CultureInfo.InvariantCulture))
                        .Append(" ms×").Append(calls.ToString(CultureInfo.InvariantCulture));
                }
                return text.ToString();
            }
            internal void Add(string label,double milliseconds)
            {
                double total;
                Milliseconds.TryGetValue(label,out total);
                Milliseconds[label]=total+milliseconds;
                int calls;
                Counts.TryGetValue(label+"@调用",out calls);
                Counts[label+"@调用"]=calls+1;
            }
        }

        private sealed class Step : IDisposable
        {
            private readonly string label;
            private readonly Measurement owner;
            private readonly Stopwatch watch=Stopwatch.StartNew();
            internal Step(string label,Measurement owner) { this.label=label; this.owner=owner; }
            public void Dispose()
            {
                try { watch.Stop(); owner.Add(label,watch.Elapsed.TotalMilliseconds); }
                catch { }
            }
        }

        private sealed class Noop : IDisposable
        {
            internal static readonly Noop Instance=new Noop();
            public void Dispose() { }
        }

        private static void Write(string line)
        {
            try
            {
                string directory=Path.Combine(Environment.GetFolderPath(
                    Environment.SpecialFolder.LocalApplicationData),"SteelSectionProbe");
                if(!Directory.Exists(directory)) Directory.CreateDirectory(directory);
                File.AppendAllText(Path.Combine(directory,"statistics_trace.log"),
                    line+Environment.NewLine,Encoding.UTF8);
            }
            catch { }
        }
    }
}
