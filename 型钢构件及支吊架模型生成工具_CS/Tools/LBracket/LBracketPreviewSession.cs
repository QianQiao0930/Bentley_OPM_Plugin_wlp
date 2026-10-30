using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class LBracketPreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("D7 ");
        private LBracketPlan plan;
        internal bool HasPreview {get{return ownership.HasPreview;}}
        internal void Show(LBracketPlan next)
        {
            ownership.Invalidate();plan=null;
            var parts=LBracketBuilder.Build(next);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                LBracketCatalog.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("D7 预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的 D7 预览。");
            ownership.Confirm(element=>Statistics.AttachLBracket(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
