using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class PadPlatePreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("垫板");
        private PadPlatePlan plan;
        internal bool HasPreview { get { return ownership.HasPreview; } }
        internal void Show(PadPlatePlan next)
        {
            ownership.Invalidate();plan=null;
            var parts=PadPlateBuilder.Build(next);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),next.CellName,
                DPoint3d.Zero,DMatrix3d.Identity,parts);
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("垫板预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的垫板预览。");
            ownership.Confirm(element=>Statistics.AttachPadPlate(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
