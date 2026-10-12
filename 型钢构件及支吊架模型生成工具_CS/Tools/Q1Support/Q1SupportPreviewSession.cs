using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal sealed class Q1SupportPreviewSession
    {
        private readonly List<Element> owned=new List<Element>();
        private Element preview;
        private Q1SupportPlan plan;
        private Q2SupportPlan q2Plan;
        internal bool HasPreview {get{return preview!=null&&preview.IsValid;}}
        internal static Element Prototype(Q1SupportPlan p,DPoint3d center,DVector3d axis)
        {return new CellHeaderElement(Session.Instance.GetActiveDgnModel(),Q1SupportCatalog.CellName,
            DPoint3d.Zero,DMatrix3d.Identity,Q1SupportBuilder.Build(p,center,axis));}
        internal void Show(Q1SupportPlan p,DPoint3d center,DVector3d axis)
        {
            Replace(Prototype(p,center,axis));plan=p;q2Plan=null;
        }
        internal static Element Prototype(Q2SupportPlan p,DPoint3d center,DVector3d axis)
        {return new CellHeaderElement(Session.Instance.GetActiveDgnModel(),Q2SupportCatalog.CellName,DPoint3d.Zero,DMatrix3d.Identity,Q2SupportBuilder.Build(p,center,axis));}
        internal void Show(Q2SupportPlan p,DPoint3d center,DVector3d axis)
        {Replace(Prototype(p,center,axis));q2Plan=p;plan=null;}
        private void Replace(Element replacement)
        {
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("支架预览写入失败："+status);
            owned.Add(replacement);
            try
            {
                foreach(var old in owned.ToArray())if(!ReferenceEquals(old,replacement))Delete(old);
            }
            catch
            {
                // 回滚失败仍保留全部待删元素的所有权，后续取消可重试。
                Delete(replacement);throw;
            }
            preview=replacement;
        }
        internal void Confirm()
        {
            if(!HasPreview||owned.Count!=1)throw new InvalidOperationException("请先成功更新并清理支架预览。");
            if(q2Plan!=null)Statistics.AttachQ2Support(preview,q2Plan);else Statistics.AttachQ1Support(preview,plan);
            owned.Remove(preview);preview=null;plan=null;q2Plan=null;
        }
        internal void Cancel()
        {
            foreach(var element in owned.ToArray())Delete(element);
            preview=null;plan=null;q2Plan=null;
        }
        private void Delete(Element element)
        {
            if(element.IsValid)
            {
                var status=element.DeleteFromModel();
                if(status!=StatusInt.Success)throw new InvalidOperationException("支架预览删除失败："+status);
            }
            owned.Remove(element);
        }
    }
}
