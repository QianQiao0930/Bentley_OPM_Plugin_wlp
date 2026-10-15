using System;
using System.Linq;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static void AddTarget(ulong id,int dn,string supportId,string parentId)
        {
            var root=FakeState.Elements[100].Clone();root.ElementId=id;
            var native=root.Items.Values.Single(v=>v.ClassDefinition.Name=="SSP_PIPE_CLAMP");
            native.InstanceId=supportId;native["PARENT_ID"].StringValue=parentId;
            string tag="A1-DN"+dn+"-C1";native["ALIAS"].StringValue=tag;
            root.Items["PipeSupportComponents/PipeSupportAssembly_A1"]["AssemblyTag"].StringValue=tag;
            var source=new NativePipeSupportRecord{Code="A1",NativeClass="SSP_PIPE_CLAMP",Dn=dn,
                SupportInstanceId=supportId,PipeInstanceId=parentId,IsoTag=tag};
            root.Items["SteelSectionProbeNativeSupports/PlacedPipeSupport"]["Payload"].StringValue=new JavaScriptSerializer().Serialize(source);
            FakeState.Elements.Add(id,root);
            var parent=FakeState.Elements[10].Clone();parent.ElementId=id+500;
            var pipe=parent.Items.Values.Single();pipe.InstanceId=parentId;
            pipe["NOMINAL_DIAMETER"].StringValue=(dn/FakeState.MmPerSchemaUnit).ToString(System.Globalization.CultureInfo.InvariantCulture);
            pipe["LINENUMBER"].StringValue="P-"+dn;
            FakeState.Elements.Add(parent.ElementId,parent);
        }
        private static SupportBindingTarget Bind(ulong id,params ulong[] members)
        {
            var target=SupportBindingReader.ReadTarget(Located(id));var draft=SupportBindingComposer.Copy(target.Binding);
            draft.Members.Clear();foreach(ulong member in members)draft.Members.Add(SupportBindingReader.ReadMember(Located(member)));
            return SupportBindingEditor.Apply(target,draft);
        }
        private static SupportBindingMaterialRecord[] Materials()
        {return FakeState.Elements.Values.Select(SupportBindingStore.ReadMaterial).Where(r=>r!=null).ToArray();}
        private static void BomChecks()
        {
            Fixture();
            Bind(100,200);
            Check(Materials().Length==0,"保存绑定不创建材料附注");
            Check(SupportBindingReader.ReadTarget(Located(100)).Alias.Contains("(2)G4"),"钢构编号仍写在管夹引注");
            Check(FakeState.Elements[200].Items.Count==1,"钢构本体与材料清单未复制或改写");
            Check(SupportBindingMaterials.Description("G4-∠50×5")=="G4-L50x5","材料描述使用ASCII符号");
            PlantNote();
            Bind(100,200);
            Check(Materials().Length==0,"再次保存删除已有材料附注");
            PlantNote();
            FakeState.Fault="note-delete";
            Reject(()=>Bind(100),"删除已有附注失败时回滚解除");
            Check(Materials().Length==1&&BMECApi.Instance.DeferCommits,"删除失败保留附注并恢复提交开关");
            FakeState.Fault="";
            SupportBindingEditor.SynchronizeAllMaterials();
            Check(Materials().Length==0,"全模型同步删除遗留材料附注");
            Fixture();var binding=Draft(SupportBindingReader.ReadTarget(Located(100)),200);
            Check(SupportBindingComposer.Compose(binding,true).All(c=>c>=32&&c<=126),"完整ISO组合引注为ASCII");
            Fixture();var legacy=Draft(SupportBindingReader.ReadTarget(Located(100)),200);
            SupportBindingStore.Write(FakeState.Elements[100],legacy);
            FakeState.Elements[100].Items["SteelSectionProbeSupportBindings/SupportBinding"]["Payload"].StringValue=new JavaScriptSerializer().Serialize(legacy);
            FakeState.Instance("support-1")["ALIAS"].StringValue="①A1-DN100-C1$②G4-A-500-250";
            var oldTarget=SupportBindingReader.ReadTarget(Located(100));
            var migrated=SupportBindingEditor.Apply(oldTarget,SupportBindingComposer.Copy(oldTarget.Binding));
            Check(migrated.Alias=="(1)A1-DN100-C1$ (2)G4-A-500-250"&&Materials().Length==0,"旧绑定保存升级引注且不补材料附注");
            string canonical=SupportBindingStore.Encode(migrated.Binding);
            Check(SupportBindingStore.Encode(SupportBindingStore.Decode(canonical))==canonical,"绑定JSON编解码与反射缓存无关，输出顺序稳定");
        }
        private static void PlantNote()
        {
            var element=new Element{ElementId=900};
            FakeState.Elements[900]=element;
            var instance=new Bentley.DgnPlatformNET.DgnEC.IDgnECInstance{InstanceId="old-note"};
            instance.ClassDefinition.Name="ADDITIONAL_MATERIAL";
            instance.ClassDefinition.Schema.Name="OpenPlant_3D";
            instance["PARENT_ID"].StringValue="pipe-1";
            instance["TEXT"].StringValue="G4-A-500-250";
            element.Items["OpenPlant_3D/ADDITIONAL_MATERIAL"]=instance;
            SupportBindingStore.WriteMaterial(element,new SupportBindingMaterialRecord{
                ModelId=Session.Instance.GetActiveDgnModel().GetModelId().ToString(),
                CarrierElementId=200,ItemType="PipeSupportAssembly_T_FRAME_G4",Tag="G4-A-500-250",
                OwnerSupportInstanceId="support-1",ParentInstanceId="pipe-1",OwnerDn=100,NoteInstanceId="old-note"});
        }
    }
}
