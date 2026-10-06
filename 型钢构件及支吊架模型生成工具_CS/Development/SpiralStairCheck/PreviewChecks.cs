// 测试替身只用于验证实际会话的所有权/回退，不代表Bentley实体实测。
using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
namespace Bentley.DgnPlatformNET
{
    internal enum StatusInt {Success,Failure}
}
namespace Bentley.DgnPlatformNET.Elements
{
    internal sealed class Element
    {
        internal bool Written,IsValid=true;
        internal StatusInt AddStatus,DeleteStatus;
        internal StatusInt AddToModel(){if(AddStatus==StatusInt.Success)Written=true;return AddStatus;}
        internal StatusInt DeleteFromModel(){if(DeleteStatus==StatusInt.Success){Written=false;IsValid=false;}return DeleteStatus;}
    }
}
namespace SteelSectionProbe
{
    internal static class Statistics
    {
        internal static int Writes;
        internal static void AttachHandrail(Element e,HandrailPlan p){if(!e.Written)throw new Exception("统计目标未写入");Writes++;}
    }
    internal static class PreviewChecks
    {
        private static void Check(bool ok,string name){if(!ok)throw new Exception(name);}
        private static void Reject(Action action){try{action();}catch(InvalidOperationException){return;}throw new Exception("会话错误未拒绝");}
        private static SpiralStairBuildResult Result(params Element[] elements)
        {var r=new SpiralStairBuildResult();r.Elements.AddRange(elements);return r;}
        internal static void Run()
        {
            var session=new SpiralStairPreviewSession();var structure=new Element();var railing=new Element();var next=Result(structure,railing);
            next.Railings.Add(new KeyValuePair<Element,HandrailPlan>(railing,new HandrailPlan()));
            session.Show(next);Check(structure.Written&&railing.Written&&Statistics.Writes==0,"预览禁止最终统计");
            session.Confirm();Check(Statistics.Writes==1&&!session.HasPreview,"确认解除所有权");session.Cancel();Check(structure.Written&&railing.Written,"确认后取消不得删除");
            var first=new Element();var fail=new Element{AddStatus=StatusInt.Failure};Reject(()=>session.Show(Result(first,fail)));Check(!first.Written&&!session.HasPreview,"部分写入失败回退");
            var old=new Element();session.Show(Result(old));var broken=new Element{AddStatus=StatusInt.Failure};Reject(()=>session.Show(Result(broken)));Check(old.Written&&session.HasPreview,"重建失败保留旧预览");Reject(()=>session.Confirm());session.Cancel();Check(!old.Written,"取消旧预览");
            var stuck=new Element{DeleteStatus=StatusInt.Failure};session.Show(Result(stuck));Reject(()=>session.Cancel());Check(session.HasPreview&&stuck.Written,"删除失败保留所有权");Reject(()=>session.Confirm());stuck.DeleteStatus=StatusInt.Success;session.Cancel();Check(!session.HasPreview,"删除可重试");
            old=new Element{DeleteStatus=StatusInt.Failure};session.Show(Result(old));var replacement=new Element();Reject(()=>session.Show(Result(replacement)));Check(old.Written&&!replacement.Written&&session.HasPreview,"旧预览删除失败回退新预览");old.DeleteStatus=StatusInt.Success;session.Cancel();
            var leaked=new Element{DeleteStatus=StatusInt.Failure};Reject(()=>session.Show(Result(leaked,new Element{AddStatus=StatusInt.Failure})));Check(session.HasPreview&&leaked.Written,"回退失败也保留新元素所有权");Reject(()=>session.Confirm());leaked.DeleteStatus=StatusInt.Success;session.Cancel();
            Console.WriteLine("盘梯会话：确认/取消、重建失败、部分写入及删除失败重试检查通过（API替身）。");
        }
    }
}
