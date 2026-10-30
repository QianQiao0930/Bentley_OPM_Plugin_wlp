using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class TFramePreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("T 型架");
        private TFramePlan plan;
        internal bool HasPreview{get{return ownership.HasPreview;}}
        internal void Show(TFramePlan next,PipeClampSelection line)
        {
            ownership.Invalidate();plan=null;
            var parts=TFrameBuilder.Build(next,line);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                next.CellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("T 型架预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);plan=next;
        }
        internal string UpdateStiffener(string text)
        {
            if(!ownership.CanConfirm||plan==null||plan.Parameters.Kind!="D15")return null;
            plan.Parameters.Stiffener=text;
            plan.Number=TFrameCalculator.Number(plan.Parameters,plan.HeightMm,plan.L1Mm);
            return plan.Number;
        }
        internal void Confirm()
        {
            if(plan==null)throw new InvalidOperationException("没有可确认的 T 型架预览。");
            ownership.Confirm(element=>Statistics.AttachTFrame(element,plan));plan=null;
        }
        internal void Cancel(){plan=null;ownership.Cancel();}
    }
}
