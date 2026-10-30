using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class BracketPreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("三角架");
        private BracketPlan plan;
        internal bool HasPreview{get{return ownership.HasPreview;}}
        internal void Show(BracketPlan next,PipeClampSelection line)
        {
            ownership.Invalidate();plan=null;
            var parts=BracketBuilder.Build(next,line);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                next.Double?"N4_DOUBLE_BRACKET":"N3_SINGLE_BRACKET",
                DPoint3d.Zero,DMatrix3d.Identity,parts);
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("三角架预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的三角架预览。");
            ownership.Confirm(element=>Statistics.AttachBracket(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
