using System;
using System.IO;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Com=Bentley.Interop.MicroStationDGN;
namespace SteelSectionProbe {
 internal static class Program {
  static int checks;static void Check(bool v,string n){checks++;if(!v)throw new Exception(n);}
  static void Throws(Action a,string n){bool thrown=false;try{a();}catch{thrown=true;}Check(thrown,n);}
  static CelPlacementMetadata Meta(){return new CelPlacementMetadata{LibraryFileName="coil.cel",CellName="coil",Category="盘管",Specification="DN25",RotationDegrees=90};}
  static Com.CellElement Make(DPoint3d p){return new Com.CellElement{Origin=new Com.Point3d{X=p.X/1000,Y=p.Y/1000,Z=p.Z/1000}};}
  static int Main(){try{
   Fixture.Reset();var p=new DPoint3d(1000,2000,3000);var result=CelPlacementWriter.Place(Make,Meta(),p);
   Check(result.ElementId=="10"&&Session.Instance.Model.Elements.Count==1,"one persisted root");
   var snapshot=CelComponentStore.Read();Check(snapshot.InstanceCount==1&&snapshot.TotalQuantity==1,"persisted item read");Check(snapshot.Rows[0].RotationDegrees==90&&snapshot.Rows[0].Category=="盘管","all metadata persists");
   Fixture.Reset();Fixture.KeepNew=true;var frozen=CelPlacementWriter.Place(Make,Meta(),p);Check(frozen.ElementId=="10"&&CelComponentStore.Read().TotalQuantity==1,"persisted cell accepted while original COM IsNew stays true");
   Fixture.Reset();Fixture.KeepNew=true;Fixture.KeepZeroId=true;var copied=CelPlacementWriter.Place(Make,Meta(),p);Check(copied.ElementId=="10"&&CelComponentStore.Read().TotalQuantity==1,"copied descriptor resolved from new matching last root");
   Fixture.Reset();CelPlacementWriter.Place(Make,Meta(),p);Fixture.SuppressAdd=true;Throws(()=>CelPlacementWriter.Place(Make,Meta(),p),"unchanged old last cell is never accepted as a new placement");Check(CelComponentStore.Read().TotalQuantity==1,"failed no-op add leaves original cell and metadata intact");
   foreach(var fault in new Action[]{()=>Fixture.FailAttach=true,()=>Fixture.FailProperties=true,()=>Fixture.DropProperties=true,()=>Fixture.FailLibraryWrite=true,()=>Fixture.FailAdd=true,()=>TransactionManager.FailClose=true}){
    Fixture.Reset();fault();Throws(()=>CelPlacementWriter.Place(Make,Meta(),p),"fault rejected");Check(Session.Instance.Model.Elements.Count==0&&TransactionManager.CancelCalls==1,"atomic rollback");
   }
   Fixture.Reset();Fixture.FailAdd=true;Fixture.ThrowIdentity=true;Throws(()=>CelPlacementWriter.Place(Make,Meta(),p),"identity unreadable reported");Check(TransactionManager.CancelCalls==1&&Session.Instance.Model.Elements.Count==0,"identity getter cannot prevent rollback");
   Fixture.Reset();Fixture.FailProperties=true;TransactionManager.FailCancel=true;Throws(()=>CelPlacementWriter.Place(Make,Meta(),p),"rollback failure exposed");Check(Session.Instance.Model.Elements.Count==1,"failed rollback never falsely removes root");
   Fixture.Reset();Throws(()=>CelPlacementWriter.Place(_=>{throw new Exception("factory");},Meta(),p),"factory fails offline");Check(TransactionManager.CloseCalls==0&&Session.Instance.Model.Elements.Count==0,"factory failure no transaction write");
   Fixture.Reset();var other=new DgnModel{Id=2,Info=new ModelInfo{Name="Second"}};Session.Instance.File.Models.Add(other);CelPlacementWriter.Place(Make,Meta(),p);
   var original=Session.Instance.Model.Elements[0];ulong copyId=20;Session.Instance.Model.Elements.Add(new Bentley.DgnPlatformNET.Elements.CellHeaderElement{ElementId=new ElementId(ref copyId),Instances=original.Instances});
   ulong nestedId=21;Session.Instance.Model.Elements.Add(new Bentley.DgnPlatformNET.Elements.CellHeaderElement{ElementId=new ElementId(ref nestedId),Instances=original.Instances,IsComplexComponent=true,ParentElement=original});
   ulong otherId=10;other.Elements.Add(new Bentley.DgnPlatformNET.Elements.CellHeaderElement{ElementId=new ElementId(ref otherId),Instances=original.Instances});
   Check(CelComponentStore.Read().TotalQuantity==2,"copy counted nested excluded");Check(CelComponentStore.Read(true).TotalQuantity==3,"same element ID other root model counted");
   Session.Instance.Model.Elements.Remove(original);Check(CelComponentStore.Read().TotalQuantity==1,"deletion reflected");
   var csv=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"check.csv");CelStatisticsExporter.WriteCsv(csv,CelComponentStore.Read(true));Check(File.ReadAllText(csv).Contains("盘管"),"CSV UTF8 export");
   Fixture.Reset();var factories=0;Func<DPoint3d,Com.CellElement> make=x=>{factories++;return Make(x);};int ended=0;Action onEnd=()=>ended++;CelPlacementTool.Ended+=onEnd;
   AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=false;SelectionSetManager.Count=4;CelPlacementTool.Begin(make,Meta());var tool=DgnPrimitiveTool.Installed;
   Check(SelectionSetManager.Count==0&&CelPlacementTool.IsActive,"start clears selection");tool.Dynamic(p);tool.Dynamic(new DPoint3d(4000,2000,3000));Check(factories==1&&Fixture.TransientCreates==2&&Session.Instance.Model.Elements.Count==0,"cached transient preview never persists");
   SelectionSetManager.Count=2;CelPlacementTool.Begin(make,Meta());Check(ReferenceEquals(tool,DgnPrimitiveTool.Installed)&&SelectionSetManager.Count==0,"repeat begin reuse clears selection");tool.Click(p);Check(Session.Instance.Model.Elements.Count==1&&CelComponentStore.Read().TotalQuantity==1,"one left click commits");tool.Click(p);Check(Session.Instance.Model.Elements.Count==2,"continuous second click");Check(Fixture.VisibleCount==2&&Fixture.RedrawCalls==2&&CelPlacementTool.IsActive&&tool.DynamicsStarted,"each commit redraws before right-click and resumes continuous dynamics");
   Fixture.FailRedraw=true;tool.Click(p);Check(Session.Instance.Model.Elements.Count==3&&CelComponentStore.Read().TotalQuantity==3,"refresh failure never rolls back committed cell or metadata");Fixture.FailRedraw=false;
   tool.Dynamic(p);Fixture.FailReset=true;tool.Reset();Check(!CelPlacementTool.IsActive&&CelPlacementTool.NeedsCleanup&&Fixture.BaseCleanupCalls>0,"native reset catches clear failure and retains owner");Check(ended==1,"ended once");
   Fixture.FailReset=false;CelPlacementTool.End();Check(!CelPlacementTool.NeedsCleanup,"explicit end retries pending display");Check(!AccuSnap.SnapEnabled&&!AccuSnap.LocateEnabled,"capture restored");Check(ended==1,"retry no duplicate ended");CelPlacementTool.Ended-=onEnd;
   Fixture.Reset();LicenseService.IsActivated=false;Throws(()=>CelPlacementTool.Begin(make,Meta()),"unlicensed cannot begin");Check(!CelPlacementTool.IsActive,"license failure no install");
   Fixture.Reset();Session.Instance.Model.IsReadOnly=true;Throws(()=>CelPlacementWriter.Place(Make,Meta(),p),"read only blocked");Check(Session.Instance.Model.Elements.Count==0,"readonly no model mutation");
   Console.WriteLine("CEL placement: "+checks+" assertions passed using real writer/store/tool with host API fakes. Native Bentley rendering/transactions require host acceptance.");return 0;
  }catch(Exception ex){Console.Error.WriteLine(ex);return 1;}}
 }
}
