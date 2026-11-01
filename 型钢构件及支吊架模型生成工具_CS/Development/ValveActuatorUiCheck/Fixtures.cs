using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using Forms = System.Windows.Forms;

namespace Bentley.ECObjects.Instance
{
    internal interface IECInstance { FakeClass ClassDefinition { get; } FakeValue this[string name] { get; } }
    internal sealed class FakeValue
    {
        internal int IntValue;
        internal string StringValue;
        internal double DoubleValue;
        internal object NativeValue;
    }
    internal sealed class FakeType { internal string Name; }
    internal sealed class FakeProperty { internal string Name; internal FakeType Type; }
    internal sealed class FakeClass
    {
        internal IEnumerable<FakeProperty> Properties(bool inherited)
        {
            foreach (string name in SteelSectionProbe.ActuatorCelInstanceData.SizeFields)
                yield return new FakeProperty { Name = name, Type = new FakeType { Name = name == "TOTAL_HEIGHT" ? "string" : "double" } };
            foreach (string name in new[] { "ANGLE", "HANDLE_OFFSET", "LENGTH", "DIAMETER" })
                yield return new FakeProperty { Name = name, Type = new FakeType { Name = "double" } };
        }
    }
    internal sealed class FakeInstance : IECInstance
    {
        private readonly Dictionary<string, FakeValue> values = new Dictionary<string, FakeValue>();
        public FakeClass ClassDefinition { get; } = new FakeClass();
        public FakeValue this[string name] { get { if (!values.ContainsKey(name)) values[name] = new FakeValue(); return values[name]; } }
    }
}

namespace SteelSectionProbe
{
    internal sealed class MainWindow : Forms.Form
    {
        internal static MainWindow Current;
        internal void SetStatus(string message, bool error) { }
        internal void BeginTitleDrag() { }
        internal void MinimizeFromHome() { }
        internal void ShowHome() { }
    }
    internal sealed class CelLibraryPreviewControl : Border
    {
        internal event Action<string> Failed;
        internal static bool Fail;
        internal void ShowCell(CelLibraryEntry entry, double angle)
        { if (Fail) throw new InvalidOperationException("preview failed"); Child = new TextBlock { Text = "离线界面检查：" + entry.Name, TextWrapping = TextWrapping.Wrap }; }
        internal void Clear(string text) { Child = new TextBlock { Text = text }; }
        internal void SetTopView(bool top) { }
    }
    internal static class CelLibraryReader
    {
        internal static bool Fail;
        internal static Action DuringRead;
        internal static string ValidatePath(string path)
        { if (!File.Exists(path)) throw new FileNotFoundException(); return path; }
        internal static CelLibraryCatalog Read(string path)
        {
            DuringRead?.Invoke();
            if (Fail) throw new InvalidOperationException("unreadable CEL");
            return new CelLibraryCatalog(path, new List<CelLibraryEntry> {
                Entry(path,"执行机构 A"), Entry(path,"执行机构 B") }, 0);
        }
        internal static CelLibraryEntry Entry(string path, string name, string unit = "mm", double uor = 1000, bool point = false, double origin = 0)
        { return new CelLibraryEntry(path, name, "", true, point, origin, 0, 0, unit, uor); }
    }
    internal static class ValveActuatorPlacement
    {
        internal static bool IsActive, FailEnd;
        internal static int Starts, Ends;
        internal static string LastCell;
        internal static string Start(CelLibraryEntry entry)
        { if (entry == null) throw new Exception("missing selection"); IsActive = true; Starts++; LastCell = entry.Name; return "请点选阀门"; }
        internal static void End() { if (FailEnd) throw new Exception("exit failed"); IsActive = false; Ends++; }
        internal static void CheckContext() { }
    }
    internal static class ValveActuatorLog { internal static void Write(string stage, string text) { } }
}
