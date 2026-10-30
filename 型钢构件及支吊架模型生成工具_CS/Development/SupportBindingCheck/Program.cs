using System;
using System.IO;
using System.Linq;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static int checks;
        private static void Check(bool value,string label){checks++;if(!value)throw new Exception(label);}
        private static void Reject(Action action,string label)
        {try{action();}catch(InvalidOperationException){checks++;return;}catch(ArgumentException){checks++;return;}throw new Exception("应拒绝："+label);}
        private static LocatedElement Located(ulong id){return new LocatedElement{ModelRef=FakeState.Model,ElementId=id};}
        private static Element Fixture(string className="SSP_PIPE_CLAMP")
        {
            FakeState.Reset();
            ItemTypeLibrary.Create("PipeSupportComponents",FakeState.File,false);
            var root=new Element{ElementId=100};FakeState.Elements.Add(100,root);
            var pipe=new Element{ElementId=10};FakeState.Elements.Add(10,pipe);
            var parent=FakeState.Item(pipe,"OpenPlant_3D","PIPE","pipe-1");
            parent["NOMINAL_DIAMETER"].StringValue="100";parent["LINENUMBER"].StringValue="P-100";
            string tag=className=="SSP_PIPE_CLAMP"?"A1-DN100-C1":"F6-A-DN100-250";
            var native=FakeState.Item(root,"OpenPlant_3D",className,"support-1");
            native["ALIAS"].StringValue=tag;native["DEVICE_TYPE_CODE"].StringValue=className=="SSP_PIPE_CLAMP"?"SSPPC":"SSPTR";
            native["SSP_RECIPE"].StringValue="opaque-original-recipe";
            native["SUPPORT_POINT_X"].StringValue="1234.5";native["NAME"].StringValue="unique-native-name";
            native["PARENT_ID"].StringValue="pipe-1";
            native["DESCRIPTION"].StringValue="ORIGINAL-BOM";
            var record=new NativePipeSupportRecord{Code=className=="SSP_PIPE_CLAMP"?"A1":"F6",NativeClass=className,
                SupportInstanceId="support-1",PipeInstanceId="pipe-1",IsoTag=tag,Dn=100};
            FakeState.Item(root,"SteelSectionProbeNativeSupports","PlacedPipeSupport")["Payload"].StringValue=new JavaScriptSerializer().Serialize(record);
            Assembly(root,"PipeSupportAssembly_A1",tag);
            foreach(ulong id in new[]{200UL,201UL})
            {
                var member=new Element{ElementId=id};FakeState.Elements.Add(id,member);
                Assembly(member,"PipeSupportAssembly_T_FRAME_G4","G4-A-500-250");
            }
            return root;
        }
        private static void Assembly(Element root,string name,string tag)
        {
            var item=FakeState.Item(root,"PipeSupportComponents",name);
            item["RecordKind"].StringValue="Assembly";item["AssemblyTag"].StringValue=tag;item["SupportType"].StringValue="支架";
        }
        private static SupportBindingRecord Draft(SupportBindingTarget target,params ulong[] members)
        {
            var value=SupportBindingComposer.Copy(target.Binding);
            foreach(ulong id in members)value.Members.Add(SupportBindingReader.ReadMember(Located(id)));
            return value;
        }
        private static void DataChecks()
        {
            foreach(string className in new[]{"SSP_PIPE_CLAMP","SINGLE_PIPE_TRUNNION","DOUBLE_PIPE_TRUNNION","SIMPLE_ELBOW_SUPPORT","SSP_TRUNNION","SUPPORT_LOCATION"})
            foreach(bool deferred in new[]{false,true})
            {
                Fixture(className);BMECApi.Instance.DeferCommits=deferred;
                var before=SupportBindingReader.ReadTarget(Located(100));
                var draft=Draft(before,200,201);
                string expected="(1)"+before.BaseTag+"$ (2)G4-A-500-250$ (3)G4-A-500-250";
                Check(SupportBindingComposer.Compose(draft,true)==expected,"不同构件相同编号保留两行");
                Check(SupportBindingComposer.ComposeMaterial(draft)=="(1)"+before.BaseTag+" (2)G4-A-500-250 (3)G4-A-500-250","材料描述用空格分隔编号");
                Check(SupportBindingComposer.Compose(draft,false).Contains(Environment.NewLine),"页面使用普通换行");
                var updated=SupportBindingEditor.Apply(before,draft);
                Check(updated.Alias==expected,"原生ALIAS组合编码 "+className);
                Check(FakeState.Instance("support-1")["DESCRIPTION"].StringValue==SupportBindingComposer.ComposeMaterial(draft),"保存后材料描述为编号列表");
                Check(updated.BaseTag==before.BaseTag&&updated.NativePayload==before.NativePayload,"原单件编号和身份记录保持");
                var native=FakeState.Instance("support-1");
                Check(native["SSP_RECIPE"].StringValue=="opaque-original-recipe"&&native["SUPPORT_POINT_X"].StringValue=="1234.5"&&
                    native["NAME"].StringValue=="unique-native-name"&&native["PARENT_ID"].StringValue=="pipe-1","配方/位置/原生身份/父管保持");
                Check(BMECApi.Instance.DeferCommits==deferred&&TransactionManager.Closes==2,"独立事务且恢复提交开关");
                Check(FakeState.Elements[200].Items.Count==1&&FakeState.Elements[201].Items.Count==1,"不复制或改写承重支架材料");
                Check(!FakeState.Libraries[SupportBindingStore.LibraryName].Types.Keys.Any(n=>n.StartsWith("PipeSupportAssembly_")),"组合不新增材料记录");
                var reopened=SupportBindingReader.ReadTarget(Located(100));
                Check(reopened.Binding.Members.Count==2,"持久记录重读");
                draft=SupportBindingComposer.Copy(reopened.Binding);draft.Members.Reverse();
                updated=SupportBindingEditor.Apply(reopened,draft);
                Check(updated.Binding.Members[0].ElementId==201,"调整顺序持久化");
                draft=SupportBindingComposer.Copy(updated.Binding);draft.Members.Clear();
                updated=SupportBindingEditor.Apply(updated,draft);
                Check(updated.Alias==before.BaseTag&&updated.Binding.Members.Count==0,"解除全部恢复原单行编号");
                Check(FakeState.Instance("support-1")["DESCRIPTION"].StringValue=="ORIGINAL-BOM","解除全部恢复原材料描述");
            }
            foreach(string fault in new[]{"serialize","item-write","library-write","drop-alias","drop-item"})
            {
                Fixture();var before=SupportBindingReader.ReadTarget(Located(100));var draft=Draft(before,200);
                FakeState.Fault=fault;Reject(()=>SupportBindingEditor.Apply(before,draft),"失败注入 "+fault);
                Check(TransactionManager.Rollbacks==1&&BMECApi.Instance.DeferCommits,"失败回滚且恢复提交开关 "+fault);
                Check(SupportBindingReader.ReadTarget(Located(100)).Alias==before.Alias,"失败恢复原引注 "+fault);
                Check(SupportBindingReader.ReadTarget(Located(100)).BindingPayload=="","失败不留绑定记录 "+fault);
            }
            Fixture();var original=SupportBindingReader.ReadTarget(Located(100));var changes=Draft(original,200);
            FakeState.Fault="rollback";
            try{SupportBindingEditor.Apply(original,changes);throw new Exception("应失败");}
            catch(AggregateException ex){Check(ex.Message.Contains("恢复未完成"),"回滚失败明确提示");}
            Check(BMECApi.Instance.DeferCommits,"回滚失败也恢复提交开关");
            foreach(string change in new[]{"alias","delete-member","change-tag","lock","read-only","model","file","detached","license","undo","copied-root"})
            {
                Fixture();var before=SupportBindingReader.ReadTarget(Located(100));var draft=Draft(before,200);
                switch(change)
                {
                    case "alias":FakeState.Instance("support-1")["ALIAS"].StringValue="other";break;
                    case "delete-member":FakeState.Elements[200].IsDeleted=true;break;
                    case "change-tag":FakeState.Elements[200].Items.Values.Single()["AssemblyTag"].StringValue="G4-B-new";break;
                    case "lock":FakeState.Elements[100].Locked=true;break;
                    case "read-only":FakeState.Model.IsReadOnly=true;break;
                    case "model":FakeState.Token++;break;
                    case "file":FakeState.File.Name="other.dgn";break;
                    case "detached":FakeState.Detached=true;break;
                    case "license":LicenseService.IsActivated=false;break;
                    case "undo":TransactionManager.IsUndoInProgress=true;break;
                    case "copied-root":var copy=FakeState.Elements[100].Clone();copy.ElementId=101;FakeState.Elements[101]=copy;break;
                }
                if(change=="copied-root")Reject(()=>SupportBindingReader.ReadTarget(Located(101)),change);
                else Reject(()=>SupportBindingEditor.Apply(before,draft),change);
                Check(FakeState.Serializes==0,"校验失败不写原生对象 "+change);
            }
            Fixture();var clean=SupportBindingReader.ReadTarget(Located(100));var duplicate=Draft(clean,200,200);
            Reject(()=>SupportBindingComposer.Compose(duplicate,true),"同一元素重复");
            foreach(string tag in new[]{"", " ","A$B","A\nB","A\rB","A\u2028B",new string('x',257)})
                Reject(()=>SupportBindingComposer.ValidateTag(tag),"非法单件编号");
            Reject(()=>SupportBindingStore.Decode("{}"),"缺少版本");
            var bad=SupportBindingComposer.Copy(clean.Binding);bad.Version=2;Reject(()=>SupportBindingStore.Encode(bad),"未知版本");
            var maximum=SupportBindingComposer.Copy(clean.Binding);
            for(int i=0;i<19;i++)maximum.Members.Add(new SupportBindingMember{ElementId=(ulong)i+1,ModelId="1",Tag="G4-"+i,ItemType="PipeSupportAssembly_T_FRAME_G4"});
            Check(SupportBindingComposer.Compose(maximum,true).Contains("(20)G4-18"),"ASCII序号支持20行");
            maximum.Members.Add(new SupportBindingMember{ElementId=99,ModelId="1",Tag="G4",ItemType="PipeSupportAssembly_T_FRAME_G4"});
            Reject(()=>SupportBindingStore.Encode(maximum),"超过19个承重支架");
            Check(!SupportBindingComposer.IsCarrier("PipeSupportAssembly_A1")&&!SupportBindingComposer.IsCarrier("PipeSupportAssembly_STEEL_HANDRAIL"),"拒绝管夹和围栏充当承重钢构");
        }
        private static void Click(SupportBindingPage page,string name){((Button)page.FindName(name)).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));}
        private static void Pump(){Dispatcher.CurrentDispatcher.Invoke(()=>{},DispatcherPriority.Background);}
        private static bool Enabled(SupportBindingPage page,string name){return ((Button)page.FindName(name)).IsEnabled;}
        private static void UiChecks(string output)
        {
            Fixture();AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=true;
            var page=new SupportBindingPage();page.OnActivated();page.OnActivated();NativePanelLayout.Apply(page);
            Click(page,"PickTargetButton");Click(page,"PickTargetButton");
            Check(SupportBindingLocateTool.IsActive&&AccuSnap.SnapEnabled,"重复开始幂等");
            DgnElementSetTool.Pick(FakeState.Elements[100]);Pump();
            Check(!SupportBindingLocateTool.IsActive&&!AccuSnap.SnapEnabled&&AccuSnap.LocateEnabled,"选择管夹后恢复原捕捉");
            Check(Enabled(page,"AddMemberButton")&&!Enabled(page,"ConfirmButton"),"读取原管夹不自动写入");
            Click(page,"AddMemberButton");DgnElementSetTool.Pick(FakeState.Elements[200]);Pump();
            Check(Enabled(page,"ConfirmButton")&&((TextBox)page.FindName("PreviewText")).Text.Contains("(2)G4"),"添加后预览并允许保存");
            DgnElementSetTool.Pick(FakeState.Elements[201]);Pump();
            var list=(ListBox)page.FindName("MembersList");list.SelectedIndex=1;Click(page,"UpButton");
            Check(list.SelectedIndex==0,"顺序调整");
            Click(page,"ConfirmButton");
            Check(Enabled(page,"ConfirmButton")&&SupportBindingReader.ReadTarget(Located(100)).Binding.Members[0].ElementId==201,"页面保存顺序且允许再次核对计材");
            list.SelectedIndex=0;Click(page,"UpButton");
            Click(page,"ReloadButton");
            Check(list.Items.Count==2&&SupportBindingReader.ReadTarget(Located(100)).Binding.Members[0].ElementId==201,"重新读取放弃未保存的顺序");
            list.SelectedIndex=0;Click(page,"RemoveButton");
            Check(list.Items.Count==1&&SupportBindingReader.ReadTarget(Located(100)).Binding.Members.Count==1,"移除立即保存，再点管夹不会读回已删关联");
            FakeState.Elements[200].Items.Values.Single()["AssemblyTag"].StringValue="G4-B-500-500";
            Click(page,"RefreshMembersButton");
            Check(Enabled(page,"ConfirmButton")&&((TextBox)page.FindName("PreviewText")).Text.Contains("G4-B-500-500"),"核对读取改号且等待保存");
            Click(page,"ConfirmButton");
            Check(SupportBindingReader.ReadTarget(Located(100)).Alias.Contains("G4-B-500-500"),"更新编号保存到ISO引注");
            FakeState.Elements[200].IsDeleted=true;Click(page,"RefreshMembersButton");
            Check(MainWindow.Current.LastStatus.Contains("核对失败")&&list.Items.Count==1,"核对删除提示并保留列表供移除");
            FakeState.Elements[200].IsDeleted=false;
            Click(page,"ClearButton");
            Check(SupportBindingReader.ReadTarget(Located(100)).Alias=="A1-DN100-C1","页面解除全部立即恢复原编号");
            Click(page,"AddMemberButton");DgnElementSetTool.Pick(FakeState.Elements[200]);Pump();
            FakeState.Fault="serialize";Click(page,"ConfirmButton");
            Check(Enabled(page,"ConfirmButton")&&MainWindow.Current.LastStatus.Contains("保存失败"),"保存失败保留草稿供重试");
            FakeState.Fault="";Click(page,"ConfirmButton");
            TransactionManager.UndoEvent();Check(!Enabled(page,"AddMemberButton")&&!Enabled(page,"ConfirmButton"),"Undo后清空过期快照");
            Click(page,"PickTargetButton");DgnElementSetTool.Pick(FakeState.Elements[100]);page.OnDeactivated();Pump();
            Check(!Enabled(page,"AddMemberButton"),"离开阻止排队点取回调");
            page.OnActivated();Click(page,"PickTargetButton");DgnElementSetTool.Pick(FakeState.Elements[100]);Click(page,"StopButton");Pump();
            Check(!Enabled(page,"AddMemberButton"),"结束点取阻止延迟回调");
            Click(page,"PickTargetButton");DgnElementSetTool.Pick(FakeState.Elements[100]);Pump();
            foreach(Size size in new[]{new Size(400,560),new Size(400,600),new Size(400,880),new Size(400,1080),new Size(520,720)})
            {
                page.Measure(size);page.Arrange(new Rect(new Point(),size));page.UpdateLayout();Pump();
                var confirm=(Button)page.FindName("ConfirmButton");var operation=(FrameworkElement)page.FindName("OperationCard");
                Point pos=confirm.TranslatePoint(new Point(),page);
                Check(pos.Y>=0&&pos.Y+confirm.ActualHeight<=size.Height,"保存按钮小窗口可见 "+size);
                foreach(var button in Children<Button>(page).Where(b=>b.IsVisible))
                {
                    Point point=button.TranslatePoint(new Point(),page);
                    Check(point.X>=-.1&&point.X+button.ActualWidth<=size.Width+.1,"按钮边界 "+button.Name+size);
                }
                Point before=operation.TranslatePoint(new Point(),page);
                ((ScrollViewer)page.FindName("ParameterScroll")).ScrollToBottom();page.UpdateLayout();
                Check(operation.TranslatePoint(new Point(),page)==before,"操作区固定 "+size);
                foreach(double dpi in new[]{1d,1.25,1.5,2})
                {
                    var bitmap=new RenderTargetBitmap((int)(size.Width*dpi),(int)(size.Height*dpi),96*dpi,96*dpi,PixelFormats.Pbgra32);bitmap.Render(page);
                    Check(bitmap.PixelHeight==(int)(size.Height*dpi),"四档DPI "+size+dpi);
                    if(size.Width==400&&size.Height==880&&dpi==1)
                    {
                        var png=new PngBitmapEncoder();png.Frames.Add(BitmapFrame.Create(bitmap));
                        using(var file=File.Create(Path.Combine(output,"support-binding-400-880.png")))png.Save(file);
                    }
                }
            }
            page.OnWorkspaceClosing();page.OnWorkspaceClosing();
            Check(!SupportBindingLocateTool.IsActive&&!AccuSnap.SnapEnabled&&AccuSnap.LocateEnabled,"关闭幂等且恢复捕捉");
        }
        private static System.Collections.Generic.IEnumerable<T> Children<T>(DependencyObject parent) where T:DependencyObject
        {if(parent is T)yield return (T)parent;for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++)foreach(var child in Children<T>(VisualTreeHelper.GetChild(parent,i)))yield return child;}
        [STAThread] private static int Main(string[] args)
        {
            try
            {
                DataChecks();
                BomChecks();
                LocateSelectionChecks();
                string output=args.Length==0?Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"previews"):args[0];Directory.CreateDirectory(output);
                UiChecks(output);
                Console.WriteLine("PASS: "+checks+" 组合绑定领域、真实Reader/Store/Editor、点取及页面检查。");return 0;
            }
            catch(Exception error){Console.Error.WriteLine(error);return 1;}
        }
    }
}
