using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>持有所有已写入但未确认的预览，失败后仍可重试清理。</summary>
    internal sealed class PreviewElementOwnership
    {
        private readonly string name;
        private readonly List<Element> owned = new List<Element>();
        private Element candidate;

        internal PreviewElementOwnership(string name) { this.name = name; }
        internal bool HasPreview { get { return owned.Count > 0; } }
        internal bool CanConfirm
        {
            get { return candidate != null && candidate.IsValid && owned.Count == 1; }
        }

        internal void Invalidate() { candidate = null; }

        /// <summary>仅接收 AddToModel 已成功的元素，立即登记所有权后再删除旧预览。</summary>
        internal void ReplaceWrittenElement(Element replacement)
        {
            Invalidate();
            var previous = owned.ToArray();
            owned.Add(replacement);
            try
            {
                foreach (var old in previous)
                {
                    Delete(old);
                    owned.Remove(old);
                }
                candidate = replacement;
            }
            catch (Exception error)
            {
                try
                {
                    Delete(replacement);
                    owned.Remove(replacement);
                }
                catch (Exception cleanup)
                {
                    throw new InvalidOperationException(error.Message + "；新预览清理失败：" + cleanup.Message, error);
                }
                throw;
            }
        }

        internal void Confirm(Action<Element> finalize)
        {
            if (!CanConfirm)
                throw new InvalidOperationException("没有可确认的完整" + name + "预览，请更新预览。");
            if (finalize != null) finalize(candidate);
            owned.Clear();
            candidate = null;
        }

        internal void Cancel()
        {
            Invalidate();
            var errors = new List<string>();
            foreach (var element in owned.ToArray())
            {
                try
                {
                    Delete(element);
                    owned.Remove(element);
                }
                catch (Exception error) { errors.Add(error.Message); }
            }
            if (errors.Count > 0) throw new InvalidOperationException(string.Join("；", errors));
        }

        private void Delete(Element element)
        {
            if (element == null || !element.IsValid) return;
            var status = element.DeleteFromModel();
            if (status != StatusInt.Success)
                throw new InvalidOperationException(name + "预览删除失败：" + status);
        }
    }
}
