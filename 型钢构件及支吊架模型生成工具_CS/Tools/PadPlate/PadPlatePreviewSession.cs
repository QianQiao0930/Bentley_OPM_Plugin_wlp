using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class PadPlatePreviewSession
    {
        private Element preview;
        private PadPlatePlan plan;
        internal bool HasPreview { get { return preview!=null; } }
        internal void Show(PadPlatePlan next)
        {
            var parts=PadPlateBuilder.Build(next);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),next.CellName,
                DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("垫板预览写入失败："+status);
            try{Delete(preview);}catch{Delete(replacement);throw;}
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            if(preview==null||plan==null)throw new InvalidOperationException("没有可确认的垫板预览。");
            Statistics.AttachPadPlate(preview,plan);preview=null;plan=null;
        }
        internal void Cancel(){Delete(preview);preview=null;plan=null;}
        private static void Delete(Element element)
        {if(element==null||!element.IsValid)return;var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("垫板预览删除失败："+status);}
    }
}
