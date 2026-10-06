using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
namespace SteelSectionProbe
{
    internal sealed class SpiralStairPreviewSession
    {
        private SpiralStairBuildResult preview;
        private bool complete;
        internal bool HasPreview {get{return preview!=null;}}
        internal void Show(SpiralStairBuildResult next)
        {
            complete=false;
            var written=new List<Element>();
            try{
                foreach(var element in next.Elements){var status=element.AddToModel();if(status!=StatusInt.Success)throw new InvalidOperationException("盘梯预览写入失败："+status);written.Add(element);}
                Cancel();preview=next;complete=true;
            }catch(Exception ex){
                var failed=new List<Element>();foreach(var e in written)try{Delete(e);}catch{failed.Add(e);}
                if(failed.Count>0){if(preview==null)preview=new SpiralStairBuildResult();preview.Elements.AddRange(failed);throw new InvalidOperationException(ex.Message+"；部分新预览清理失败，请再次取消。",ex);}throw;
            }
        }
        internal void Confirm()
        {
            if(preview==null||!complete)throw new InvalidOperationException("没有可确认的完整盘梯预览。");
            foreach(var e in preview.Elements)if(!e.IsValid)throw new InvalidOperationException("盘梯预览失效，请重新建模。");
            foreach(var rail in preview.Railings)Statistics.AttachHandrail(rail.Key,rail.Value);
            preview=null;complete=false;
        }
        internal void Cancel()
        {
            complete=false;
            if(preview==null)return;
            var errors=new List<string>();
            for(int i=preview.Elements.Count-1;i>=0;i--)try{Delete(preview.Elements[i]);preview.Elements.RemoveAt(i);}catch(Exception ex){errors.Add(ex.Message);}
            if(errors.Count>0)throw new InvalidOperationException(string.Join("；",errors));preview=null;
        }
        private static void Delete(Element e)
        {if(e==null||!e.IsValid)return;var status=e.DeleteFromModel();if(status!=StatusInt.Success)throw new InvalidOperationException("盘梯预览删除失败："+status);}
    }
}
