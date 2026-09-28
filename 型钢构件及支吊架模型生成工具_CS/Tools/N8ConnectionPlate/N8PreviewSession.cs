using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class N8PreviewSession
    {
        private Element preview;
        private N8Plan plan;
        internal bool HasPreview { get { return preview!=null; } }
        internal void Show(N8Plan next,DPoint3d origin)
        {
            var parts=N8Builder.Build(next,origin);
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),
                "N8_CONNECTION_PLATE",DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("N8 预览写入失败："+status);
            try { Delete(preview); } catch {Delete(replacement);throw;}
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            if(preview==null||plan==null)throw new InvalidOperationException("没有 N8 预览。");
            Statistics.AttachN8(preview,plan);preview=null;plan=null;
        }
        internal void Cancel() {Delete(preview);preview=null;plan=null;}
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("N8 预览删除失败："+status);
        }
    }
}
