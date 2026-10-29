using System;
using System.Collections.Generic;
using System.Linq;

// 仅验证真实业务代码的控制流；不声称替身能验证 Bentley COM 的实际持久化行为。
namespace EquipmentLevelCheck
{
    internal sealed class State
    {
        internal ulong Id;
        internal bool Cell, Complex, Shared, Locked, BlockWrite, ThrowWrite, FailEnumeration;
        internal bool NullLevel, ThrowLevelRead, NullCellCast, NullComplexCast;
        internal bool Smart, RejectStaleWrite;
        internal bool NullSharedCast, OverrideLevel, OverrideColor, BlockLevelOverride, BlockColorOverride;
        internal string SharedName = "PUMP_PART";
        internal bool Graphic = true;
        internal int Level = 1, Color = 7;
        internal string Type = "Solid";
        internal List<ulong> Children = new List<ulong>();
        internal State Copy()
        {
            var copy = (State)MemberwiseClone();
            copy.Children = new List<ulong>(Children);
            return copy;
        }
    }

    internal static class Store
    {
        internal static Dictionary<ulong, State> Data;
        internal static Dictionary<ulong, State> Saved;
        internal static List<ulong> Writes;
        internal static List<ulong> SmartWrites;
        internal static List<ulong> SharedWrites;
        internal static bool ReturnOuterCell;
        internal static Dictionary<ulong, ulong> LookupRedirects;
        internal static int Revision;
        internal static List<string> Logs;
        internal static bool FailRollback, NoOpRollback, UndoInProgress;
        internal static int Marks, Commits, Cancels;
        internal static Action<ulong> AfterRewrite;
        internal static Bentley.DgnPlatformNET.DgnModel ActiveModel;
        internal static List<Bentley.DgnPlatformNET.LevelHandle> LevelHandles;
        internal static State Add(ulong id, bool cell = false, params ulong[] children)
        {
            var state = new State { Id = id, Cell = cell, Complex = cell, Type = cell ? "Cell" : "Solid" };
            state.Children.AddRange(children);
            Data.Add(id, state);
            return state;
        }
        internal static void Reset()
        {
            Data = new Dictionary<ulong, State>();
            Writes = new List<ulong>();
            SmartWrites = new List<ulong>();
            SharedWrites = new List<ulong>();
            ReturnOuterCell = true;
            LookupRedirects = new Dictionary<ulong, ulong>();
            Revision = 0;
            Logs = new List<string>();
            Saved = null;
            FailRollback = NoOpRollback = UndoInProgress = false;
            Marks = Commits = Cancels = 0;
            AfterRewrite = null;
            ActiveModel = new Bentley.DgnPlatformNET.DgnModel();
            LevelHandles = new List<Bentley.DgnPlatformNET.LevelHandle>();
            Bentley.MstnPlatformNET.SelectionSetManager.Items.Clear();
            Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp = new Bentley.Interop.MicroStationDGN.Application();
        }
        internal static Dictionary<ulong, State> Clone()
        {
            return Data.ToDictionary(p => p.Key, p => p.Value.Copy());
        }
        internal static Bentley.Interop.MicroStationDGN.Element Read(ulong id)
        {
            State state;
            if (!Data.TryGetValue(id, out state)) return null;
            // 每次读取都创建新包装；未 Rewrite 的 setter 不影响持久状态。
            return state.Shared ? new Bentley.Interop.MicroStationDGN.SharedCellElement(state.Copy()) :
                state.Smart ? new Bentley.Interop.MicroStationDGN.SmartSolidElement(state.Copy()) :
                state.Cell ? new Bentley.Interop.MicroStationDGN.CellElement(state.Copy()) :
                state.Complex ? new Bentley.Interop.MicroStationDGN.ComplexElement(state.Copy()) :
                new Bentley.Interop.MicroStationDGN.Element(state.Copy());
        }
    }
}

namespace Bentley.Interop.MicroStationDGN
{
    using EquipmentLevelCheck;
    internal class Level
    {
        internal int ID { get; set; }
        internal bool IsLocked { get; set; }
        internal int ElementColor { get; set; }
    }
    internal sealed class Levels
    {
        internal Level Target = new Level { ID = 2 };
        internal Dictionary<string, Level> Other = new Dictionary<string, Level>();
        internal Level Find(string name) { Level value; return name == "equipment" ? Target : Other.TryGetValue(name, out value) ? value : null; }
    }
    internal sealed class Application
    {
        internal ModelReference ActiveModelReference = new ModelReference();
        internal int ByLevelColor() { return -1; }
    }
    internal sealed class ModelReference
    {
        internal Levels Levels = new Levels();
        internal int InternalColorFromRGBColor(int color) { return color | 0x1000000; }
        internal int InternalColorToRGBColor(int color) { return color & 0xFFFFFF; }
        internal Element GetElementByID64(long id)
        {
            ulong requested = checked((ulong)id);
            ulong current;
            if (Store.LookupRedirects.TryGetValue(requested, out current)) return Store.Read(current);
            current = requested;
            if (Store.ReturnOuterCell)
            {
                var visited = new HashSet<ulong> { current };
                while (true)
                {
                    var parent = Store.Data.Values.FirstOrDefault(s => !s.Shared && !s.Smart &&
                        (s.Cell || s.Complex) && s.Children.Contains(current));
                    if (parent == null) break;
                    if (!visited.Add(parent.Id)) return Store.Read(requested); // 成环由真实 Tree 检查。
                    current = parent.Id;
                }
            }
            return Store.Read(current);
        }
    }
    internal class Element
    {
        protected readonly State state;
        private readonly int revision;
        internal Element(State value) { state = value; revision = Store.Revision; }
        internal long ID64 { get { return checked((long)state.Id); } }
        internal string Type { get { return state.Type; } }
        internal bool IsGraphical { get { return state.Graphic; } }
        internal bool IsLocked { get { return state.Locked; } }
        internal bool IsCellElement() { return state.Cell; }
        internal bool IsComplexElement() { return state.Complex; }
        internal bool IsComplexStringElement() { return state.Type == "ComplexString"; }
        internal bool IsComplexShapeElement() { return state.Type == "ComplexShape"; }
        internal bool IsSmartSolidElement { get { return state.Smart; } }
        internal SmartSolidElement AsSmartSolidElement { get { return state.Smart ? (SmartSolidElement)this : null; } }
        internal bool IsSharedCellElement() { return state.Shared; }
        internal SharedCellElement AsSharedCellElement() { return state.NullSharedCast ? null : (SharedCellElement)this; }
        internal CellElement AsCellElement() { return state.NullCellCast ? null : (CellElement)this; }
        internal ComplexElement AsComplexElement() { return state.NullComplexCast ? null : (ComplexElement)this; }
        internal Level Level
        {
            get
            {
                if (state.ThrowLevelRead) throw new NullReferenceException("simulated missing layer attribute");
                return state.NullLevel ? null : new Level { ID = state.Level };
            }
            set { state.Level = value.ID; }
        }
        internal int Color { get { return state.Color; } set { state.Color = value; } }
        internal void Rewrite()
        {
            Store.Writes.Add(state.Id);
            if (state.RejectStaleWrite && revision != Store.Revision) throw new InvalidOperationException("stale COM component wrapper");
            if (state.ThrowWrite) throw new InvalidOperationException("simulated rewrite failure");
            if (state.BlockWrite) return;
            Store.Data[state.Id].Level = state.Level;
            Store.Data[state.Id].Color = state.Color;
            if (!state.BlockLevelOverride) Store.Data[state.Id].OverrideLevel = state.OverrideLevel;
            if (!state.BlockColorOverride) Store.Data[state.Id].OverrideColor = state.OverrideColor;
            Store.Revision++;
            if (Store.AfterRewrite != null) Store.AfterRewrite(state.Id);
        }
    }
    internal class ComplexElement : Element
    {
        internal ComplexElement(State value) : base(value) { }
        internal ElementEnumerator GetSubElements()
        {
            if (state.FailEnumeration) throw new InvalidOperationException("simulated unreadable cell");
            return new ElementEnumerator(state.Children);
        }
    }
    internal sealed class CellElement : ComplexElement
    {
        internal CellElement(State value) : base(value) { }
    }
    internal sealed class SmartSolidElement : ComplexElement
    {
        internal SmartSolidElement(State value) : base(value) { }
        internal new void Rewrite() { Store.SmartWrites.Add(state.Id); base.Rewrite(); }
    }
    internal sealed class SharedCellElement : ComplexElement
    {
        internal SharedCellElement(State value) : base(value) { }
        internal string Name { get { return state.SharedName; } }
        internal bool OverridesComponentLevel { get { return state.OverrideLevel; } set { state.OverrideLevel = value; } }
        internal bool OverridesComponentColor { get { return state.OverrideColor; } set { state.OverrideColor = value; } }
        internal new void Rewrite() { Store.SharedWrites.Add(state.Id); base.Rewrite(); }
    }
    internal sealed class ElementEnumerator
    {
        private readonly List<ulong> ids;
        private int index = -1;
        internal ElementEnumerator(List<ulong> values) { ids = new List<ulong>(values); }
        internal bool MoveNext() { return ++index < ids.Count; }
        internal Element Current { get { return Store.Read(ids[index]); } }
    }
}

namespace Bentley.MstnPlatformNET.InteropServices
{
    internal static class Utilities
    {
        internal static Bentley.Interop.MicroStationDGN.Application ComApp;
    }
}

namespace Bentley.DgnPlatformNET
{
    using EquipmentLevelCheck;
    internal sealed class DgnModel
    {
        internal bool IsReadOnly;
        internal DgnFile File = new DgnFile();
        internal DgnFile GetDgnFile() { return File; }
        internal ModelInfo GetModelInfo() { return new ModelInfo(); }
        internal Elements.Element FindElementById(ElementId id)
        { return Store.Data.ContainsKey(id.Value) ? new Elements.Element { ElementId = id.Value, DgnModelRef = new DgnModelRef { Model = this } } : null; }
    }
    internal sealed class ModelInfo { internal string Name = "Default"; }
    internal sealed class DgnModelRef { internal DgnModel Model; }
    internal sealed class DgnFile
    {
        internal bool IsReadOnly;
        internal string FileName = "fixtures.dgn";
        internal FileLevelCache GetLevelCache() { return new FileLevelCache(); }
        internal string GetFileName() { return FileName; }
    }
    internal sealed class FileLevelCache
    { internal IEnumerable<LevelHandle> GetHandles() { return Store.LevelHandles; } }
    internal sealed class LevelHandle
    {
        internal bool IsValid = true, ReadOnly;
        internal LevelId LevelId;
        internal string Name;
    }
    internal struct ElementId
    {
        internal ulong Value;
        internal ElementId(ref ulong id) { Value = id; }
    }
    internal struct LevelId
    {
        private uint value;
        internal LevelId(uint id) { value = id; }
        public static explicit operator uint(LevelId id) { return id.value; }
    }
    internal enum StatusInt { Success, Error }
    internal struct TransactionPosition { }
    internal static class TransactionManager
    {
        internal static bool IsUndoInProgress { get { return Store.UndoInProgress; } }
        internal static bool IsActive { get { return true; } }
        internal static void Activate() { }
        internal static TransactionPosition CurrentTransactionPosition
        {
            get { Store.Marks++; Store.Saved = Store.Clone(); return new TransactionPosition(); }
        }
        internal static void CloseCurrentTransaction(bool commit) { Store.Commits++; }
        internal static StatusInt CancelToPosition(TransactionPosition position, bool undo)
        {
            Store.Cancels++;
            if (Store.FailRollback) return StatusInt.Error;
            if (!Store.NoOpRollback) Store.Data = Store.Saved;
            return StatusInt.Success;
        }
    }
}

namespace Bentley.DgnPlatformNET.Elements
{
    internal sealed class Element
    {
        internal ulong ElementId;
        internal bool IsValid = true;
        internal Bentley.DgnPlatformNET.DgnModelRef DgnModelRef;
    }
}
namespace Bentley.MstnPlatformNET
{
    using Bentley.DgnPlatformNET;
    using Bentley.DgnPlatformNET.Elements;
    internal static class Settings { internal static LevelId ActiveLevelId = new LevelId(2); }
    internal static class SelectionSetManager
    {
        internal static readonly List<Element> Items = new List<Element>();
        internal static bool IsActive() { return Items.Count > 0; }
        internal static uint NumSelected() { return (uint)Items.Count; }
        internal static StatusInt GetElement(uint index, ref Element element, ref DgnModelRef model)
        { element = Items[(int)index]; model = element == null ? null : element.DgnModelRef; return element == null ? StatusInt.Error : StatusInt.Success; }
    }
}

namespace SteelSectionProbe
{
    internal static class EquipmentLevelReader
    {
        internal static Bentley.DgnPlatformNET.DgnModel ActiveModel()
        { return EquipmentLevelCheck.Store.ActiveModel; }
        internal static EquipmentLevelEntry Classify(Bentley.DgnPlatformNET.DgnModelRef model, ulong id)
        {
            bool reference = model == null || !ReferenceEquals(model.Model, EquipmentLevelCheck.Store.ActiveModel);
            bool cell = EquipmentLevelCheck.Store.Data[id].Cell;
            return new EquipmentLevelEntry { ElementId = id, Name = "Equipment " + id,
                Verdict = reference ? EquipmentLevelVerdict.FromReference : cell ? EquipmentLevelVerdict.Equipment : EquipmentLevelVerdict.NotEquipment,
                Reason = reference ? "参考文件" : cell ? "" : "不是设备" };
        }
    }
    internal static class EquipmentLevelLog
    {
        internal static void Write(string text) { EquipmentLevelCheck.Store.Logs.Add(text); }
        internal static void WriteTree(string text) { }
    }
}
