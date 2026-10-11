using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 只拥有未确认箱体；替换失败时保留旧预览及删除失败的新元素。
    /// </summary>
    internal sealed class HoseCabinetPreviewSession
    {
        private FireCabinetBuildResult preview;
        private HoseCabinetPlan plan;
        private readonly List<Element> cleanup = new List<Element>();
        internal bool HasPreview
        {
            get
            {
                return preview != null;
            }
        }
        internal string Warning
        {
            get
            {
                return preview == null ? "" : preview.Warning;
            }
        }

        internal void Show(HoseCabinetPlan next, DPoint3d origin)
        {
            Drain();
            FireCabinetBuildResult replacement = HoseCabinetBuilder.Build(next, origin);
            StatusInt status = replacement.Cell.AddToModel();
            if (status != StatusInt.Success)
            {
                throw new InvalidOperationException("水龙柜预览写入失败：" + status);
            }
            try
            {
                if (preview != null)
                {
                    Delete(preview.Cell);
                }
            }
            catch
            {
                try
                {
                    Delete(replacement.Cell);
                }
                catch
                {
                    cleanup.Add(replacement.Cell);
                }
                throw;
            }

            preview = replacement;
            plan = next;
        }

        internal void Confirm()
        {
            Drain();
            if (preview == null)
            {
                throw new InvalidOperationException("没有可确认的水龙柜预览。");
            }
            HoseCabinetStatistics.Attach(preview.Cell, plan);
            preview = null;
            plan = null;
        }

        internal void Cancel()
        {
            Drain();
            if (preview != null)
            {
                Delete(preview.Cell);
            }
            preview = null;
            plan = null;
        }

        private void Drain()
        {
            for (int index = cleanup.Count - 1; index >= 0; index--)
            {
                Delete(cleanup[index]);
                cleanup.RemoveAt(index);
            }
        }

        private static void Delete(Element element)
        {
            if (element == null || !element.IsValid)
            {
                return;
            }
            StatusInt status = element.DeleteFromModel();
            if (status != StatusInt.Success)
            {
                throw new InvalidOperationException("水龙柜预览删除失败：" + status);
            }
        }
    }
}
