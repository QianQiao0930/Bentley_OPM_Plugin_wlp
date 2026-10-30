using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>页面使用的活动文档图层与选择集读取，全部只读。</summary>
    internal static class EquipmentLevelUiReader
    {
        internal static EquipmentLevelDocument ReadDocument()
        {
            var model = EquipmentLevelReader.ActiveModel();
            var file = model.GetDgnFile();
            if (file == null) throw new InvalidOperationException("无法读取活动文档。");
            var cache = file.GetLevelCache() as FileLevelCache;
            if (cache == null) throw new InvalidOperationException("无法读取文档图层表。");
            var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if (app == null || app.ActiveModelReference == null)
                throw new InvalidOperationException("无法读取活动模型的图层。");
            var active = app.ActiveModelReference;
            var result = new EquipmentLevelDocument { Model = model, FileName = file.GetFileName(),
                ModelName = model.GetModelInfo().Name, ActiveLevelId = (uint)Settings.ActiveLevelId };
            foreach (LevelHandle handle in cache.GetHandles())
            {
                if (handle == null || !handle.IsValid) continue;
                var level = new EquipmentLevelChoice { Id = (uint)handle.LevelId, Name = handle.Name,
                    IsWritable = !handle.ReadOnly && !model.IsReadOnly && !file.IsReadOnly,
                    Availability = "只读", ColorHex = "未读取" };
                try
                {
                    var com = active.Levels.Find(handle.Name);
                    if (com == null || (uint)com.ID != level.Id)
                    { level.IsWritable = false; level.Availability = "不可用"; }
                    else
                    {
                        if (com.IsLocked) { level.IsWritable = false; level.Availability = "已锁定"; }
                        int oleRgb = active.InternalColorToRGBColor(com.ElementColor);
                        uint rgb = (uint)(((oleRgb & 255) << 16) | (oleRgb & 0xFF00) | ((oleRgb >> 16) & 255));
                        level.ColorHex = "#" + rgb.ToString("X6");
                    }
                }
                catch (Exception ex)
                {
                    // 无法确认 COM 对应图层时不允许写入；不从层名猜 ID。
                    level.IsWritable = false; level.Availability = "不可用";
                    EquipmentLevelLog.Write("读取图层「" + handle.Name + "」失败：" + ex.Message);
                }
                if (level.IsWritable) level.Availability = "可用";
                result.Levels.Add(level);
            }
            result.Levels = result.Levels.OrderBy(l => l.Name, StringComparer.CurrentCultureIgnoreCase).ToList();
            return result;
        }

        internal static EquipmentLevelSelection ReadSelection()
        {
            var result = new EquipmentLevelSelection { Model = EquipmentLevelReader.ActiveModel() };
            if (!SelectionSetManager.IsActive()) return result;
            var seen = new HashSet<ulong>();
            for (uint index = 0; index < SelectionSetManager.NumSelected(); index++)
            {
                Element element = null;
                DgnModelRef modelRef = null;
                if (SelectionSetManager.GetElement(index, ref element, ref modelRef) != StatusInt.Success || element == null)
                    throw new InvalidOperationException("选择集中有无法读取的元素，请重新选择。");
                var entry = EquipmentLevelReader.Classify(modelRef, element.ElementId);
                if (entry.Verdict == EquipmentLevelVerdict.Equipment)
                {
                    if (seen.Add(entry.ElementId)) result.Equipment.Add(entry);
                }
                else result.Rejected.Add(entry);
            }
            ReadChildCounts(result);
            return result;
        }

        /// <summary>沿修改时使用的实际包含树统计图形，不写模型或展开实体内部表示。</summary>
        private static void ReadChildCounts(EquipmentLevelSelection selection)
        {
            var tree = new EquipmentLevelTree();
            var counted = new HashSet<ulong>();
            foreach (var entry in selection.Equipment)
            {
                try
                {
                    var snapshot = tree.Capture(entry.ElementId);
                    int count = 0;
                    foreach (var node in snapshot.Nodes.Values)
                    {
                        if (!node.RequiresAppearance) continue;
                        count++;
                        counted.Add(node.Id);
                    }
                    selection.EquipmentChildCounts.Add(entry.ElementId, count);
                }
                catch (Exception ex)
                {
                    // 必须完整读出每台设备，不能把已读部分显示为整个选择的完整数量。
                    throw new InvalidOperationException("设备 " + entry.ElementId +
                        " 的子构件数量读取失败，请重新选择或检查设备：" + ex.Message, ex);
                }
            }
            selection.ChildElementCount = counted.Count;
        }

        internal static void Validate(EquipmentLevelDocument document, EquipmentLevelSelection selection)
        {
            if (document == null || selection == null || selection.Equipment.Count == 0)
                throw new InvalidOperationException("请先读取选中的设备。");
            ValidateDocument(document);
            var current = EquipmentLevelReader.ActiveModel();
            if (!ReferenceEquals(selection.Model, current))
                throw new InvalidOperationException("活动文档或模型已切换，请刷新图层并重新读取设备。");
            foreach (var entry in selection.Equipment)
            {
                ulong id = entry.ElementId;
                var element = current.FindElementById(new ElementId(ref id));
                if (element == null || !element.IsValid)
                    throw new InvalidOperationException("设备 " + id + " 已不存在，请重新读取选择。");
                var verdict = EquipmentLevelReader.Classify(element.DgnModelRef, id);
                if (verdict.Verdict != EquipmentLevelVerdict.Equipment)
                    throw new InvalidOperationException("设备 " + id + " 已不能处理：" + verdict.Reason);
            }
        }

        internal static void ValidateDocument(EquipmentLevelDocument document)
        {
            var current = EquipmentLevelReader.ActiveModel();
            if (document == null || !ReferenceEquals(document.Model, current) ||
                current.GetDgnFile() == null || document.FileName != current.GetDgnFile().GetFileName())
                throw new InvalidOperationException("活动文档或模型已切换，已停止设备修改。");
        }
    }

    internal sealed class EquipmentLevelDocument
    {
        internal DgnModel Model;
        internal string FileName, ModelName;
        internal uint ActiveLevelId;
        internal List<EquipmentLevelChoice> Levels = new List<EquipmentLevelChoice>();
    }

    internal sealed class EquipmentLevelSelection
    {
        internal DgnModel Model;
        internal readonly List<EquipmentLevelEntry> Equipment = new List<EquipmentLevelEntry>();
        internal readonly List<EquipmentLevelEntry> Rejected = new List<EquipmentLevelEntry>();
        internal int ChildElementCount;
        internal readonly Dictionary<ulong, int> EquipmentChildCounts = new Dictionary<ulong, int>();
    }
}
