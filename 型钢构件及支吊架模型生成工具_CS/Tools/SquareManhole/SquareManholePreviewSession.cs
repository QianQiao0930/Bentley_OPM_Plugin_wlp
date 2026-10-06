using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
namespace SteelSectionProbe
{
    internal sealed class SquareManholePreviewSession
    {
        private Element preview;
        internal bool HasPreview {get{return preview!=null;}}
        internal void Regenerate(SquareManholePlan plan,DPoint3d origin)
        {
            var replacement=SquareManholeBuilder.Build(plan,origin);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("方形人孔预览写入失败："+status);
            try{Delete(preview);}catch{Delete(replacement);throw;}
            preview=replacement;
        }
        internal void Confirm()
        {
            if(preview==null||!preview.IsValid)throw new InvalidOperationException("没有有效的方形人孔预览。");
            preview=null;
        }
        internal void Cancel(){Delete(preview);preview=null;}
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("方形人孔预览删除失败："+status);
        }
    }
}
