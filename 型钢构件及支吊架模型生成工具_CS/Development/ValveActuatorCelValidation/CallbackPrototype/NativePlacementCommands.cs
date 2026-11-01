extern alias NativeOPM;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Bentley.OpenPlant.Modeler.Api;

namespace ActuatorCallbackCheck
{
    [AddInAttribute(MdlTaskID="ValveActuatorCallbackCheck")]
    public sealed class CheckAddIn : AddIn
    {
        private CheckAddIn(IntPtr descriptor) : base(descriptor)
        {
            UnloadingEvent+=(sender,args)=>
            {
                if(!Commands.HasNativeObjects||(args.UnloadKind!=AddIn.UnloadReasons.Command&&args.UnloadKind!=AddIn.UnloadReasons.LibraryUnload))return;
                args.ResponseCode=AddIn.UnloadingEventArgs.Response.UnloadAbort;
                NotificationManager.OutputPrompt("官方放置工具已接收验证对象，请正常退出 OPM 后再更新验证 DLL。");
            };
        }
        protected override int Run(string[] args) {return 0;}
    }

    /// <summary>Delegates selection, installation and persistence to the official Topwork tool.</summary>
    public static class Commands
    {
        private const string Relation="VALVE_HAS_VALVE_OPERATING_DEVICE";
        private static bool running;
        // The official tool may retain the supplied object through confirmation or
        // cancellation. Keep a bounded set alive until the host exits.
        private static readonly List<BMECObject> placementObjects=new List<BMECObject>();
        internal static bool HasNativeObjects {get{return placementObjects.Count!=0;}}

        public static void Place(string args) {Gearbox(args);}
        public static void Gearbox(string args) {Run("gearbox_place",trace=>StartOfficialPlacement(trace,true),true);}
        public static void Handwheel(string args) {Run("handwheel_place",trace=>StartOfficialPlacement(trace,false),true);}
        public static void Create(string args) {Place(args);} // Old command now starts the official tool too.
        public static void Probe(string args) {Run("probe",ProbeCore,false);}

        private static void Run(string stage,Action<StringBuilder> action,bool keepNativePrompt)
        {
            if(running){NotificationManager.OutputPrompt("执行机构命令正在执行，请稍后。");return;}
            running=true;bool failed=false;string failureMessage=null;
            var trace=new StringBuilder("Version=5; Route=official BMECApi.StartPlacement(BMECObject); Stage="+stage+"\r\n");
            try
            {
                if(!Utilities.IsMicroStationMainThread)throw new InvalidOperationException("请在 OPM 主线程运行命令。");
                action(trace);
                trace.AppendLine(keepNativePrompt?"PlacementRequestReturned=true; user interaction/commit/relation NOT yet verified.":"ProbeCompleted=true");
            }
            catch(Exception error){failed=true;failureMessage=error.Message;trace.AppendLine("CommandFailed="+error);}
            finally
            {
                TraceLog.Save(stage,trace.ToString());
                // Keep the native "select valve/orient/accept" prompt visible.
                if(failed)NotificationManager.OutputPrompt("执行机构命令失败："+failureMessage+"；日志："+TraceLog.LastFile);
                else if(!keepNativePrompt)NotificationManager.OutputPrompt("探查完成；日志："+TraceLog.LastFile);
                running=false;
            }
        }

        private static void StartOfficialPlacement(StringBuilder trace,bool gearbox)
        {
            CelResource.RequireContext();
            var model=Session.Instance.GetActiveDgnModel();var file=Session.Instance.GetActiveDgnFile();
            if(model.IsReadOnly||file.IsReadOnly||TransactionManager.IsUndoInProgress)throw new InvalidOperationException("请打开可写三维模型，并结束撤销/重做。");
            if(placementObjects.Count>=16)throw new InvalidOperationException("本轮每进程最多16次启动，请正常退出 OPM 后重开。");
            var api=BMECApi.Instance;
            if(api.DeferCommits)throw new InvalidOperationException("宿主正在延迟提交，请结束当前操作后重试。");
            string className=gearbox?CelResource.GearboxClassName:CelResource.ClassName;
            trace.AppendLine("RequestedClass="+className+"; NativeBase="+(gearbox?"GEARBOX_OPERATOR":"HAND_WHEEL"));
            var instance=BMECInstanceManager.Instance.CreateECInstance(className,true);
            if(instance==null)throw new InvalidOperationException("当前工作集未加载 "+className+"；请安装对应测试Schema后重启OPM。");
            instance["SSP_CEL_VERSION"].IntValue=1;
            Number(instance,"ANGLE",0);Number(instance,"LENGTH",1);Number(instance,"DIAMETER",1);
            // Fixed CEL geometry does not consume native size fields. These are setup
            // seeds, not dimensions measured from the actuator or a catalogue selection.
            if(gearbox)
            {
                foreach(string name in GearboxDimensions)Number(instance,name,name=="HANDLE_OFFSET"?0:1);
                trace.AppendLine("NativeSetupDimensions=1 (HANDLE_OFFSET=0); ValuesAreMeasuredCelDimensions=false; FixedCelGeometry=true");
            }
            var component=new BMECObject(instance,false);
            bool correctHandler=gearbox?component.Component is CelGearboxComponent:component.Component is CelHandwheelComponent;
            if(!component.IsParametric||!correctHandler
                ||component.PlacementTool!="TopworksPlacementTool")
            {
                component.Dispose();
                throw new InvalidOperationException("测试类没有解析为参数化CEL处理器和TopworksPlacementTool。");
            }
            placementObjects.Add(component);
            trace.AppendLine("Assembly="+typeof(Commands).Assembly.Location+"; MVID="+typeof(Commands).Assembly.ManifestModule.ModuleVersionId);
            trace.AppendLine("DGN="+file.GetFileName()+"; Model="+model.GetModelInfo().Name);
            trace.AppendLine("Class="+instance.ClassDefinition.Name+"; IsParametric="+component.IsParametric
                +"; PlacementTool="+component.PlacementTool+"; Component="+component.Component.GetType().FullName);
            DescribeDimensions(instance,trace);
            trace.AppendLine("RelatedInstanceAssignedByPlugin=false; CreateCalledByPlugin=false; SerializeCalledByPlugin=false; SelectionCountBefore="+SelectionSetManager.NumSelected());
            SelectionSetManager.EmptyAll();
            if(SelectionSetManager.NumSelected()!=0)throw new InvalidOperationException("无法清空旧选择集，请取消选择后重新激活。");
            NotificationManager.OutputPrompt("请按官方执行机构工具提示，在模型中点选要安装的阀门。");
            // No custom picker, placement transform, relationship assignment, or writer.
            api.StartPlacement(component);
            var current=api.CurrentPlacementTool;
            trace.AppendLine("CurrentPlacementTool="+(current==null?"null/pending":current.GetType().FullName));
        }

        private static readonly string[] GearboxDimensions={"TOTAL_HEIGHT","GEAR_BOX_HEIGHT","GEAR_BOX_WIDTH",
            "GEAR_BOX_THICKNESS","HANDLE_WIDTH","HANDLE_HEIGHT","HANDLE_LENGTH","HANDLE_THICKNESS","HANDLE_OFFSET"};

        private static void DescribeDimensions(IECInstance instance,StringBuilder trace)
        {
            foreach(string name in GearboxDimensions.Concat(new[]{"ANGLE","LENGTH","DIAMETER"}))
            {
                var property=instance.ClassDefinition.Properties(true).FirstOrDefault(p=>p.Name==name);
                if(property==null)continue;
                var value=instance[name];
                trace.AppendLine("NativeParameter="+name+"; Value="+(value.IsNull?"null":
                    property.Type.Name.Equals("string",StringComparison.OrdinalIgnoreCase)?value.StringValue:
                    value.DoubleValue.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            }
        }

        private static void Number(IECInstance instance,string name,double value)
        {
            var property=instance.ClassDefinition.Properties(true).First(p=>p.Name==name);
            if(property.Type.Name.Equals("string",StringComparison.OrdinalIgnoreCase))instance[name].StringValue=value.ToString(System.Globalization.CultureInfo.InvariantCulture);
            else instance[name].DoubleValue=value;
        }

        private static unsafe IntPtr Token(DgnModel model) {return (IntPtr)DgnModelRef.GetNativeDgnModelRefP(model,false);}
        private static unsafe IECInstance ReadInstanceAndRelations(Element element)
        {
            return BMECApi.Instance.LoadInstanceWithAllRelationships(
                (NativeOPM::Bentley.DgnPlatform.ElementRefBase*)element.GetNativeElementRef(),
                (NativeOPM::Bentley.DgnPlatform.DgnModelRef*)element.GetNativeDgnModelRef());
        }
        private static List<IECInstance> Related(IECInstance instance,bool forward)
        {
            // Include descendants on both sides, including both isolated test subclasses.
            return BMECApi.Instance.GetRelatedInstances(instance,Relation,
                forward?"VALVE_OPERATING_DEVICE":"PIPING_COMPONENT",forward,true,true).Cast<IECInstance>().ToList();
        }
        private static void ProbeCore(StringBuilder trace)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("请激活三维模型。");
            uint count=SelectionSetManager.NumSelected();
            if(count==0||count>2)throw new InvalidOperationException("放置结束后，选择阀门或执行机构（1～2件）再运行 PROBE。");
            for(uint i=0;i<count;i++)
            {
                Element element=null;DgnModelRef reference=null;
                if(SelectionSetManager.GetElement(i,ref element,ref reference)!=StatusInt.Success||element==null
                    ||element.GetNativeDgnModelRef()!=Token(model))throw new InvalidOperationException("仅探查活动模型中的元素。");
                trace.AppendLine("SelectedElement="+(ulong)element.ElementId);
                var instance=ReadInstanceAndRelations(element);
                if(instance==null){trace.AppendLine("NativeInstance=none");continue;}
                Describe(instance,trace);
                var parents=Related(instance,false);var children=Related(instance,true);
                trace.AppendLine("ReverseParentCount="+parents.Count+"; ForwardOperatorCount="+children.Count);
                foreach(var parent in parents){trace.AppendLine("Reverse="+Relation);Describe(parent,trace);}
                foreach(var child in children){trace.AppendLine("Forward="+Relation);Describe(child,trace);}
                var raw=BMECApi.Instance.GetAllRelationshipInstances(instance);
                if(raw==null)trace.AppendLine("RawRelations=unavailable");
                else foreach(IECRelationshipInstance relation in raw)
                    trace.AppendLine("RawRelation="+relation.ClassDefinition.Name+"; Id="+relation.InstanceId);
            }
        }
        private static void Describe(IECInstance instance,StringBuilder trace)
        {
            using(var obj=new BMECObject(instance))
            {
                trace.AppendLine("Instance="+instance.InstanceId+"; Class="+instance.ClassDefinition.Name+"; IsParametric="+obj.IsParametric
                    +"; PlacementTool="+obj.PlacementTool+"; Component="+(obj.Component==null?"null":obj.Component.GetType().FullName)+"; Transform="+obj.Transform3d);
                DescribeDimensions(instance,trace);
            }
        }
    }
}
