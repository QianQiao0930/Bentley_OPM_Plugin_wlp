using System;
using System.Collections.Generic;
using System.Linq;
namespace Bentley.GeometryNET {
 public struct DPoint3d { public double X,Y,Z; public static DPoint3d Zero{get{return new DPoint3d();}} public DPoint3d(double x,double y,double z){X=x;Y=y;Z=z;} }
}
namespace Bentley.DgnPlatformNET {
 using Bentley.DgnPlatformNET.Elements;
 public enum StatusInt { Success, Error }
 public enum MSElementType { CellHeader, Line }
 public struct ModelId { public ulong Value; public static explicit operator ModelId(ulong v){return new ModelId{Value=v};} }
 public struct ElementId { public ulong Value; public ElementId(ref ulong v){Value=v;} public static explicit operator ulong(ElementId v){return v.Value;} }
 public sealed class ModelInfo { public string Name; public double UorPerMaster=1000; }
 public sealed class ModelIndex { public ulong Id; public string Name; }
 public sealed class DgnModel {
  public bool Is3d=true,IsReadOnly; public ulong Id=1; public ModelInfo Info=new ModelInfo{Name="Default"};
  public readonly List<Element> Elements=new List<Element>();
  public ModelInfo GetModelInfo(){return Info;}
  public Element FindElementById(ElementId id){return Elements.FirstOrDefault(x=>(ulong)x.ElementId==id.Value&&!x.IsDeleted);}
  public IEnumerable<Element> GetGraphicElements(){return Elements.ToArray();}
 }
 public sealed class DgnFile {
  public bool IsReadOnly; public string Name="E:/fixture/test.dgn"; public List<DgnModel> Models=new List<DgnModel>();
  public Dictionary<string,ItemTypeLibrary> Libraries=new Dictionary<string,ItemTypeLibrary>();
  public string GetFileName(){return Name;}
  public IEnumerable<ModelIndex> GetModelIndexCollection(){return Models.Select(m=>new ModelIndex{Id=m.Id,Name=m.Info.Name});}
  public DgnModel LoadRootModelById(out StatusInt status,ModelId id){var m=Models.FirstOrDefault(x=>x.Id==id.Value);status=m==null?StatusInt.Error:StatusInt.Success;return m;}
 }
 public static class TransactionManager {
  public static bool IsActive,IsUndoInProgress,FailCancel,FailClose; public static int CancelCalls,CloseCalls;
  public static event EventHandler OnUndoRedoFinished; public static void Undo(){if(OnUndoRedoFinished!=null)OnUndoRedoFinished(null,EventArgs.Empty);}
  private static HashSet<ulong> before;
  public static void Activate(){IsActive=true;}
  public static void CloseCurrentTransaction(bool b){CloseCalls++;if(FailClose&&CloseCalls>1)throw new Exception("close fault");}
  public static int CurrentTransactionPosition {get{before=new HashSet<ulong>(Bentley.MstnPlatformNET.Session.Instance.File.Models.SelectMany(m=>m.Elements).Select(e=>(ulong)e.ElementId));return 1;}}
  public static StatusInt CancelToPosition(int p,bool b){CancelCalls++;if(FailCancel)return StatusInt.Error;foreach(var m in Bentley.MstnPlatformNET.Session.Instance.File.Models)m.Elements.RemoveAll(e=>!before.Contains((ulong)e.ElementId));return StatusInt.Success;}
 }
 public sealed class CustomProperty {
  public enum TypeKind {String,Integer,Double} public string Name; public TypeKind Type; public object DefaultValue;
 }
 public sealed class ItemType {
  public string Name,SchemaName; public Dictionary<string,CustomProperty> Props=new Dictionary<string,CustomProperty>();
  public CustomProperty GetPropertyByName(string n){CustomProperty p;return Props.TryGetValue(n,out p)?p:null;}
  public CustomProperty AddProperty(string n,bool b){var p=new CustomProperty{Name=n};Props.Add(n,p);return p;}
 }
 public sealed class ItemTypeLibrary {
  public string InternalName; public Dictionary<string,ItemType> Types=new Dictionary<string,ItemType>();
  public static ItemTypeLibrary FindByName(string n,DgnFile f){ItemTypeLibrary l;return f.Libraries.TryGetValue(n,out l)?l:null;}
  public static ItemTypeLibrary Create(string n,DgnFile f,bool b){var l=new ItemTypeLibrary{InternalName=n};f.Libraries.Add(n,l);return l;}
  public ItemType GetItemTypeByName(string n){ItemType t;return Types.TryGetValue(n,out t)?t:null;}
  public ItemType AddItemType(string n,bool b){var t=new ItemType{Name=n,SchemaName=InternalName};Types.Add(n,t);return t;}
  public bool Write(){return !SteelSectionProbe.Fixture.FailLibraryWrite;}
 }
 public sealed class CustomItemHost {
  private Element element; public CustomItemHost(Element e,bool b){element=e;}
  public Bentley.DgnPlatformNET.DgnEC.IDgnECInstance ApplyCustomItem(ItemType t){if(SteelSectionProbe.Fixture.FailAttach)return null;var i=new Bentley.DgnPlatformNET.DgnEC.IDgnECInstance(t,element);element.Instances.Add(i);return i;}
 }
 public static class SelectionSetManager {
  public static int Count;public static void EmptyAll(){Count=0;}public static bool IsActive(){return Count>0;}public static int NumSelected(){return Count;}
 }
 public sealed class DgnButtonEvent {public Bentley.GeometryNET.DPoint3d Point;}
 public abstract class DgnPrimitiveTool {
  public static DgnPrimitiveTool Installed; protected DgnPrimitiveTool(int a,int b){}
  public void InstallTool(){if(!OnInstall())return;Installed=this;OnPostInstall();}
  public void ExitTool(){if(ReferenceEquals(Installed,this))Installed=null;OnCleanup();}
  public bool DynamicsStarted; protected virtual bool OnInstall(){return true;}protected virtual void OnPostInstall(){}protected void BeginDynamics(){DynamicsStarted=true;}protected void EndDynamics(){DynamicsStarted=false;}
  protected virtual void OnDynamicFrame(DgnButtonEvent e){}protected virtual bool OnDataButton(DgnButtonEvent e){return true;}
  protected virtual bool OnResetButton(DgnButtonEvent e){return true;}protected virtual void OnRestartTool(){}protected virtual void OnCleanup(){SteelSectionProbe.Fixture.BaseCleanupCalls++;}
  public void Dynamic(Bentley.GeometryNET.DPoint3d p){OnDynamicFrame(new DgnButtonEvent{Point=p});}
  public void Click(Bentley.GeometryNET.DPoint3d p){OnDataButton(new DgnButtonEvent{Point=p});}
  public void Reset(){OnResetButton(new DgnButtonEvent());}
 }
}
namespace Bentley.DgnPlatformNET.Elements {
 using Bentley.DgnPlatformNET;
 public class Element:IDisposable {
  public bool IsValid=true,IsDeleted,IsComplexComponent;public Element ParentElement;public MSElementType ElementType;
  public ElementId ElementId;public List<Bentley.DgnPlatformNET.DgnEC.IDgnECInstance> Instances=new List<Bentley.DgnPlatformNET.DgnEC.IDgnECInstance>();
  public void Dispose(){}
 }
 public sealed class CellHeaderElement:Element {public CellHeaderElement(){ElementType=MSElementType.CellHeader;}}
}
namespace Bentley.ECObjects.Instance {
 public sealed class IECPropertyValue {
  private object value; public bool IsNull{get{return value==null;}}
  public string StringValue{get{return (string)value;}set{this.value=value;}}
  public int IntValue{get{return (int)value;}set{this.value=value;}}
  public double DoubleValue{get{return (double)value;}set{this.value=value;}}
 }
}
namespace Bentley.EC.Persistence.Query {
 [Flags]public enum ECQueryProcessFlags {SearchAllClasses=1}
 public sealed class ECQuery {public Selection SelectClause=new Selection();public object ExtendedDataValueSetter;public sealed class Selection{public bool SelectAllProperties;}}
}
namespace Bentley.DgnPlatformNET.DgnEC {
 using Bentley.DgnPlatformNET;using Bentley.DgnPlatformNET.Elements;using Bentley.ECObjects.Instance;
 public enum DgnECHostType {Element}
 public sealed class FindInstancesScopeOption {public FindInstancesScopeOption(DgnECHostType t){}}
 public sealed class FindInstancesScope {public Element Element;public static FindInstancesScope CreateScope(Element e,FindInstancesScopeOption o){return new FindInstancesScope{Element=e};}}
 public sealed class Schema {public string Name;}
 public sealed class ClassDefinition {public Schema Schema;public string Name;public ItemType Item;public IEnumerable<CustomProperty> Properties(bool b){return Item.Props.Values;}}
 public sealed class IDgnECInstance {
  private Element element;public ClassDefinition ClassDefinition;public Dictionary<string,IECPropertyValue> Values=new Dictionary<string,IECPropertyValue>();
  public IDgnECInstance(ItemType t,Element e){element=e;ClassDefinition=new ClassDefinition{Schema=new Schema{Name=t.SchemaName},Name=t.Name,Item=t};foreach(var p in t.Props.Keys)Values[p]=new IECPropertyValue();}
  public IECPropertyValue this[string n]{get{IECPropertyValue p;return Values.TryGetValue(n,out p)?p:null;}}
  public StatusInt WriteChanges(){if(SteelSectionProbe.Fixture.DropProperties)element.Instances.Clear();return SteelSectionProbe.Fixture.FailProperties?StatusInt.Error:StatusInt.Success;}
 }
 public sealed class Instances:List<IDgnECInstance>,IDisposable {public void Dispose(){}}
 public sealed class DgnECManager {
  public static readonly DgnECManager Manager=new DgnECManager();
  public Instances FindInstances(FindInstancesScope s,Bentley.EC.Persistence.Query.ECQuery q){var r=new Instances();r.AddRange(s.Element.Instances);return r;}
 }
}
namespace Bentley.MstnPlatformNET {
 public sealed class Session {public static readonly Session Instance=new Session();public Bentley.DgnPlatformNET.DgnModel Model;public Bentley.DgnPlatformNET.DgnFile File;public Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel(){return Model;}public Bentley.DgnPlatformNET.DgnFile GetActiveDgnFile(){return File;}}
 public static class AccuSnap {public static bool SnapEnabled,LocateEnabled;}
 public static class NotificationManager {public static void OutputPrompt(string s){}}
}
namespace Bentley.MstnPlatformNET.InteropServices {public static class Utilities {public static Bentley.Interop.MicroStationDGN.Application ComApp;}}
namespace Bentley.Interop.MicroStationDGN {
 public struct Point3d {public double X,Y,Z;} public struct Range3d {public Point3d Low,High;}
 [Flags]public enum MsdTransientFlags {Overlay=1,DontIncludeInFit=2}public enum MsdViewMask{AllViews}public enum MsdDrawingMode{Normal}
 public sealed partial class CellElement {
  public bool IsValid=true,Ordinary=true,New=true,ThrowIdentity;public string Name="coil";public long Id;public Point3d Origin;
  public bool IsNew{get{if(ThrowIdentity)throw new Exception("identity fault");return New;}}
  public long ID64{get{if(ThrowIdentity)throw new Exception("identity fault");return Id;}}
  public Range3d Range=new Range3d{Low=new Point3d{X=-1,Y=-1,Z=0},High=new Point3d{X=1,Y=1,Z=4}};public long MdlElementDescrP(bool b){return 42;}
  public CellElement AsCellElement(){return this;}public bool IsCellElement(){return Ordinary;}public void Move(ref Point3d d){Origin.X+=d.X;Origin.Y+=d.Y;Origin.Z+=d.Z;Range.Low.X+=d.X;Range.High.X+=d.X;Range.Low.Y+=d.Y;Range.High.Y+=d.Y;Range.Low.Z+=d.Z;Range.High.Z+=d.Z;}
 }
 public sealed class View {public bool IsOpen=true;public void Redraw(){if(Bentley.DgnPlatformNET.DgnPrimitiveTool.Installed!=null&&Bentley.DgnPlatformNET.DgnPrimitiveTool.Installed.DynamicsStarted)throw new Exception("redraw attempted during dynamics");if(SteelSectionProbe.Fixture.FailRedraw)throw new Exception("redraw fault");SteelSectionProbe.Fixture.RedrawCalls++;SteelSectionProbe.Fixture.VisibleCount=Bentley.MstnPlatformNET.Session.Instance.Model.Elements.Count;}}
 public sealed class DesignFile {public string FullName;public List<View> Views=new List<View>{new View()};}
 public sealed class ModelReference {
  public bool Is3D=true;public string Name="Default";public double UORsPerMasterUnit=1000;
  private CellElement last;
  public CellElement GetLastValidGraphicalElement(){return last;}
  public void AddElement(CellElement e){if(SteelSectionProbe.Fixture.SuppressAdd)return;var f=SteelSectionProbe.Fixture.NextId++;e.Id=SteelSectionProbe.Fixture.KeepZeroId?0:(long)f;e.New=SteelSectionProbe.Fixture.KeepNew;last=new CellElement{Name=e.Name,Id=(long)f,New=false,Origin=e.Origin};Bentley.MstnPlatformNET.Session.Instance.Model.Elements.Add(new Bentley.DgnPlatformNET.Elements.CellHeaderElement{ElementId=new Bentley.DgnPlatformNET.ElementId(ref f)});if(SteelSectionProbe.Fixture.FailAdd){e.ThrowIdentity=SteelSectionProbe.Fixture.ThrowIdentity;throw new Exception("add fault");}}
 }
 public sealed class TransientElementContainer {
  public bool Cleared;public void Reset(){if(SteelSectionProbe.Fixture.FailReset)throw new Exception("reset fault");Cleared=true;}
 }
 public sealed partial class Application {
  public bool HasActiveModelReference=true,HasActiveDesignFile=true;public ModelReference ActiveModelReference=new ModelReference();public DesignFile ActiveDesignFile=new DesignFile();
  public TransientElementContainer CreateTransientElementContainer1(CellElement e,MsdTransientFlags f,MsdViewMask v,MsdDrawingMode d){SteelSectionProbe.Fixture.TransientCreates++;return new TransientElementContainer();}
 }
}
namespace SteelSectionProbe {
 internal static class CelLibraryLog {internal static void Write(string stage,string message){}}
 internal static class ECQueryProcessAccessor {internal static void SetIn(object o,Bentley.EC.Persistence.Query.ECQueryProcessFlags f){}}
 internal static class Fixture {
  internal static bool FailAttach,FailProperties,DropProperties,FailLibraryWrite,FailAdd,ThrowIdentity,FailReset,KeepNew,KeepZeroId,SuppressAdd,FailRedraw;
  internal static ulong NextId=10;internal static int TransientCreates,BaseCleanupCalls,RedrawCalls,VisibleCount;
  internal static void Reset(){
   FailAttach=FailProperties=DropProperties=FailLibraryWrite=FailAdd=ThrowIdentity=FailReset=KeepNew=KeepZeroId=SuppressAdd=FailRedraw=false;NextId=10;TransientCreates=BaseCleanupCalls=RedrawCalls=VisibleCount=0;
   var m=new Bentley.DgnPlatformNET.DgnModel();var f=new Bentley.DgnPlatformNET.DgnFile();f.Models.Add(m);Bentley.MstnPlatformNET.Session.Instance.Model=m;Bentley.MstnPlatformNET.Session.Instance.File=f;
   Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp=new Bentley.Interop.MicroStationDGN.Application{ActiveDesignFile=new Bentley.Interop.MicroStationDGN.DesignFile{FullName=f.Name}};
   Bentley.DgnPlatformNET.TransactionManager.IsActive=Bentley.DgnPlatformNET.TransactionManager.IsUndoInProgress=Bentley.DgnPlatformNET.TransactionManager.FailCancel=Bentley.DgnPlatformNET.TransactionManager.FailClose=false;
   Bentley.DgnPlatformNET.TransactionManager.CancelCalls=Bentley.DgnPlatformNET.TransactionManager.CloseCalls=0;LicenseService.IsActivated=true;
  }
 }
}
