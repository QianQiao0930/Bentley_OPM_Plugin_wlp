using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        // 直接调用真实SupportBindingLocateTool.Begin/End和真实ProbeLocateTool。
        // 替身会把安装时未清空的选择集编入议程，使一次点击走修改/退出分支。
        private static void LocateSelectionChecks()
        {
            var picked=new List<ulong>();
            Action<LocatedElement> onPicked=value=>picked.Add(value.ElementId);
            SupportBindingLocateTool.Picked+=onPicked;
            try
            {
                Fixture();AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=true;
                SelectionSetManager.Selected.Add(FakeState.Elements[200]);
                SupportBindingLocateTool.Begin();
                Check(DgnElementSetTool.SelectedBeforeOnInstall==0&&DgnElementSetTool.SelectedInBaseOnInstall==0,
                    "已有选择在InstallTool之前已清空，宿主安装也收到空选择集");
                Check(SelectionSetManager.NumSelected()==0&&DgnElementSetTool.AgendaAdoptions==0&&DgnElementSetTool.Tool.UsesDirectPick,
                    "真实组合绑定工具忽略选择与围栅并直接点取");
                DgnElementSetTool.Pick(FakeState.Elements[201]);
                Check(picked.Count==1&&picked[0]==201&&DgnElementSetTool.LocateCalls==1&&SupportBindingLocateTool.IsActive,
                    "已有选择后第一次点击即走真实DoLocate和Picked回调");
                SupportBindingLocateTool.End();
                Check(SelectionSetManager.NumSelected()==0&&!SupportBindingLocateTool.IsActive&&!AccuSnap.SnapEnabled&&AccuSnap.LocateEnabled,
                    "结束点取恢复捕捉但不恢复已放弃选择");

                Fixture();
                DgnElementSetTool.BeforeInstall=()=>SelectionSetManager.Selected.Add(FakeState.Elements[200]);
                SupportBindingLocateTool.Begin();
                Check(DgnElementSetTool.SelectedBeforeOnInstall==1&&DgnElementSetTool.SelectedInBaseOnInstall==0&&SelectionSetManager.NumSelected()==0,
                    "构造后安装前出现的选择在base.OnInstall之前再清空");
                SupportBindingLocateTool.End();

                Fixture();
                bool agendaEmptyBeforePost=false;
                DgnElementSetTool.AfterBaseInstall=()=>DgnElementSetTool.Tool.SeedSelectionAgenda(FakeState.Elements[200]);
                DgnElementSetTool.BeforePostInstall=()=>agendaEmptyBeforePost=DgnElementSetTool.Tool.ElementAgenda.IsEmpty&&DgnElementSetTool.Tool.UsesDirectPick;
                SupportBindingLocateTool.Begin();
                Check(agendaEmptyBeforePost,"OnInstall在宿主安装结束后立即清议程并复位Pick来源");
                SupportBindingLocateTool.End();

                Fixture();
                DgnElementSetTool.BeforePostInstall=()=>
                {
                    SelectionSetManager.Selected.Add(FakeState.Elements[200]);
                    DgnElementSetTool.Tool.SeedSelectionAgenda(FakeState.Elements[200]);
                };
                SupportBindingLocateTool.Begin();
                Check(SelectionSetManager.NumSelected()==0&&DgnElementSetTool.Tool.ElementAgenda.IsEmpty&&DgnElementSetTool.Tool.UsesDirectPick,
                    "OnPostInstall再次清空宿主安装期间出现的选择与议程");
                SupportBindingLocateTool.End();

                Fixture();
                SelectionSetManager.Selected.Add(FakeState.Elements[200]);SupportBindingLocateTool.Begin();
                var active=DgnElementSetTool.Tool;
                SelectionSetManager.Selected.Add(FakeState.Elements[201]);active.SeedSelectionAgenda(FakeState.Elements[201]);
                int beforeRepeat=picked.Count;
                SupportBindingLocateTool.Begin();
                Check(ReferenceEquals(active,DgnElementSetTool.Tool)&&DgnElementSetTool.InstallCalls==1&&SelectionSetManager.NumSelected()==0&&active.ElementAgenda.IsEmpty,
                    "重复开始复用工具并直接放弃新选择、清空议程");
                DgnElementSetTool.Pick(FakeState.Elements[200]);
                Check(picked.Count==beforeRepeat+1&&SupportBindingLocateTool.IsActive,"重复开始后一次点击即可定位");
                SelectionSetManager.Selected.Add(FakeState.Elements[201]);
                SupportBindingLocateTool.End();
                Check(SelectionSetManager.Selected.Count==1&&SelectionSetManager.Selected[0].ElementId==201,
                    "结束不触碰点取期间用户新增选择，也不归还旧选择");

                Fixture();
                DgnElementSetTool.DelayCleanup=true;
                SelectionSetManager.Selected.Add(FakeState.Elements[200]);SupportBindingLocateTool.Begin();SupportBindingLocateTool.End();
                Check(DgnElementSetTool.PendingCleanup.Count==1&&SelectionSetManager.NumSelected()==0,"旧工具已结束但宿主清理延迟");
                SelectionSetManager.Selected.Add(FakeState.Elements[201]);SupportBindingLocateTool.Begin();
                var next=DgnElementSetTool.Tool;
                SelectionSetManager.Selected.Add(FakeState.Elements[200]);
                DgnElementSetTool.DrainCleanup();
                Check(SupportBindingLocateTool.IsActive&&ReferenceEquals(next,DgnElementSetTool.Tool)&&SelectionSetManager.Selected.Count==1&&SelectionSetManager.Selected[0].ElementId==200,
                    "旧工具延迟Cleanup不恢复旧选择、不删除新选择且不结束新工具");
                int beforeDelayed=picked.Count;DgnElementSetTool.Pick(FakeState.Elements[201]);
                Check(picked.Count==beforeDelayed+1,"延迟清理后新工具仍能一次定位");
                DgnElementSetTool.DelayCleanup=false;SupportBindingLocateTool.End();

                foreach(bool silent in new[]{false,true})
                {
                    Fixture();AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=true;
                    SelectionSetManager.Selected.Add(FakeState.Elements[200]);
                    SelectionSetManager.ThrowOnEmpty=!silent;SelectionSetManager.IgnoreEmpty=silent;
                    RejectSelectionClear(()=>SupportBindingLocateTool.Begin(),"构造清空"+(silent?"未生效":"异常"));
                    Check(DgnElementSetTool.InstallCalls==0&&!SupportBindingLocateTool.IsActive&&!AccuSnap.SnapEnabled&&AccuSnap.LocateEnabled,
                        "选择集清理失败不安装，也不改变捕捉 "+silent);
                }

                Fixture();AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=true;
                DgnElementSetTool.BeforeInstall=()=>{SelectionSetManager.Selected.Add(FakeState.Elements[201]);SelectionSetManager.ThrowOnEmpty=true;};
                RejectSelectionClear(()=>SupportBindingLocateTool.Begin(),"OnInstall清空失败");
                Check(DgnElementSetTool.InstallCalls==1&&DgnElementSetTool.BaseInstallCalls==0&&!SupportBindingLocateTool.IsActive&&!AccuSnap.SnapEnabled,
                    "安装前清空失败不进入宿主base.OnInstall且恢复捕捉");
                SelectionSetManager.ThrowOnEmpty=false;DgnElementSetTool.Cleanup(DgnElementSetTool.Tool);
                Check(SelectionSetManager.Selected.Count==1&&SelectionSetManager.Selected[0].ElementId==201,"失败后的Cleanup不修改当前选择");

                Fixture();AccuSnap.SnapEnabled=false;AccuSnap.LocateEnabled=true;
                SelectionSetManager.Selected.Add(FakeState.Elements[200]);FakeState.Fault="tool-install";
                Reject(()=>SupportBindingLocateTool.Begin(),"宿主安装异常");
                Check(!SupportBindingLocateTool.IsActive&&SelectionSetManager.NumSelected()==0&&!AccuSnap.SnapEnabled&&AccuSnap.LocateEnabled,
                    "宿主安装失败恢复捕捉但不归还已清空选择");
                DgnElementSetTool.Cleanup(DgnElementSetTool.Tool);
                Check(SelectionSetManager.NumSelected()==0,"宿主安装失败后的Cleanup也不恢复选择");

                Fixture();SupportBindingLocateTool.Begin();
                SelectionSetManager.Selected.Add(FakeState.Elements[201]);SelectionSetManager.ThrowOnEmpty=true;
                RejectSelectionClear(()=>SupportBindingLocateTool.Begin(),"重复开始清空失败");
                Check(DgnElementSetTool.InstallCalls==1&&DgnElementSetTool.LocateCalls==0,"重复开始清空失败不重装或误定位");
                SelectionSetManager.ThrowOnEmpty=false;SupportBindingLocateTool.Begin();
                int beforeRetry=picked.Count;DgnElementSetTool.Pick(FakeState.Elements[200]);
                Check(picked.Count==beforeRetry+1&&SelectionSetManager.NumSelected()==0,"选择清理恢复后可直接重试点取");
                SupportBindingLocateTool.End();
            }
            finally
            {
                SelectionSetManager.ThrowOnEmpty=SelectionSetManager.IgnoreEmpty=false;
                DgnElementSetTool.DelayCleanup=false;
                SupportBindingLocateTool.End();DgnElementSetTool.DrainCleanup();
                SupportBindingLocateTool.Picked-=onPicked;
            }
        }

        private static void RejectSelectionClear(Action action,string stage)
        {
            try { action(); }
            catch(InvalidOperationException error)
            {
                Check(error.Message.Contains("清空")&&error.Message.Contains("选择集"),stage+"明确报告中文选择集失败");
                return;
            }
            throw new Exception("应拒绝："+stage);
        }
    }
}
