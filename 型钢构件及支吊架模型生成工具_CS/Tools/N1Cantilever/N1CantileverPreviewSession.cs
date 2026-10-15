using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal sealed class N1CantileverPreviewSession
    {
        private Element preview;
        private N1CantileverPlan plan;
        private readonly List<Element> cleanup=new List<Element>();
        internal bool HasPreview{get{return preview!=null;}}
        internal void Show(N1CantileverPlan next,N1CantileverFrame frame)
        {
            Drain();
            var replacement=new CellHeaderElement(Session.Instance.GetActiveDgnModel(),N1CantileverCatalog.CellName,
                DPoint3d.Zero,DMatrix3d.Identity,N1CantileverBuilder.Build(next,frame));
            SupportModelLevel.Use(replacement);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("N1 预览写入失败："+status);
            try{Delete(preview);}
            catch
            {
                try{Delete(replacement);}catch{cleanup.Add(replacement);}
                throw;
            }
            preview=replacement;plan=next;
        }
        internal void Confirm()
        {
            Drain();
            if(preview==null||plan==null)throw new InvalidOperationException("没有可确认的 N1 预览。");
            Statistics.AttachN1Cantilever(preview,plan);
            preview=null;plan=null;
        }
        internal void Cancel(){Drain();Delete(preview);preview=null;plan=null;}
        private void Drain()
        {for(int i=cleanup.Count-1;i>=0;i--){Delete(cleanup[i]);cleanup.RemoveAt(i);}}
        private static void Delete(Element element)
        {
            if(element==null||!element.IsValid)return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)throw new InvalidOperationException("N1 预览删除失败："+status);
        }
    }
}
