using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class PortalFramePreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("门型架");
        private PortalFramePlan plan;
        internal bool HasPreview{get{return ownership.HasPreview;}}
        internal void Show(PortalFramePlan next,PipeClampSelection line)
        {
            ownership.Invalidate();plan=null;
            var parts=PortalFrameBuilder.Build(next,line);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                next.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("门型架预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的门型架预览。");
            ownership.Confirm(element=>Statistics.AttachPortalFrame(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
