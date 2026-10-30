using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class HandrailPreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("围栏");
        private HandrailPlan plan;
        internal bool HasPreview {get{return ownership.HasPreview;}}
        internal void Show(HandrailPlan next)
        {
            ownership.Invalidate();plan=null;
            var parts=HandrailBuilder.Build(next);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                HandrailCatalog.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("围栏 预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的 围栏 预览。");
            ownership.Confirm(element=>Statistics.AttachHandrail(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
