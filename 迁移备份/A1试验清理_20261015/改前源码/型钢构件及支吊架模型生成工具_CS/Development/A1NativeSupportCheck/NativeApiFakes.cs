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
        internal static HashSet<Bentley.Interop.MicroStationDGN.TransientElementContainer> Displays;
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
            Displays = new HashSet<Bentley.Interop.MicroStationDGN.TransientElementContainer>();
            Pipe.NativePipeInstanceId=Source.InstanceId;Pipe.NativeModelToken=1;Pipe.SourceUorPerMm=1000;
        }
        internal static Element Find(IECInstance instance) { return Elements.Values.SingleOrDefault(e => e.Instance == instance); }
    }
    internal static class LicenseService { internal static bool IsActivated = true; }
    internal static class PipeClampReader { internal static PipeClampSelection Read(ulong id, double x, double y, double z) { return World.Pipe; } }
    internal static class A1ClampBuilder
    { internal static List<Element> Build(A1ClampPlan plan, DPoint3d origin, DVector3d axis) { return Enumerable.Range(0, 5).Select(i => new Element { Geometry=new[]{origin,new DPoint3d(origin.X+i+1,origin.Y+i+2,origin.Z+i+3)} }).ToList(); } }
    internal static partial class Statistics
    { internal static void AttachA1Clamp(Element element, A1ClampPlan plan) { if (World.Fault == "Statistics") throw new Exception("统计失败"); element.MaterialTag = plan.AssemblyTag; } }
    internal static class NativeSupportGraphics
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
                var element = new Element { ElementId = World.Next++, Model = Bentley.MstnPlatformNET.Session.Instance.Model, Instance = support.Instance,
                    Geometry=graphics.Geometry.Select(placement.Apply).ToArray(),CellName=graphics.CellName };
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
    internal struct DMatrix3d { public DVector3d X, Y, Z; public DVector3d ColumnX { get { return X; } } public static DMatrix3d Identity { get { return FromColumns(new DVector3d(1, 0, 0), new DVector3d(0, 1, 0), new DVector3d(0, 0, 1)); } } public static DMatrix3d FromColumns(DVector3d x, DVector3d y, DVector3d z) { return new DMatrix3d { X = x, Y = y, Z = z }; } }
    internal struct DTransform3d
    {
        public DMatrix3d Matrix; public DPoint3d Translation;
        public DTransform3d(DMatrix3d rotation) { Matrix = rotation; Translation = new DPoint3d(); }
        public DPoint3d Apply(DPoint3d p) { return new DPoint3d(Matrix.X.X*p.X+Matrix.Y.X*p.Y+Matrix.Z.X*p.Z+Translation.X, Matrix.X.Y*p.X+Matrix.Y.Y*p.Y+Matrix.Z.Y*p.Z+Translation.Y, Matrix.X.Z*p.X+Matrix.Y.Z*p.Y+Matrix.Z.Z*p.Z+Translation.Z); }
    }
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
        public int IntValue { get { return value is int ? (int)value : 0; } set { this.value = value; } }
    }
    internal sealed class Definition
    {
        public string Name;
        internal bool NominalString;
        public Definition Type { get { return new Definition { Name = Name == "NOMINAL_DIAMETER" && !NominalString ? "double" : "string" }; } }
        public IEnumerable<Definition> Properties(bool includeBase)
          { return new[] { "NAME", "DEVICE_TYPE_CODE", "NUMBER", "ALIAS", "DESCRIPTION", "SPECIFICATION", "UBOLT_DIAMETER", "UBOLT_LENGTH", "UBOLT_WIDTH", "NOMINAL_DIAMETER", "STATE", "SHOP_FIELD", "SUPPORT_POINT_X", "SUPPORT_POINT_Y", "SUPPORT_POINT_Z", "SSP_A1_DN", "SSP_A1_OPENING", "SSP_RECIPE", "TOTAL_HEIGHT", "SUPPORT_HEIGHT", "SUPPORT_DIAMETER", "BASE_LENGTH" }
            .Where(n => SteelSectionProbe.World.Fault != "MissingIsoProperty" || n != "SUPPORT_POINT_X").Select(n => new Definition { Name = n,NominalString=Name=="SUPPORT_LOCATION" || Name=="SSP_A1_NATIVE_TEST" || Name=="SSP_PIPE_CLAMP" }); }
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
    internal sealed class DgnModel : DgnModelRef { public bool Is3d = true; public int Handle = 1; public double Scale = 1000; public DgnFile File = new DgnFile(); public ModelInfo GetModelInfo() { return new ModelInfo { UorPerMeter = Scale * 1000 }; } public DgnFile GetDgnFile() { return File; } }
    internal sealed class TransformInfo { public DTransform3d Transform; public TransformInfo(DTransform3d transform){Transform=transform;} }
    internal sealed class ModelInfo { public double UorPerMeter; }
    internal struct LevelId { internal uint Value; public static explicit operator uint(LevelId id) { return id.Value; } }
    internal struct LevelHandle { internal bool IsValid; internal LevelId LevelId; }
    internal class LevelCache { }
    internal sealed class FileLevelCache : LevelCache
    {
        internal LevelHandle Existing;
        public LevelHandle GetLevelByName(string name) { return Existing.IsValid ? Existing : new LevelHandle(); }
        public LevelHandle CreateLevel(string name) { Existing = new LevelHandle { IsValid = true, LevelId = new LevelId { Value = 8 } }; return Existing; }
    }
    internal sealed class DgnFile { internal FileLevelCache Cache = new FileLevelCache(); public LevelCache GetLevelCache() { return Cache; } }
    internal sealed class ElementPropertiesSetter : System.IDisposable
    {
        public void SetLevel(LevelId level) { }
        public bool Apply(Elements.Element element) { return true; }
        public void Dispose() { }
    }
    internal static class TransactionManager
    {
        public static bool IsUndoInProgress, IsActive;
        private static Dictionary<ulong,Element> before;
        public static void Activate() { IsActive = true; }
        public static void CloseCurrentTransaction(bool commit) { }
        public static int CurrentTransactionPosition { get { before = new Dictionary<ulong,Element>(SteelSectionProbe.World.Elements); return 1; } }
        public static StatusInt CancelToPosition(int mark, bool restart)
        {
            if (SteelSectionProbe.World.FailRollback) return StatusInt.Error;
            foreach (ulong id in SteelSectionProbe.World.Elements.Keys.Where(id => !before.ContainsKey(id)).ToArray()) SteelSectionProbe.World.Elements.Remove(id);
            foreach(var pair in before)SteelSectionProbe.World.Elements[pair.Key]=pair.Value;
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
        internal DPoint3d[] Geometry=new DPoint3d[0];
        internal string CellName;
        public ulong ElementId;
        public bool IsValid { get { return true; } }
        public static Element GetFromElementRef(IntPtr reference) { Element element; SteelSectionProbe.World.Elements.TryGetValue((ulong)reference.ToInt64(), out element); return element; }
        public IntPtr GetNativeDgnModelRef() { return (IntPtr)Model.Handle; }
        public bool IsEffectivelyLocked(bool parents, bool children) { return Locked; }
        public StatusInt AddToModel(){ ElementId=SteelSectionProbe.World.Next++;Model=Bentley.MstnPlatformNET.Session.Instance.Model;SteelSectionProbe.World.Elements[ElementId]=this;return StatusInt.Success; }
        public StatusInt DeleteFromModel(){if(SteelSectionProbe.World.Fault=="PreviewDelete")return StatusInt.Error;SteelSectionProbe.World.Elements.Remove(ElementId);return StatusInt.Success;}
        public int ApplyTransform(TransformInfo transform){if(SteelSectionProbe.World.Fault=="Transform")return 1;Geometry=Geometry.Select(transform.Transform.Apply).ToArray();return 0;}
        public void Dispose() { }
    }
    internal sealed class CellHeaderElement : Element { public CellHeaderElement(DgnModel model, string name, DPoint3d origin, DMatrix3d orientation, IList<Element> elements) { Model = model;CellName=name;Geometry=elements.SelectMany(e=>e.Geometry).ToArray(); } }
}
namespace Bentley.MstnPlatformNET
{
    internal static class SettingsActivator { public static void SetActiveLevel(uint levelId) { } }
    internal sealed class Session { public static Session Instance = new Session(); public DgnModel Model = new DgnModel(); public DgnModel GetActiveDgnModel() { return Model; } public object GetActiveDgnFile() { return this; } }
}
namespace Bentley.OpenPlant.Modeler.Api
{
    internal sealed class BMECObject : IDisposable
    {
        internal bool Disposed;
        public IECInstance Instance, RelatedInstance;
#if A1_NATIVE_SETUP_CHECK
        private SteelSectionProbe.A1NativeParametricComponent component;
#endif
#if PIPE_CLAMP_NATIVE_CHECK
        private SteelSectionProbe.NativePipeSupportComponent nativeComponent;
#endif
        public BMECObject(IECInstance instance, bool nonParametric)
        {
            Instance = instance; Instance.Parametric = !nonParametric;
#if A1_NATIVE_SETUP_CHECK
            if (!nonParametric && instance.ClassDefinition.Name == "SSP_A1_NATIVE_TEST")
            {
                component = new SteelSectionProbe.A1NativeParametricComponent {
                    BMECObject = new SteelSectionProbe.ParametricSetupValues { Source = instance, ParentReady = false } };
                // The host's actual Init callback occurs here, not after RelatedInstance is assigned.
                component.Setup();
            }
#endif
#if PIPE_CLAMP_NATIVE_CHECK
            if (!nonParametric && (instance.ClassDefinition.Name == "SSP_PIPE_CLAMP" || instance.ClassDefinition.Name == "SSP_TRUNNION"
                || instance.ClassDefinition.Name == "SINGLE_PIPE_TRUNNION" || instance.ClassDefinition.Name == "DOUBLE_PIPE_TRUNNION"
                || instance.ClassDefinition.Name == "SIMPLE_ELBOW_SUPPORT"))
            {
                nativeComponent = new SteelSectionProbe.NativePipeSupportComponent {
                    BMECObject = new SteelSectionProbe.ParametricSetupValues { Source = instance, ParentReady = false } };
                nativeComponent.Setup();
            }
#endif
        }
        // Only models creation/persistence. No simulated native manipulation or automatic following.
        public int Create()
        {
            SteelSectionProbe.World.Created = this;
            if (SteelSectionProbe.World.Fault == "Create") return 1;
#if A1_NATIVE_SETUP_CHECK
            if (component != null)
            {
                component.BMECObject.ParentReady = RelatedInstance != null;
                component.PrepareGraphics();
            }
#endif
            if (BMECApi.Instance.IsPersistentId(Instance.InstanceId)) return 0;
#if PIPE_CLAMP_NATIVE_CHECK
            if (nativeComponent != null)
            {
                nativeComponent.BMECObject.ParentReady = RelatedInstance != null;
                nativeComponent.PrepareGraphics();
            }
#endif
            Instance.Parent = SteelSectionProbe.World.Fault == "Relationship" ? null : RelatedInstance;
            if (SteelSectionProbe.World.Fault == "Parametric") Instance.Parametric = false;
            if (SteelSectionProbe.World.Fault == "WrongOrigin")
            {
                var shifted = Transform3d; shifted.Translation.X += 10000; Transform3d = shifted;
            }
            if (!BMECApi.Instance.DeferCommits)
            {
                Instance.InstanceId = "trial-" + Guid.NewGuid().ToString("N");
                var element = new Element { ElementId = SteelSectionProbe.World.Next++, Model = Bentley.MstnPlatformNET.Session.Instance.Model, Instance = Instance };
#if PIPE_CLAMP_NATIVE_CHECK
                if (nativeComponent != null)
                    using (var local = SteelSectionProbe.NativePipeSupportRecipeGraphics.BuildLocal(nativeComponent.RecipeForCheck))
                    {
                        element.Geometry = local.Geometry.Select(Transform3d.Apply).ToArray();
                        element.CellName = local.CellName;
                    }
#endif
                SteelSectionProbe.World.Elements[element.ElementId] = element;
                SteelSectionProbe.World.Instances[Instance.InstanceId] = Instance;
            }
            return 0;
        }
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
    { public static BMECInstanceManager Instance = new BMECInstanceManager(); public IECInstance CreateECInstance(string type, bool defaults) { return SteelSectionProbe.World.Fault=="SchemaMissing" ? null : new IECInstance(type, "mechanical"); } }
    internal sealed class BMECObjectWriter
    {
        private readonly BMECObject support;
        public BMECObjectWriter(BMECObject support) { this.support = support; }
        public bool Serialize()
        {
            // Match the active SUPPORT.NAME expression instead of letting a handwritten NAME appear stable.
            if (support.Instance.ClassDefinition.Name == "SUPPORT_LOCATION" || support.Instance.ClassDefinition.Name == "SSP_PIPE_CLAMP" || support.Instance.ClassDefinition.Name == "SSP_TRUNNION"
                || support.Instance.ClassDefinition.Name == "SINGLE_PIPE_TRUNNION" || support.Instance.ClassDefinition.Name == "DOUBLE_PIPE_TRUNNION"
                || support.Instance.ClassDefinition.Name == "SIMPLE_ELBOW_SUPPORT")
                support.Instance["NAME"].StringValue = support.Instance["DEVICE_TYPE_CODE"].StringValue + "-" + WorldNumber(support);
            if (SteelSectionProbe.World.Fault == "AliasDropped") support.Instance["ALIAS"].Clear();
            if (SteelSectionProbe.World.Fault == "MarkerDropped") support.Instance["DEVICE_TYPE_CODE"].StringValue = "SP";
            if (SteelSectionProbe.World.Fault == "RecipeDropped") support.Instance["SSP_RECIPE"].Clear();
            if (SteelSectionProbe.World.Fault == "IsoPointDropped") support.Instance["SUPPORT_POINT_X"].DoubleValue = 0;
            if (SteelSectionProbe.World.Fault == "StateDropped") support.Instance["STATE"].Clear();
            return SteelSectionProbe.World.Fault != "Serialize";
        }
        private static string WorldNumber(BMECObject support)
        {
            var number = support.Instance["NUMBER"];
            if(number.IsNull) number.StringValue = SteelSectionProbe.World.Next.ToString("0000");
            return number.StringValue;
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
{ internal static class DgnUtilities { public static List<IECInstance> GetSelectedInstances() { return SteelSectionProbe.World.Selected; } public static IECInstance GetInstanceByInstanceId(string id){IECInstance instance;SteelSectionProbe.World.Instances.TryGetValue(id,out instance);return instance;} } }
namespace SteelSectionProbe.PipeAlignment
{
    internal static class OpenPlantObjectFactory
    {
        internal sealed class Acquired : IDisposable { public BMECObject Object; public void Dispose() { } }
        public static Acquired Acquire(string id, IECInstance instance) {
            var found=BMECApi.Instance.ObjectCache.FindByInstanceId(id);
            if(SteelSectionProbe.World.Fault=="ReadbackAliasDropped"&&found!=null)found.Instance["ALIAS"].Clear();
            if(SteelSectionProbe.World.Fault=="ReadbackRecipeDropped"&&found!=null)found.Instance["SSP_RECIPE"].Clear();
            return new Acquired { Object = found };
        }
    }
}

namespace Bentley.Interop.MicroStationDGN
{
    [Flags] internal enum MsdTransientFlags {Overlay=1,DontIncludeInFit=2}
    internal enum MsdViewMask {AllViews}
    internal enum MsdDrawingMode {Normal}
    internal sealed class TransientElementContainer
    {
        public void Reset(){if(SteelSectionProbe.World.Fault=="DisplayClose")throw new InvalidOperationException("暂态清理失败");SteelSectionProbe.World.Displays.Remove(this);}
    }
    internal sealed class ModelReference
    {public Element GetElementByID64(long id){return new Element{Native=SteelSectionProbe.World.Elements[(ulong)id]};}}
    internal sealed class Element { internal Bentley.DgnPlatformNET.Elements.Element Native; }
    internal sealed class Application
    {
        public ModelReference ActiveModelReference=new ModelReference();
        public TransientElementContainer CreateTransientElementContainer1(Element element,MsdTransientFlags flags,MsdViewMask views,MsdDrawingMode mode)
        {if(SteelSectionProbe.World.Fault=="DisplayCreate")throw new InvalidOperationException("暂态创建失败");var display=new TransientElementContainer();SteelSectionProbe.World.Displays.Add(display);return display;}
    }
}
namespace Bentley.MstnPlatformNET.InteropServices
{internal static class Utilities {public static Bentley.Interop.MicroStationDGN.Application ComApp=new Bentley.Interop.MicroStationDGN.Application();}}
