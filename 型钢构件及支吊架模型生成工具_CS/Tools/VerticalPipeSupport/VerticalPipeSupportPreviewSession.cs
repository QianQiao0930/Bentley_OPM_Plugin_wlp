using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class VerticalPipeSupportPreviewSession
    {
        private Element preview;
        private VerticalPipeSupportPlan plan;
        internal bool HasPreview { get { return preview!=null; } }
        internal void Show(VerticalPipeSupportPlan next,DPoint3d center,DVector3d axis)
        {
            var parts=VerticalPipeSupportBuilder.Build(next,center,axis);
            var model=Session.Instance.GetActiveDgnModel();
            var replacement=new CellHeaderElement(model,"VERTICAL_PIPE_SUPPORT",DPoint3d.Zero,
                DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success) throw new InvalidOperationException("立管耳轴预览写入失败："+status);
            try { Delete(preview); }
            catch { Delete(replacement);throw; }
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            if(preview==null||plan==null) throw new InvalidOperationException("没有可确认的立管耳轴预览。");
            Statistics.AttachVerticalPipeSupport(preview,plan);
            preview=null;plan=null;
        }
        internal void Cancel() { Delete(preview);preview=null;plan=null; }
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid) return;
            var result=element.DeleteFromModel();
            if(result!=StatusInt.Success) throw new InvalidOperationException("删除立管耳轴预览失败："+result);
        }
    }
}
