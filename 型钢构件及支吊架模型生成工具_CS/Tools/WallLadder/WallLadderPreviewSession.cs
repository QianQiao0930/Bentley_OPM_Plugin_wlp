using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
namespace SteelSectionProbe
{
    internal sealed class WallLadderPreviewSession
    {
        private readonly List<Element> owned=new List<Element>();
        private Element[] candidate;
        internal bool HasPreview {get{return owned.Count>0;}}
        internal void Invalidate(){candidate=null;}
        internal void Show(Element[] replacements)
        {
            Invalidate();
            if(replacements==null||replacements.Length<1||replacements.Length>2||replacements.Any(p=>p==null||!p.IsValid)||replacements.Distinct().Count()!=replacements.Length)
                throw new InvalidOperationException("墙面爬梯预览不完整。");
            var previous=owned.ToArray();var added=new List<Element>();
            try
            {
                foreach(var e in replacements)
                {
                    var status=e.AddToModel();if(status!=StatusInt.Success)throw new InvalidOperationException("墙面爬梯预览写入失败："+status);
                    owned.Add(e);added.Add(e);
                }
                foreach(var e in previous){Delete(e);owned.Remove(e);}
                candidate=replacements.ToArray();
            }
            catch(Exception ex)
            {
                var errors=new List<string>();
                foreach(var e in added)try{Delete(e);owned.Remove(e);}catch(Exception cleanup){errors.Add(cleanup.Message);}
                if(errors.Count>0)throw new InvalidOperationException(ex.Message+"；回收失败："+string.Join("；",errors),ex);
                throw;
            }
        }
        internal void Confirm()
        {
            if(candidate==null||candidate.Length!=owned.Count||candidate.Any(p=>!p.IsValid||!owned.Contains(p)))throw new InvalidOperationException("没有可确认的完整爬梯预览，请更新预览。");
            owned.Clear();candidate=null;
        }
        internal void Cancel()
        {
            Invalidate();var errors=new List<string>();
            foreach(var e in owned.ToArray())try{Delete(e);owned.Remove(e);}catch(Exception ex){errors.Add(ex.Message);}
            if(errors.Count>0)throw new InvalidOperationException(string.Join("；",errors));
        }
        private static void Delete(Element e)
        {if(!e.IsValid)return;var status=e.DeleteFromModel();if(status!=StatusInt.Success)throw new InvalidOperationException("墙面爬梯预览删除失败："+status);}
    }
}
