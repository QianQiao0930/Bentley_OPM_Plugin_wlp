using System;
using System.Linq;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static int checks;
        private static void Check(bool pass,string name){checks++;if(!pass)throw new Exception(name);}
        private static void Reject(Action action,string name){bool failed=false;try{action();}catch{failed=true;}Check(failed,name);}
        private static PipeClampPreviewSession Preview(PipeClampKind kind,bool native=true,double scale=1000,int direction=0,bool reset=true,string material="C1")
        {
            if(reset)World.Reset();
            int originalRoots=World.Elements.Count;
            Bentley.MstnPlatformNET.Session.Instance.Model.Scale=scale;World.Pipe.SourceUorPerMm=scale;
            var axis=kind==PipeClampKind.U3BearingUBolt?new DVector3d(0,0,direction==1?-1:1):
                kind==PipeClampKind.E1Guide||kind==PipeClampKind.K1Limit?new DVector3d(direction==1?0:1,direction==1?1:0,0):
                direction==0?new DVector3d(1,0,0):direction==1?new DVector3d(0,1,0):new DVector3d(.6,0,.8);
            World.Pipe.EndX=World.Pipe.StartX+2000*axis.X;World.Pipe.EndY=World.Pipe.StartY+2000*axis.Y;World.Pipe.EndZ=World.Pipe.StartZ+2000*axis.Z;
            World.Pipe.IsPipe=native;
            var p=new DPoint3d(World.Pipe.StartX+600*axis.X,World.Pipe.StartY+600*axis.Y,World.Pipe.StartZ+600*axis.Z);
            var c=new DPoint3d(p.X*scale,p.Y*scale,p.Z*scale);
            var session=new PipeClampPreviewSession();
            var a1=A1ClampCalculator.Calculate(100,true,100,45,"PIPE-X",material);
            var ring=new A22ClampPlan{Dn=100,ColdThicknessMm=40,BoltDiameterMm=12,Number="CUSTOM",Specification="CUSTOM"};
            var shoe=new T4ShoeLayout{Dn=100,ShoeLengthMm=300,InsulationMm=80,Number="CUSTOM"};
            switch(kind)
            {
                case PipeClampKind.A1UBolt:session.ShowA1(a1,c,axis);break;
                case PipeClampKind.U3BearingUBolt:session.ShowU3(new U3ClampPlan{Clamp=a1,Subitem="G",MaterialCode="C1",Number="U3-X"},c,axis);break;
                case PipeClampKind.A2StandardTwoBolt:session.ShowA2(A2ClampCalculator.Calculate(new A2ClampParameters{MaterialCode=material},true,100,20),c,axis);break;
                case PipeClampKind.A22ColdTwoBolt:session.ShowA22(ring,c,axis);break;
                case PipeClampKind.A24ColdFourBolt:session.ShowA24(ring,c,axis);break;
                case PipeClampKind.E1Guide:session.ShowE1(new E1GuidePlan{Dn=100,Item=new E1GuideItem{Key="B",ProfileName="L50x5"},HeightMm=107,CenterXmm=p.X,CenterYmm=p.Y,CenterZmm=p.Z,PipeX=axis.X,PipeY=axis.Y,Number="E1-B-107"});break;
                case PipeClampKind.K1Limit:session.ShowK1(new K1LimitPlan{Dn=100,SubitemKey="B",ExistingWidthMm=100,Number="K1-X"},c,axis);break;
                case PipeClampKind.T4Insulated:session.ShowT4(shoe,new T4ShoeBooleanLayout(),c,axis,true,true);break;
                case PipeClampKind.L2ColdShoe:session.ShowL2(shoe,new T4ShoeBooleanLayout(),c,axis,true,true);break;
            }
            session.BindSource(World.Pipe);
            Check(World.Elements.Count==originalRoots&&World.Displays.Count==1,"预览仅暂态显示，无模型残留 "+kind);
            return session;
        }
        private static void SameGeometry(DPoint3d[] a,DPoint3d[] b)
        {
            Check(a.Length==b.Length,"实体采样数量保持");
            for(int i=0;i<a.Length;i++)Check(Math.Abs(a[i].X-b[i].X)<1e-5&&Math.Abs(a[i].Y-b[i].Y)<1e-5&&Math.Abs(a[i].Z-b[i].Z)<1e-5,"局部化再放置保持原预览外形");
        }
        private static int Main()
        {
            try
            {
                var label=NativePipeSupportDefinition.Create("E1",100,"E1-B-107","B-∠50×50×5");
                Check(label.Label=="E1-B-107"&&label.Description=="E1-DN100-B-L50x50x5 PIPE GUIDE","显示编号与详细BOM描述分开");
                Check(NativePipeSupportDefinition.Create("A2",100,"DN100","").Label=="DN100","无连字符的现有AssemblyTag原样保留");
                string longTag=new string('X',150)+"-0001";
                Check(NativePipeSupportDefinition.Create("E1",100,longTag,"").Label==longTag,"不截断编号或擅自删除原编号尾段");
                Check(NativePipeSupportDefinition.Create("A1",100,"A1-DN100-M12-45°","").Label.EndsWith("45°"),"原编号角度符号保持");
                Reject(()=>NativePipeSupportDefinition.Create("UNKNOWN",100,"X",""),"未知类别不生成含糊标注");
                Reject(()=>NativePipeSupportDefinition.Create("A1",0,"X",""),"非法DN不生成标注");
                foreach(var invalid in new[]{null,""," ","X\nY","X\rY","X$Y"})
                    Reject(()=>NativePipeSupportDefinition.Create("E1",100,invalid,""),"空编号与意外ISO控制符拒绝");
                var serializer=new JavaScriptSerializer();
                var oldPreferences=serializer.Deserialize<PipeClampLastChoice.Data>("{\"A1DnIndex\":2,\"A2Insulation\":\"20\",\"T4Name\":\"OLD\"}");
                Check(oldPreferences.A1MaterialCode=="C1"&&oldPreferences.A2MaterialCode=="C1"&&oldPreferences.T4Name=="OLD","旧偏好默认材料C1并保留其他类别");
                oldPreferences.A1MaterialCode="S";oldPreferences.A2MaterialCode="A2";
                var preferences=serializer.Deserialize<PipeClampLastChoice.Data>(serializer.Serialize(oldPreferences));
                Check(preferences.A1MaterialCode=="S"&&preferences.A2MaterialCode=="A2","A1/A2材料代码可独立持久化");
                foreach(var namedKind in new[]{PipeClampKind.A1UBolt,PipeClampKind.A2StandardTwoBolt})
                foreach(var material in new[]{"C1"," s ","a2"})
                foreach(bool native in new[]{true,false})
                {
                    var named=Preview(namedKind,native,material:material);named.Confirm();
                    string expected=PipeClampCatalog.Type(namedKind).Code+"-DN100-"+material.Trim().ToUpperInvariant();
                    var root=World.Elements.Values.Single(e=>e.ElementId!=1);
                    Check(root.MaterialTag==expected,"A1/A2普通/原生清单采用新编号 "+namedKind);
                    if(native) {
                        var record=serializer.Deserialize<NativePipeSupportRecord>(root.Metadata["Payload"].StringValue);
                        Check(World.Created.Instance["ALIAS"].StringValue==expected&&record.IsoTag==expected,"新编号原样传入ISO引注记录");
                    }
                }
                foreach(var kind in PipeClampCatalog.All.Select(t=>t.Kind))
                foreach(double scale in new[]{1d,1000d,10000d})
                foreach(double schemaUnit in new[]{1d,25.4d,1000d})
                foreach(int direction in new[]{0,1,2})
                {
                    var session=Preview(kind,true,scale,direction);World.SupportPointMmPerUnit=schemaUnit;BMECApi.Instance.DeferCommits=true;
                    DPoint3d[] expected;using(var proto=session.CreatePrototype())expected=proto.Geometry;
                    session.Confirm();
                    Check(session.LastConfirmedNative&&!session.HasPreview,"九类别确认释放所有权 "+kind);
                    Check(World.Elements.Count==2&&World.Displays.Count==0,"只留下父管和一个原生根，无重复预览");
                    Check(World.Created.Instance.ClassDefinition.Name=="SSP_PIPE_CLAMP"&&World.Created.IsParametric,"使用正式参数化原生组件类");
                    string code=PipeClampCatalog.Type(kind).Code;
                    Check(World.Created.Instance["NAME"].StringValue.StartsWith("SSPPC-"),"原生实例保留独立自动编号");
                    Check(World.Created.Instance["DESCRIPTION"].StringValue.All(ch=>ch>=32&&ch<=126),"ISO描述无中文缺字");
                    Check(World.Created.Instance["NOMINAL_DIAMETER"].StringValue=="100","兼容支架位置类的字符串DN");
                    var element=World.Find(World.Created.Instance);
                    SameGeometry(expected,element.Geometry);
                    var record=new JavaScriptSerializer().Deserialize<NativePipeSupportRecord>(element.Metadata["Payload"].StringValue);
                    string json=World.Created.Instance["SSP_RECIPE"].StringValue;
                    var recipe=NativePipeSupportRecipeCodec.Decode(json);
                    Check(recipe.Code==code&&recipe.Dn==100&&record.RecipeVersion==1,"持久配方类别/DN/版本正确");
                    Check(NativePipeSupportRecipeCodec.Encode(recipe)==json,"完整计划含内部字段往返无损 "+kind);
                    var script=new NativePipeSupportComponent { BMECObject=new ParametricSetupValues { Source=World.Created.Instance } };
                    script.Setup();Check(script.HostCalls==0&&script.LengthCalls==0,"正式组件构造Setup不提前要求父管");
                    Reject(()=>script.PrepareGraphics(),"正式组件几何阶段仍拒绝缺失父管");
                    script.BMECObject.ParentReady=true;script.PrepareGraphics();
                    Check(script.HostCalls==2&&script.LengthCalls==1,"正式组件绑定后初始化端口与操作长度");
                    using(var local=NativePipeSupportRecipeGraphics.BuildLocal(script.RecipeForCheck))
                    {
                        var edited=World.Created.Transform3d;
                        edited.Translation.X+=12*scale;edited.Translation.Z-=35*scale;
                        var moved=local.Geometry.Select(edited.Apply).ToArray();
                        Check(moved.Length==expected.Length,"原生重生成保留所有子图形");
                        for(int i=0;i<moved.Length;i++)
                            Check(Math.Abs(moved[i].X-expected[i].X-12*scale)<1e-5&&Math.Abs(moved[i].Y-expected[i].Y)<1e-5&&Math.Abs(moved[i].Z-expected[i].Z+35*scale)<1e-5,"配方重建服从当前变换且无二次平移");
                    }
                    Check(World.Elements.Count==2&&element.MaterialTag==World.Created.Instance["ALIAS"].StringValue,"重生成不另写模型或重复材料记录");
                    Check(record.Code==code&&record.PipeInstanceId==World.Source.InstanceId&&record.SupportInstanceId==World.Created.Instance.InstanceId,"根元素保存可追溯记录");
                    Check(!string.IsNullOrEmpty(element.MaterialTag)&&element.CellName==PipeClampCatalog.Type(kind).CellName,"原材料清单及Cell名称保持");
                    Check(World.Created.Instance["ALIAS"].StringValue==element.MaterialTag&&record.IsoTag==element.MaterialTag,"引注严格等于原材料AssemblyTag，不追加编号");
                    Check(record.NativeName==World.Created.Instance["NAME"].StringValue&&record.NativeName!=record.IsoTag,"记录分别追溯显示编号与实例编号");
                    if(kind==PipeClampKind.E1Guide)Check(record.IsoTag=="E1-B-107","用户示例E1-B-107完整保留");
                    Check(BMECApi.Instance.DeferCommits,"成功恢复宿主开关");
                    session.Cancel();Check(World.Elements.Count==2,"关闭不删除已确认原生支架");
                    TransactionManager.CancelToPosition(1,false);
                    Check(World.Elements.Count==1&&World.Displays.Count==0,"撤销创建不会复活普通预览");
                }
                foreach(var kind in PipeClampCatalog.All.Select(t=>t.Kind))
                {
                    var session=Preview(kind,false);session.Confirm();
                    Check(!session.LastConfirmedNative&&World.Created==null&&World.Elements.Count==2&&World.Displays.Count==0&&World.Elements.Values.Single(e=>e.Instance==null).CellName==PipeClampCatalog.Type(kind).CellName,"辅助线保持普通Cell与原名称 "+kind);
                    session.Cancel();Check(World.Elements.Count==2,"取消不删普通确认件");
                    session=Preview(kind);World.Pipe.IsFromReference=true;session.BindSource(World.Pipe);session.Confirm();
                    Check(!session.LastConfirmedNative&&World.Created==null,"参考来源不伪造活动管关联 "+kind);
                    foreach(string fault in new[]{"Create","Serialize","Cache","Statistics","Metadata","Relationship","WrongOrigin","Parametric","IsoPointWrite","IsoPointDropped","StateDropped","Transform","DisplayClose","AliasDropped","MarkerDropped","ReadbackAliasDropped","RecipeDropped","ReadbackRecipeDropped"})
                    {
                        session=Preview(kind);World.Fault=fault;BMECApi.Instance.DeferCommits=true;
                        Reject(session.Confirm,"确认失败明确抛错 "+kind+"/"+fault);
                        Check(World.Elements.Count==1&&session.HasPreview&&World.Displays.Count==1,"失败回收新原生根并保留可重试预览");
                        Check(BMECApi.Instance.DeferCommits,"失败恢复宿主开关");
                        World.Fault="";session.Cancel();Check(World.Elements.Count==1&&World.Displays.Count==0,"失败后可取消干净");
                    }
                }
                foreach(string change in new[]{"axis","unit","model","dn","deleted","locked","identity"})
                {
                    var session=Preview(PipeClampKind.A1UBolt);
                    switch(change){case "axis":World.Pipe.EndX+=10;break;case "unit":Bentley.MstnPlatformNET.Session.Instance.Model.Scale=2;break;case "model":Bentley.MstnPlatformNET.Session.Instance.Model.Handle=3;break;case "dn":World.Pipe.NominalMm=200;break;case "deleted":World.Elements.Clear();break;case "locked":World.Elements[1].Locked=true;break;case "identity":World.Source.ClassDefinition.Name="ELBOW";break;}
                    Reject(session.Confirm,"预览后源变化拒绝 "+change);Check(World.Created==null,"拒绝前不创建业务对象");session.Cancel();
                }
                var retry=Preview(PipeClampKind.A1UBolt);
                foreach(string fault in new[]{"DisplayCreate","PreviewDelete"})
                {
                    World.Fault=fault;Reject(()=>retry.ShowA1(A1ClampCalculator.Calculate(100,true,100,0,""),new DPoint3d(1,2,3),new DVector3d(1,0,0)),"更新暂态失败");
                    Check(World.Elements.Count==1&&World.Displays.Count==1&&retry.HasPreview,"更新失败保留旧预览");
                }
                World.Fault="";retry.Cancel();
                retry=Preview(PipeClampKind.A1UBolt);World.Fault="DisplayClose";
                Reject(()=>retry.ShowA1(A1ClampCalculator.Calculate(100,true,100,0,""),new DPoint3d(1,2,3),new DVector3d(1,0,0)),"更新时新旧暂态都无法释放");
                Check(World.Elements.Count==1&&World.Displays.Count==2,"清理失败仍保留全部暂态所有权");
                World.Fault="";retry.Cancel();Check(World.Displays.Count==0,"取消重试回收所有暂态");
                retry=Preview(PipeClampKind.A1UBolt);World.Fault="Metadata";Reject(retry.Confirm,"首轮确认故障");
                World.Fault="";retry.Confirm();Check(World.Elements.Count==2&&World.Displays.Count==0&&retry.LastConfirmedNative,"失败后原预览可直接重试确认");
                var repeated=Preview(PipeClampKind.E1Guide);repeated.Confirm();
                var first=World.Created.Instance;
                repeated=Preview(PipeClampKind.E1Guide,reset:false);repeated.Confirm();
                Check(World.Elements.Count==3&&first.InstanceId!=World.Created.Instance.InstanceId,"同编号的两个支架保留独立原生身份");
                Check(first["NAME"].StringValue!=World.Created.Instance["NAME"].StringValue&&
                    first["ALIAS"].StringValue=="E1-B-107"&&World.Created.Instance["ALIAS"].StringValue=="E1-B-107","同规格重复放置不污染显示编号");
                var validSession=Preview(PipeClampKind.A1UBolt);validSession.Confirm();
                string validJson=World.Created.Instance["SSP_RECIPE"].StringValue;
                Reject(()=>NativePipeSupportRecipeCodec.Decode(validJson.Replace("\"Version\":1","\"Version\":2")),"未知配方版本拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode(validJson.Replace("\"Version\":1,","")),"配方缺版本拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode("{\"__type\":\"System.IO.FileInfo\","+validJson.Substring(1)),"外部CLR类型提示拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode("{\"Unknown\":1,"+validJson.Substring(1)),"配方未知字段拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode(validJson.Replace("\"Code\":\"A1\"","\"Code\":\"UNKNOWN\"")),"未知配方类别拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode("null"),"空配方拒绝");
                Reject(()=>NativePipeSupportRecipeCodec.Decode(new string('X',131073)),"超长配方拒绝");
                var badRecipe=NativePipeSupportRecipeCodec.Decode(validJson);badRecipe.CenterMm=new[]{0d,1d};
                Reject(()=>NativePipeSupportRecipeCodec.Encode(badRecipe),"坐标缺失拒绝");
                badRecipe=NativePipeSupportRecipeCodec.Decode(validJson);badRecipe.Axis=new[]{0d,0d,0d};
                Reject(()=>NativePipeSupportRecipeCodec.Encode(badRecipe),"零管轴拒绝");
                badRecipe=NativePipeSupportRecipeCodec.Decode(validJson);badRecipe.A1.Row.OutsideMm=double.NaN;
                Reject(()=>NativePipeSupportRecipeCodec.Encode(badRecipe),"嵌套尺寸非有限拒绝");
                badRecipe=NativePipeSupportRecipeCodec.Decode(validJson);badRecipe.K1=new K1LimitPlan{Dn=100};
                Reject(()=>NativePipeSupportRecipeCodec.Encode(badRecipe),"混入其他类别计划拒绝");
                badRecipe=NativePipeSupportRecipeCodec.Decode(validJson);badRecipe.A1=null;
                Reject(()=>NativePipeSupportRecipeCodec.Encode(badRecipe),"当前类别缺计划拒绝");
                CheckTrunnions();
                Console.WriteLine("PASS: "+checks+" 管夹及耳轴真实会话/共用原生写入/暂态生命周期/单位/关联/失败与撤销检查（API替身，不代替OPM出图实测）。");return 0;
            }
            catch(Exception e){Console.Error.WriteLine(e);return 1;}
        }
    }
}
