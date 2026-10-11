using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal sealed class NozzlePreviewSession
    {
        private Element preview;
        internal string WriteElapsed { get; private set; }
        internal bool HasPreview { get { return preview!=null; } }
        internal void Regenerate(NozzlePlan plan,DPoint3d origin)
        {
            var replacement=NozzleBuilder.Build(plan,origin);
            string elapsed;
            var status=WriteDuration.Measure(replacement.AddToModel,out elapsed);
            if(status!=StatusInt.Success) throw new InvalidOperationException("写入管口预览失败："+status);
            try { DeleteOwned(preview); }
            catch { DeleteOwned(replacement);throw; }
            preview=replacement;
            WriteElapsed=elapsed;
        }
        internal void Confirm()
        {
            if(preview==null)throw new InvalidOperationException("请先点取基点生成预览。");
            preview=null;
        }
        internal void Cancel()
        { DeleteOwned(preview);preview=null; }
        private static void DeleteOwned(Element element)
        {
            if(element==null || !element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("删除管口预览失败："+status);
        }
    }
}
