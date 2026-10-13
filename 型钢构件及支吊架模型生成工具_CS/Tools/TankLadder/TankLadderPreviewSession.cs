using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>保留全部未确认预览的所有权，删除失败时仍可再次清理。</summary>
    internal sealed class TankLadderPreviewSession
    {
        private readonly List<Element> owned = new List<Element>();
        private Element candidate;
        internal bool HasPreview { get { return owned.Count > 0; } }
        internal void Invalidate() { candidate = null; }

        internal void Show(Element replacement)
        {
            Invalidate();
            if (replacement == null || !replacement.IsValid) throw new InvalidOperationException("水箱爬梯预览无效。");
            var status = replacement.AddToModel();
            if (status != StatusInt.Success) throw new InvalidOperationException("水箱爬梯预览写入失败：" + status);
            var previous = owned.ToArray();
            owned.Add(replacement);
            try
            {
                foreach (var old in previous) { Delete(old); owned.Remove(old); }
                candidate = replacement;
            }
            catch (Exception error)
            {
                try { Delete(replacement); owned.Remove(replacement); }
                catch (Exception cleanup) { throw new InvalidOperationException(error.Message + "；新预览清理失败：" + cleanup.Message, error); }
                throw;
            }
        }

        internal void Confirm()
        {
            if (candidate == null || !candidate.IsValid || owned.Count != 1)
                throw new InvalidOperationException("没有可确认的完整水箱爬梯预览，请更新预览。");
            owned.Clear(); candidate = null;
        }

        internal void Cancel()
        {
            Invalidate();
            var errors = new List<string>();
            foreach (var element in owned.ToArray())
                try { Delete(element); owned.Remove(element); } catch (Exception ex) { errors.Add(ex.Message); }
            if (errors.Count > 0) throw new InvalidOperationException(string.Join("；", errors));
        }

        private static void Delete(Element element)
        {
            if (!element.IsValid) return;
            var status = element.DeleteFromModel();
            if (status != StatusInt.Success) throw new InvalidOperationException("水箱爬梯预览删除失败：" + status);
        }
    }
}
