using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static class World
    {
        internal static Dictionary<ulong, Element> Elements;
        internal static Dictionary<string, IECInstance> Instances;
        internal static List<IECInstance> Selected;
        internal static PipeClampSelection Pipe;
        internal static IECInstance Source;
        internal static BMECObject Created;
        internal static string Fault;
        internal static bool FailRollback;
        internal static ulong Next;
        internal static double SupportPointMmPerUnit;
        internal static void Reset()
        {
            Elements = new Dictionary<ulong, Element>(); Instances = new Dictionary<string, IECInstance>();
            Next = 10; Fault = ""; FailRollback = false; Created = null; LicenseService.IsActivated = true;
            ItemTypeLibrary.Last = null;
            Bentley.MstnPlatformNET.Session.Instance.Model = new DgnModel();
            TransactionManager.IsActive = true; TransactionManager.IsUndoInProgress = false;
            Source = new IECInstance("PIPE", "pipe-1"); Source["NOMINAL_DIAMETER"].DoubleValue = 100;
            Source["SPECIFICATION"].StringValue = "TEST-SPEC";
            var element = new Element { ElementId = 1, Model = Bentley.MstnPlatformNET.Session.Instance.Model, Instance = Source };
            Elements[1] = element; Instances[Source.InstanceId] = Source; Selected = new List<IECInstance> { Source };
            Pipe = new PipeClampSelection { ElementId = 1, IsPipe = true, NominalMm = 100, OutsideMm = 114.3,
                StartX = 1000, StartY = 2000, StartZ = 3000, EndX = 2000, EndY = 2000, EndZ = 3000 };
            BMECApi.Instance.ObjectCache = new BMECObjectCache();
            BMECApi.Instance.DeferCommits = false;
            SupportPointMmPerUnit = 1;
        }
        internal static Element Find(IECInstance instance) { return Elements.Values.SingleOrDefault(e => e.Instance == instance); }
    }
    internal static class LicenseService { internal static bool IsActivated = true; }
    internal static class PipeClampReader { internal static PipeClampSelection Read(ulong id, double x, double y, double z) { return World.Pipe; } }
    internal static class A1ClampBuilder
    { internal static List<Element> Build(A1ClampPlan plan, DPoint3d origin, DVector3d axis) { return Enumerable.Range(0, 5).Select(i => new Element()).ToList(); } }
    internal static class Statistics
    { internal static void AttachA1Clamp(Element element, A1ClampPlan plan) { if (World.Fault == "Statistics") throw new Exception("统计失败"); element.MaterialTag = plan.AssemblyTag; } }
    internal static class A1NativeGraphics
    {
        internal static void Create(BMECObject support, Element graphics, DTransform3d placement, Action<string> log, Action finish)
        {
            World.Created = support;
            if (World.Fault == "Create") throw new Exception("Create失败");
            support.Transform3d = placement;
            if (World.Fault == "WrongOrigin") support.Transform3d = new DTransform3d(placement.Matrix) { Translation = new DPoint3d(placement.Translation.X + 10000, placement.Translation.Y, placement.Translation.Z) };
            support.Instance.Parametric = World.Fault == "Parametric";
            support.Instance.Parent = World.Fault == "Relationship" ? null : support.RelatedInstance;
            // Native Create may succeed while only enqueuing when the host defers commits.
            if (!BMECApi.Instance.DeferCommits)
            {
                support.Instance.InstanceId = "trial-" + Guid.NewGuid().ToString("N");
                var element = new Element { ElementId = World.Next++, Model = Bentley.MstnPlatformNET.Session.Instance.Model, Instance = support.Instance };
                World.Elements[element.ElementId] = element; World.Instances[support.Instance.InstanceId] = support.Instance;
            }
            if (!new BMECObjectWriter(support).Serialize()) throw new Exception("Serialize失败");
            finish();
        }
    }
}
namespace Bentley.GeometryNET
{
    internal struct DPoint3d { public double X, Y, Z; public DPoint3d(double x, double y, double z) { X = x; Y = y; Z = z; } public static DPoint3d Zero { get { return new DPoint3d(); } } }
    internal struct DVector3d { public double X, Y, Z; public DVector3d(double x, double y, double z) { X = x; Y = y; Z = z; } }
    internal struct DMatrix3d { public DVector3d X, Y, Z; public static DMatrix3d Identity { get { return FromColumns(new DVector3d(1, 0, 0), new DVector3d(0, 1, 0), new DVector3d(0, 0, 1)); } } public static DMatrix3d FromColumns(DVector3d x, DVector3d y, DVector3d z) { return new DMatrix3d { X = x, Y = y, Z = z }; } }
    internal struct DTransform3d { public DMatrix3d Matrix; public DPoint3d Translation; public DTransform3d(DMatrix3d rotation) { Matrix = rotation; Translation = new DPoint3d(); } }
}
namespace Bentley.ECObjects.Instance
{
    internal sealed class Value
    {
        private object value;
        public bool IsNull { get { return value == null; } }
        internal void Clear() { value = null; }
        public string StringValue { get { if (value is double) throw new InvalidOperationException(); return value as string; } set { this.value = value; } }
        public double DoubleValue { get { return value is double ? (double)value : 0; } set { this.value = value; } }
    }
    internal sealed class Definition
    {
        public string Name;
        public Definition Type { get { return new Definition { Name = Name == "NOMINAL_DIAMETER" ? "double" : "string" }; } }
        public IEnumerable<Definition> Properties(bool includeBase)
        { return new[] { "NAME", "DESCRIPTION", "SPECIFICATION", "UBOLT_DIAMETER", "UBOLT_LENGTH", "UBOLT_WIDTH", "NOMINAL_DIAMETER", "STATE", "SHOP_FIELD", "SUPPORT_POINT_X", "SUPPORT_POINT_Y", "SUPPORT_POINT_Z" }
            .Where(n => SteelSectionProbe.World.Fault != "MissingIsoProperty" || n != "SUPPORT_POINT_X").Select(n => new Definition { Name = n }); }
    }
    internal sealed class IECInstance
    {
        public string InstanceId;
        public Definition ClassDefinition;
        internal IECInstance Parent;
        internal bool Parametric;
        internal DTransform3d Transform;
        private readonly Dictionary<string, Value> values = new Dictionary<string, Value>();
        internal IECInstance(string type, string id) { ClassDefinition = new Definition { Name = type }; InstanceId = id; }
        public Value this[string key] { get { Value found; if (!values.TryGetValue(key, out found)) values[key] = found = new Value(); return found; } }
    }
}
namespace Bentley.DgnPlatformNET
{
    internal enum StatusInt { Success, Error }
    internal class DgnModelRef { public static unsafe void* GetNativeDgnModelRefP(DgnModelRef model, bool allowNull) { return (void*)((DgnModel)model).Handle; } }
    internal sealed class DgnModel : DgnModelRef { public bool Is3d = true; public int Handle = 1; public double Scale = 1000; public ModelInfo GetModelInfo() { return new ModelInfo { UorPerMeter = Scale * 1000 }; } }
    internal sealed class ModelInfo { public double UorPerMeter; }
    internal static class TransactionManager
    {
        public static bool IsUndoInProgress, IsActive;
        private static HashSet<ulong> before;
        public static void Activate() { IsActive = true; }
        public static void CloseCurrentTransaction(bool commit) { }
        public static int CurrentTransactionPosition { get { before = new HashSet<ulong>(SteelSectionProbe.World.Elements.Keys); return 1; } }
        public static StatusInt CancelToPosition(int mark, bool restart)
        {
            if (SteelSectionProbe.World.FailRollback) return StatusInt.Error;
            foreach (ulong id in SteelSectionProbe.World.Elements.Keys.Where(id => !before.Contains(id)).ToArray()) SteelSectionProbe.World.Elements.Remove(id);
            return StatusInt.Success;
        }
    }
    internal sealed class CustomProperty { public enum TypeKind { String } public TypeKind Type; }
    internal sealed class ItemType { public CustomProperty AddProperty(string name, bool array) { return new CustomProperty(); } }
    internal sealed class ItemTypeLibrary
    {
        private ItemType type;
        public static ItemTypeLibrary FindByName(string name, object file) { return Last; }
        internal static ItemTypeLibrary Last;
        public static ItemTypeLibrary Create(string name, object file, bool external) { return Last = new ItemTypeLibrary(); }
        public ItemType GetItemTypeByName(string name) { return type ?? (Last == null ? null : Last.type); }
        public ItemType AddItemType(string name, bool hidden) { return type = new ItemType(); }
        public bool Write() { return true; }
    }
    internal sealed class CustomItemHost
    {
        private readonly Element element;
        public CustomItemHost(Element element, bool schedule) { this.element = element; }
        public ItemInstance ApplyCustomItem(ItemType type) { return element.Metadata = new ItemInstance(); }
        public ItemInstance GetCustomItem(string library, string type) { return element.Metadata; }
    }
    internal sealed class ItemInstance
    {
        private readonly Dictionary<string, Value> values = new Dictionary<string, Value>();
        public Value this[string key] { get { Value value; if (!values.TryGetValue(key, out value)) values[key] = value = new Value(); return value; } }
        public StatusInt WriteChanges() { return SteelSectionProbe.World.Fault == "Metadata" ? StatusInt.Error : StatusInt.Success; }
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    internal class Element : IDisposable
    {
        internal DgnModel Model;
        internal IECInstance Instance;
        internal ItemInstance Metadata;
        internal string MaterialTag;
        internal bool Locked;
        public ulong ElementId;
        public bool IsValid { get { return true; } }
        public static Element GetFromElementRef(IntPtr reference) { Element element; SteelSectionProbe.World.Elements.TryGetValue((ulong)reference.ToInt64(), out element); return element; }
        public IntPtr GetNativeDgnModelRef() { return (IntPtr)Model.Handle; }
        public bool IsEffectivelyLocked(bool parents, bool children) { return Locked; }
        public void Dispose() { }
    }
    internal sealed class CellHeaderElement : Element { public CellHeaderElement(DgnModel model, string name, DPoint3d origin, DMatrix3d orientation, List<Element> elements) { Model = model; } }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session { public static Session Instance = new Session(); public DgnModel Model = new DgnModel(); public DgnModel GetActiveDgnModel() { return Model; } public object GetActiveDgnFile() { return this; } }
}
namespace Bentley.OpenPlant.Modeler.Api
{
    internal sealed class BMECObject : IDisposable
    {
        internal bool Disposed;
        public IECInstance Instance, RelatedInstance;
        public BMECObject(IECInstance instance, bool nonParametric) { Instance = instance; }
        public bool IsValid { get { return !Disposed; } }
        public bool IsParametric { get { return Instance.Parametric; } }
        public DTransform3d Transform3d { get { return Instance.Transform; } set { Instance.Transform = value; } }
        public bool SetDoubleValueFromMM(string name, double value)
        {
            if (SteelSectionProbe.World.Fault == "IsoPointWrite") return false;
            Instance[name].DoubleValue = value / SteelSectionProbe.World.SupportPointMmPerUnit; return true;
        }
        public double GetDoubleValueInMM(string name) { return Instance[name].DoubleValue * SteelSectionProbe.World.SupportPointMmPerUnit; }
        public void Dispose() { Disposed = true; }
    }
    internal sealed class BMECInstanceManager
    { public static BMECInstanceManager Instance = new BMECInstanceManager(); public IECInstance CreateECInstance(string type, bool defaults) { return new IECInstance(type, "mechanical"); } }
    internal sealed class BMECObjectWriter
    {
        private readonly BMECObject support;
        public BMECObjectWriter(BMECObject support) { this.support = support; }
        public bool Serialize()
        {
            if (SteelSectionProbe.World.Fault == "IsoPointDropped") support.Instance["SUPPORT_POINT_X"].DoubleValue = 0;
            if (SteelSectionProbe.World.Fault == "StateDropped") support.Instance["STATE"].Clear();
            return SteelSectionProbe.World.Fault != "Serialize";
        }
    }
    internal sealed class BMECObjectCache
    {
        private BMECObject value;
        public int Add(BMECObject support) { if (SteelSectionProbe.World.Fault == "Cache") return -1; value = support; return 1; }
        public void Remove(int key) { value = null; }
        public BMECObject FindByInstanceId(string id) { return value != null && value.Instance.InstanceId == id ? value : null; }
    }
    internal sealed class BMECApi
    {
        public static BMECApi Instance = new BMECApi(); public BMECObjectCache ObjectCache = new BMECObjectCache();
        public bool DeferCommits;
        public bool IsPersistentId(string id) { return id != null && id.StartsWith("trial-"); }
        public unsafe void* GetElementRef(IECInstance instance) { var element = SteelSectionProbe.World.Find(instance); return element == null ? null : (void*)element.ElementId; }
        public bool IsInstanceModifiable(IECInstance instance) { return true; }
        public IECInstance FindAllInformationOnInstance(IECInstance instance) { return instance; }
        // Real nonparametric UBOLT_GUIDE left these zero; do not fake automatic positioning.
        public void GetSectionalDataForSupport(IECInstance instance) { instance["SUPPORT_POINT_X"].DoubleValue = 0; instance["SUPPORT_POINT_Y"].DoubleValue = 0; instance["SUPPORT_POINT_Z"].DoubleValue = 0; }
        public List<IECInstance> GetRelatedInstances(IECInstance support, string name, bool forward, bool polymorphic)
        { if (name != "DEVICE_HAS_SUPPORT" || forward) throw new Exception("错误关系方向"); return support.Parent == null ? new List<IECInstance>() : new List<IECInstance> { support.Parent }; }
    }
}
namespace Bentley.OpenPlantModeler.SDK.Utilities
{ internal static class DgnUtilities { public static List<IECInstance> GetSelectedInstances() { return SteelSectionProbe.World.Selected; } } }
namespace SteelSectionProbe.PipeAlignment
{
    internal static class OpenPlantObjectFactory
    {
        internal sealed class Acquired : IDisposable { public BMECObject Object; public void Dispose() { } }
        public static Acquired Acquire(string id, IECInstance instance) { return new Acquired { Object = BMECApi.Instance.ObjectCache.FindByInstanceId(id) }; }
    }
}
