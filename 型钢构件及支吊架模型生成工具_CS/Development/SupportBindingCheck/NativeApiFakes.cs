using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;

namespace Bentley.GeometryNET
{
    internal struct DPoint3d { internal double X,Y,Z; internal DPoint3d(double x,double y,double z){X=x;Y=y;Z=z;} }
    internal struct DTransform3d { internal DPoint3d Translation; }
}

// API记录替身只提供存储/事务/点取边界；不执行Bentley内核或ISO提取。
namespace Bentley.ECObjects.Instance
{
    internal interface IECInstance
    {
        ClassDefinition ClassDefinition { get; }
        string InstanceId { get; }
        PropertyValue this[string name] { get; }
    }
    internal sealed class PropertyValue { internal string StringValue; internal bool IsNull { get { return StringValue == null; } } }
    internal sealed class PropertyDefinition { internal string Name; }
    internal sealed class SchemaDefinition { internal string Name; }
    internal sealed class ClassDefinition
    {
        internal string Name;
        internal SchemaDefinition Schema=new SchemaDefinition();
        internal readonly List<PropertyDefinition> Fields=new List<PropertyDefinition>();
        internal IEnumerable<PropertyDefinition> Properties(bool inherited) { return Fields; }
    }
}
namespace Bentley.DgnPlatformNET.DgnEC
{
    internal sealed class IDgnECInstance : IECInstance
    {
        public ClassDefinition ClassDefinition { get; set; }=new ClassDefinition();
        public string InstanceId { get; set; }
        internal string Library;
        internal readonly Dictionary<string,PropertyValue> Values=new Dictionary<string,PropertyValue>();
        public PropertyValue this[string name]
        {
            get
            {
                if(!Values.ContainsKey(name)) { Values[name]=new PropertyValue(); ClassDefinition.Fields.Add(new PropertyDefinition{Name=name}); }
                return Values[name];
            }
        }
        internal StatusInt WriteChanges()
        {
            if(FakeState.Fault=="item-write" || (FakeState.Fault=="note-marker" && ClassDefinition.Name=="BomMaterial")) return StatusInt.Error;
            if(FakeState.Fault=="drop-item") this["Payload"].StringValue="{}";
            return StatusInt.Success;
        }
        internal IDgnECInstance Clone()
        {
            var result=new IDgnECInstance{InstanceId=InstanceId,Library=Library};
            result.ClassDefinition.Name=ClassDefinition.Name;result.ClassDefinition.Schema.Name=ClassDefinition.Schema.Name;
            foreach(var pair in Values) result[pair.Key].StringValue=pair.Value.StringValue;
            return result;
        }
    }
    internal enum DgnECHostType { Element }
    internal sealed class FindInstancesScopeOption { internal FindInstancesScopeOption(DgnECHostType type){} }
    internal sealed class FindInstancesScope
    {
        internal Element Element;
        internal static FindInstancesScope CreateScope(Element element,FindInstancesScopeOption options){return new FindInstancesScope{Element=element};}
    }
    internal sealed class InstanceCollection : List<IDgnECInstance>,IDisposable { public void Dispose(){} }
    internal sealed class DgnECManager
    {
        internal static readonly DgnECManager Manager=new DgnECManager();
        internal InstanceCollection FindInstances(FindInstancesScope scope,Bentley.EC.Persistence.Query.ECQuery query)
        {var result=new InstanceCollection();result.AddRange(scope.Element.Items.Values);return result;}
    }
}
namespace Bentley.EC.Persistence.Query
{
    internal enum ECQueryProcessFlags { SearchAllClasses }
    internal sealed class ECQuery
    {
        internal sealed class SelectOptions { internal bool SelectAllProperties; }
        internal SelectOptions SelectClause=new SelectOptions();
        internal object ExtendedDataValueSetter;
    }
    internal static class ECQueryProcessAccessor { internal static void SetIn(object setter,ECQueryProcessFlags flags){} }
}
namespace Bentley.DgnPlatformNET.Elements
{
    internal class Element : IDisposable
    {
        internal ulong ElementId;
        internal bool IsValid=true,IsDeleted,IsComplexComponent,Locked;
        internal Element ParentElement;
        internal DgnModelRef DgnModelRef=FakeState.Model;
        internal readonly Dictionary<string,IDgnECInstance> Items=new Dictionary<string,IDgnECInstance>();
        internal bool IsEffectivelyLocked(bool a,bool b){return Locked;}
        public void Dispose(){}
        internal Element Clone()
        {
            var result=new Element{ElementId=ElementId,IsValid=IsValid,IsDeleted=IsDeleted,
                IsComplexComponent=IsComplexComponent,Locked=Locked,ParentElement=ParentElement,DgnModelRef=DgnModelRef};
            foreach(var pair in Items) result.Items.Add(pair.Key,pair.Value.Clone());
            return result;
        }
    }
}
namespace Bentley.DgnPlatformNET
{
    internal enum StatusInt { Success,Error }
    internal struct ElementId { internal ulong Value; internal ElementId(ref ulong value){Value=value;} }
    internal class DgnModelRef
    {
        internal bool IsDgnAttachment;
        internal DgnModel GetDgnModel(){return this as DgnModel;}
    }
    internal sealed class DgnModel : DgnModelRef
    {
        internal bool Is3d=true,IsReadOnly;
        internal string Id="1";
        internal DgnFile GetDgnFile(){return FakeState.File;}
        internal string GetModelId(){return Id;}
        internal Element FindElementById(ElementId id){Element result;FakeState.Elements.TryGetValue(id.Value,out result);return result;}
        internal IEnumerable<Element> GetGraphicElements(){return FakeState.Elements.Values.Where(e=>!e.IsDeleted).ToArray();}
    }
    internal sealed class DgnFile { internal bool IsReadOnly; internal string Name="fixture.dgn"; internal string GetFileName(){return Name;} }
    internal sealed class CustomProperty
    {
        internal enum TypeKind { String,Double }
        internal TypeKind Type;
    }
    internal sealed class ItemType
    {
        internal string Name,Library;
        internal readonly Dictionary<string,CustomProperty> Properties=new Dictionary<string,CustomProperty>();
        internal CustomProperty GetPropertyByName(string name){CustomProperty p;Properties.TryGetValue(name,out p);return p;}
        internal CustomProperty AddProperty(string name,bool hidden){return Properties[name]=new CustomProperty();}
    }
    internal sealed class ItemTypeLibrary
    {
        internal string InternalName;
        internal readonly Dictionary<string,ItemType> Types=new Dictionary<string,ItemType>();
        internal static ItemTypeLibrary FindByName(string name,DgnFile file){ItemTypeLibrary result;FakeState.Libraries.TryGetValue(name,out result);return result;}
        internal static ItemTypeLibrary Create(string name,DgnFile file,bool hidden){return FakeState.Libraries[name]=new ItemTypeLibrary{InternalName=name};}
        internal ItemType GetItemTypeByName(string name){ItemType result;Types.TryGetValue(name,out result);return result;}
        internal ItemType AddItemType(string name,bool hidden){return Types[name]=new ItemType{Name=name,Library=InternalName};}
        internal bool Write(){return FakeState.Fault!="library-write";}
    }
    internal sealed class CustomItemHost
    {
        private readonly Element element;
        internal CustomItemHost(Element element,bool scheduled){this.element=element;}
        internal IDgnECInstance GetCustomItem(string library,string type){IDgnECInstance result;element.Items.TryGetValue(library+"/"+type,out result);return result;}
        internal IDgnECInstance ApplyCustomItem(ItemType type)
        {
            if (GetCustomItem(type.Library, type.Name) != null) return null;
            return FakeState.Item(element, type.Library, type.Name);
        }
    }
    internal sealed class OnUndoRedoFinishedEventArgs : EventArgs {}
    internal static class TransactionManager
    {
        internal static bool IsUndoInProgress,IsActive;
        internal static event EventHandler<OnUndoRedoFinishedEventArgs> OnUndoRedoFinished;
        internal static int Closes,Rollbacks;
        internal static void Activate(){IsActive=true;}
        internal static int CurrentTransactionPosition {get{return FakeState.Mark();}}
        internal static void CloseCurrentTransaction(bool commit){Closes++;}
        internal static StatusInt CancelToPosition(int mark,bool restart)
        {Rollbacks++;if(FakeState.Fault=="rollback")return StatusInt.Error;FakeState.Restore();return StatusInt.Success;}
        internal static void UndoEvent(){OnUndoRedoFinished?.Invoke(null,new OnUndoRedoFinishedEventArgs());}
    }
    internal enum ComponentMode { None }
    internal sealed class DgnButtonEvent {}
    internal sealed class HitPath { internal Element Element; internal Element GetHeadElement(){return Element;} }
    internal class DgnElementSetTool
    {
        internal static DgnElementSetTool Tool;
        internal DgnElementSetTool(int a,int b){}
        internal void InstallTool(){Tool=this;OnPostInstall();}
        internal void ExitTool(){OnCleanup();Tool=null;}
        protected virtual void OnPostInstall(){}
        protected virtual void OnCleanup(){}
        protected virtual void OnRestartTool(){}
        protected virtual bool OnResetButton(DgnButtonEvent ev){return true;}
        protected virtual bool OnDataButton(DgnButtonEvent ev){return true;}
        protected virtual bool OnPostLocate(HitPath path,out string reason){reason="";return true;}
        public virtual StatusInt OnElementModify(Element element){return StatusInt.Error;}
        protected HitPath DoLocate(DgnButtonEvent ev,bool locate,int mode){return new HitPath{Element=FakeState.Pick};}
        internal static void Pick(Element element){FakeState.Pick=element;Tool.OnDataButton(new DgnButtonEvent());}
    }
}
namespace Bentley.MstnPlatformNET
{
    internal static class AccuSnap { internal static bool SnapEnabled,LocateEnabled; }
    internal static class NotificationManager { internal static void OutputPrompt(string text){} }
    internal sealed class Session
    {
        internal static readonly Session Instance=new Session();
        internal DgnModel GetActiveDgnModel(){return FakeState.Model;}
        internal DgnFile GetActiveDgnFile(){return FakeState.File;}
    }
}
namespace Bentley.OpenPlant.Modeler.Api
{
    internal sealed class BMECApi
    {
        internal static readonly BMECApi Instance=new BMECApi();
        internal bool DeferCommits=true;
        internal BMECObjectCache ObjectCache=new BMECObjectCache();
        internal bool IsPersistentId(string id){return FakeState.Instance(id)!=null;}
        internal List<IECInstance> GetRelatedInstances(IECInstance instance,string relation,bool forward,bool polymorphic)
        {
            var values=new List<IECInstance>();
            if(!forward && instance!=null && ((relation=="DEVICE_HAS_SUPPORT"&&instance.ClassDefinition.Name!="ADDITIONAL_MATERIAL") ||
                (relation=="PIPING_COMPONENT_HAS_NOTE"&&instance.ClassDefinition.Name=="ADDITIONAL_MATERIAL")))
            {
                var parent=FakeState.Instance(instance["PARENT_ID"].StringValue);
                if(parent!=null)values.Add(parent);
            }
            return values;
        }
        internal bool AddNoteToComponent(IECInstance parent,IECInstance note)
        {
            if(FakeState.Fault=="note-rel")return false;
            note["PARENT_ID"].StringValue=parent.InstanceId;return true;
        }
        internal int DeleteFromModel(BMECObject value)
        {
            if(FakeState.Fault=="note-delete")return 1;
            var element=FakeState.Elements.Values.Single(e=>e.Items.Values.Any(i=>i.InstanceId==value.Instance.InstanceId));
            FakeState.Elements.Remove(element.ElementId);return 0;
        }
    }
    internal sealed class BMECObjectCache
    {
        internal readonly Dictionary<int,BMECObject> Values=new Dictionary<int,BMECObject>();
        internal int Add(BMECObject item){int key=Values.Count==0?1:Values.Keys.Max()+1;Values[key]=item;return key;}
        internal void Remove(int key){Values.Remove(key);}
        internal BMECObject FindByInstanceId(string id){return Values.Values.FirstOrDefault(v=>v.Instance.InstanceId==id);}
    }
    internal sealed class BMECInstanceManager
    {
        internal static readonly BMECInstanceManager Instance=new BMECInstanceManager();
        internal IECInstance CreateECInstance(string name,bool defaults)
        {
            var value=new IDgnECInstance{InstanceId="pending-note-"+(++FakeState.NextNote)};
            value.ClassDefinition.Name=name;value.ClassDefinition.Schema.Name="OpenPlant_3D";
            foreach(string field in new[]{"TEXT","NOTE_TYPE","UNIT_OF_MEASURE","DIMENSIONED_NOTE","LINENUMBER","NOMINAL_DIAMETER","LOCATION_X","LOCATION_Y","LOCATION_Z","DIRECTION_X","DIRECTION_Y","DIRECTION_Z"})value[field].StringValue="";
            return value;
        }
    }
    internal sealed class BMECObject : IDisposable
    {
        internal IECInstance Instance;
        internal bool IsValid=true;
        internal IECInstance NetworkSystem,NetworkSegment;
        internal DTransform3d Transform3d;
        internal BMECObject(){}
        internal BMECObject(IECInstance instance){Instance=instance;}
        internal void Refresh(){Instance=FakeState.Instance(Instance.InstanceId);}
        internal void Resync(){}
        internal int Create()
        {
            if(FakeState.Fault=="note-create")return 1;
            var element=new Element{ElementId=(ulong)(1000+FakeState.NextNote)};
            FakeState.Elements.Add(element.ElementId,element);
            element.Items["OpenPlant_3D/ADDITIONAL_MATERIAL"]=(IDgnECInstance)Instance;
            return 0;
        }
        internal bool SetDoubleValueFromMM(string name,double value){Instance[name].StringValue=(value/FakeState.MmPerSchemaUnit).ToString(System.Globalization.CultureInfo.InvariantCulture);return true;}
        internal bool SetDoubleValueFromUors(string name,double value){return SetDoubleValueFromMM(name,value/FakeState.UorPerMm);}
        internal bool SetUnitlessDoubleValue(string name,double value){Instance[name].StringValue=value.ToString(System.Globalization.CultureInfo.InvariantCulture);return true;}
        internal static double GetDoubleValueInMM(IECInstance instance,string name){return double.Parse(instance[name].StringValue,System.Globalization.CultureInfo.InvariantCulture)*FakeState.MmPerSchemaUnit;}
        public void Dispose(){if(BMECApi.Instance.ObjectCache.Values.Values.Contains(this))throw new Exception("不能释放API缓存对象");FakeState.OwnedDisposes++;}
    }
    internal sealed class BMECObjectWriter
    {
        private readonly BMECObject support;
        internal BMECObjectWriter(BMECObject support){this.support=support;}
        internal bool Serialize()
        {
            FakeState.Serializes++;
            if(FakeState.Fault=="serialize"||FakeState.Fault=="rollback")return false;
            if(support.Instance.ClassDefinition.Name=="ADDITIONAL_MATERIAL")
            {
                if(FakeState.Fault=="note-serialize")return false;
                if(FakeState.Fault=="drop-note-text")support.Instance["TEXT"].StringValue="lost";
                if(FakeState.Fault=="drop-note-parent")support.Instance["PARENT_ID"].StringValue="missing";
            }
            if(FakeState.Fault=="drop-alias")support.Instance["ALIAS"].StringValue="lost";
            return true;
        }
    }
}
namespace Bentley.OpenPlantModeler.SDK.Utilities
{
    internal static class DgnUtilities { internal static IECInstance GetInstanceByInstanceId(string id){return FakeState.Instance(id);} }
}
namespace SteelSectionProbe.PipeAlignment
{
    internal static class OpenPlantObjectFactory
    {
        internal sealed class Acquired : IDisposable
        {
            internal Bentley.OpenPlant.Modeler.Api.BMECObject Object;
            internal bool OwnsObject;
            public void Dispose(){if(OwnsObject)FakeState.OwnedDisposes++;}
        }
        internal static Acquired Acquire(string id,IECInstance instance)
        {
            var api=Bentley.OpenPlant.Modeler.Api.BMECApi.Instance;
            var value=api.ObjectCache.FindByInstanceId(id);
            if(value==null)
            {
                value=new Bentley.OpenPlant.Modeler.Api.BMECObject{Instance=instance,
                    Transform3d=new DTransform3d{Translation=new DPoint3d(123*FakeState.UorPerMm,-245*FakeState.UorPerMm,800*FakeState.UorPerMm)}};
                if(!FakeState.Detached)api.ObjectCache.Add(value);
            }
            return new Acquired{Object=value,OwnsObject=FakeState.Detached};
        }
    }
}
namespace SteelSectionProbe
{
    internal static class LicenseService { internal static bool IsActivated=true; }
    internal static class NativeSupportData
    {
        internal static void RequireProperty(IECInstance instance,string name)
        {if(!instance.ClassDefinition.Properties(true).Any(p=>p.Name==name))throw new InvalidOperationException("缺少属性 "+name);}
    }
    internal static class NativeSupportElements
    {
        internal static long ActiveModelToken(){return FakeState.Token;}
        internal static Element Get(IECInstance instance,bool writable)
        {
            var root=FakeState.Elements.Values.SingleOrDefault(e=>e.Items.Values.Any(i=>i.InstanceId==instance.InstanceId));
            if(root==null||root.IsDeleted||root.Locked||!ReferenceEquals(root.DgnModelRef,FakeState.Model))throw new InvalidOperationException("原生元素不可写");
            return root;
        }
    }
    internal sealed class MainWindow
    {
        internal static MainWindow Current=new MainWindow();
        internal string LastStatus;
        internal void SetStatus(string text,bool error){LastStatus=text;}
        internal void ShowHome(){} internal void MinimizeFromHome(){} internal void Close(){} internal void BeginTitleDrag(){}
    }
}
internal static class FakeState
{
    internal static DgnModel Model;
    internal static DgnFile File;
    internal static Dictionary<ulong,Element> Elements=new Dictionary<ulong,Element>();
    internal static Dictionary<string,ItemTypeLibrary> Libraries=new Dictionary<string,ItemTypeLibrary>();
    internal static Dictionary<ulong,Element> Saved;
    internal static Element Pick;
    internal static string Fault="";
    internal static bool Detached;
    internal static int Serializes,OwnedDisposes;
    internal static int NextNote;
    internal static double UorPerMm=1,MmPerSchemaUnit=1;
    internal static long Token=1;
    internal static void Reset()
    {
        Model=new DgnModel();File=new DgnFile();Elements.Clear();Libraries.Clear();Fault="";Detached=false;
        Serializes=OwnedDisposes=NextNote=0;UorPerMm=MmPerSchemaUnit=1;Token=1;TransactionManager.Rollbacks=TransactionManager.Closes=0;
        Bentley.OpenPlant.Modeler.Api.BMECApi.Instance.ObjectCache.Values.Clear();
        TransactionManager.IsUndoInProgress=false;TransactionManager.IsActive=false;
        SteelSectionProbe.LicenseService.IsActivated=true;Bentley.OpenPlant.Modeler.Api.BMECApi.Instance.DeferCommits=true;
    }
    internal static IDgnECInstance Instance(string id){return Elements.Values.SelectMany(e=>e.Items.Values).FirstOrDefault(i=>i.InstanceId==id);}
    internal static IDgnECInstance Item(Element element,string library,string type,string id=null)
    {
        var result=new IDgnECInstance{InstanceId=id??Guid.NewGuid().ToString(),Library=library};
        result.ClassDefinition.Name=type;result.ClassDefinition.Schema.Name=library;
        element.Items.Add(library+"/"+type,result);return result;
    }
    internal static int Mark(){Saved=Elements.ToDictionary(p=>p.Key,p=>p.Value.Clone());return 1;}
    internal static void Restore(){Elements=Saved.ToDictionary(p=>p.Key,p=>p.Value.Clone());}
}
