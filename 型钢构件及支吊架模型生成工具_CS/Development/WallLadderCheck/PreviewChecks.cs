using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
namespace Bentley.DgnPlatformNET {internal enum StatusInt {Success,Failure}}
namespace Bentley.DgnPlatformNET.Elements
{
    internal class Element
    {
        internal bool IsValid=true,Written;
        internal StatusInt AddStatus=StatusInt.Success,DeleteStatus=StatusInt.Success;
        internal StatusInt AddToModel(){if(AddStatus==StatusInt.Success)Written=true;return AddStatus;}
        internal StatusInt DeleteFromModel(){if(DeleteStatus==StatusInt.Success){Written=false;IsValid=false;}return DeleteStatus;}
        internal Bentley.DgnPlatformNET.TransformInfo Transform;
        internal void ApplyTransform(Bentley.DgnPlatformNET.TransformInfo transform){Transform=transform;}
    }
}
namespace SteelSectionProbe
{
    internal static class PreviewChecks
    {
        internal static void Run(Action<bool,string> check)
        {
            var s=new WallLadderPreviewSession();var a=new Element();var b=new Element();s.Show(new[]{a,b});s.Confirm();s.Cancel();check(a.Written&&b.Written&&!s.HasPreview,"confirmed two cells retained");
            a=new Element();b=new Element{AddStatus=StatusInt.Failure};Reject(()=>s.Show(new[]{a,b}));check(!a.Written&&!s.HasPreview,"second cell add failure rolls back first");
            a=new Element{DeleteStatus=StatusInt.Failure};b=new Element{AddStatus=StatusInt.Failure};Reject(()=>s.Show(new[]{a,b}));check(a.Written&&s.HasPreview,"partial rollback failure owned");Reject(s.Confirm);a.DeleteStatus=StatusInt.Success;s.Cancel();check(!a.Written,"partial write cleanup retry");
            a=new Element{DeleteStatus=StatusInt.Failure};b=new Element();s.Show(new[]{a,b});var x=new Element();var y=new Element();Reject(()=>s.Show(new[]{x,y}));check(a.Written&&b.Written&&!x.Written&&!y.Written,"old deletion failure rolls back both new cells");Reject(s.Confirm);a.DeleteStatus=StatusInt.Success;s.Cancel();check(!a.Written&&!b.Written,"retry cleans both old cells");
            a=new Element{DeleteStatus=StatusInt.Failure};s.Show(new[]{a});x=new Element{DeleteStatus=StatusInt.Failure};y=new Element();Reject(()=>s.Show(new[]{x,y}));check(a.Written&&x.Written&&!y.Written,"multiple retained failure ownership");Reject(s.Cancel);a.DeleteStatus=x.DeleteStatus=StatusInt.Success;s.Cancel();check(!a.Written&&!x.Written,"retained cleanup retry");
            a=new Element();b=new Element();s.Show(new[]{a,b});s.Invalidate();Reject(s.Confirm);s.Cancel();check(!a.Written&&!b.Written,"dirty preview cancellation");s.Cancel();check(!s.HasPreview,"repeat cleanup");
            a=new Element();s.Show(new[]{a});x=new Element();y=new Element();s.Show(new[]{x,y});check(!a.Written&&x.Written&&y.Written,"cage switch replaces group count");y.IsValid=false;Reject(s.Confirm);s.Cancel();check(!x.Written&&!s.HasPreview,"externally deleted child group");
        }
        private static void Reject(Action action){try{action();}catch(InvalidOperationException){return;}throw new Exception("Expected preview failure");}
    }
}
