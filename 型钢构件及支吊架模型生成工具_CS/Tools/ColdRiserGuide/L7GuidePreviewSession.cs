using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class L7GuidePreviewSession
    {
        private Element preview;
        private L7GuidePlan plan;
        internal bool HasPreview {get{return preview!=null;}}
        internal void Show(L7GuidePlan next,DPoint3d center,DVector3d axis)
        {
            var model=Session.Instance.GetActiveDgnModel();
            var parts=L7GuideBuilder.Build(next,center,axis);
            var replacement=new CellHeaderElement(model,L7GuideCatalog.CellName(next),
                DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success) throw new InvalidOperationException("导向架预览写入失败："+status);
            try {Delete(preview);}
            catch {Delete(replacement);throw;}
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            if(preview==null) throw new InvalidOperationException("没有可确认的 导向架预览。");
            Statistics.AttachL7Guide(preview,plan);
            preview=null;plan=null;
        }
        internal void Cancel() {Delete(preview);preview=null;plan=null;}
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("删除 导向架预览失败："+status);
        }
    }
}
