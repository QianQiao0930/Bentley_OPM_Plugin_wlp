using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// G2 预览生命周期：重建时先写入新版预览、成功后再删除旧版；
    /// 确认时才写入 <c>PipeSupportComponents</c> ItemType（预览阶段只出几何），
    /// 取消与离开页面都会清掉未确认元素。
    /// </summary>
    internal sealed class G2AnchorPreviewSession
    {
        private Element preview;
        private G2AnchorPlan plan;

        internal bool HasPreview { get { return preview!=null; } }
        internal G2AnchorPlan Plan { get { return plan; } }

        internal void Regenerate(G2AnchorPlan next,DPoint3d origin)
        {
            if(next==null) throw new ArgumentNullException("next");
            var parts=G2AnchorBuilder.Build(next,origin);
            var model=Session.Instance.GetActiveDgnModel();
            var replacement=new CellHeaderElement(model,G2AnchorCatalog.CellName,
                DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("G2 锚板预览写入失败："+status);
            try { DeleteOwned(preview); }
            catch
            {
                try { DeleteOwned(replacement); }
                catch { preview=replacement; plan=null; }
                throw;
            }
            preview=replacement; plan=next;
        }

        internal void Confirm()
        {
            if(preview==null || plan==null)
                throw new InvalidOperationException("当前没有可确认的 G2 锚板预览。");
            Statistics.AttachG2Anchor(preview,plan);
            preview=null; plan=null;
        }

        internal void Cancel()
        {
            DeleteOwned(preview); preview=null; plan=null;
        }

        private static void DeleteOwned(Element element)
        {
            if(element==null || !element.IsValid) return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("删除 G2 预览失败："+status);
        }
    }
}
