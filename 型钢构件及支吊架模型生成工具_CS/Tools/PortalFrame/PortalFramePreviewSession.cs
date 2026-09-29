using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class PortalFramePreviewSession
    {
        private Element preview;
        private PortalFramePlan plan;
        internal bool HasPreview{get{return preview!=null;}}
        internal void Show(PortalFramePlan next,PipeClampSelection line)
        {
            var parts=PortalFrameBuilder.Build(next,line);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                next.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("门型架预览写入失败："+status);
            try{Delete(preview);}catch{Delete(replacement);throw;}
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            if(preview==null||plan==null)throw new InvalidOperationException("没有可确认的门型架预览。");
            Statistics.AttachPortalFrame(preview,plan);
            preview=null;plan=null;
        }
        internal void Cancel(){Delete(preview);preview=null;plan=null;}
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("门型架预览删除失败："+status);
        }
    }
}
