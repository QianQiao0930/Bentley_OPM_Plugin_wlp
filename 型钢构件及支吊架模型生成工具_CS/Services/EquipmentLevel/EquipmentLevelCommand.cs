using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// <c>STEELPROBE EQLEVEL</c> 的实现：把<b>选中设备</b>的图形图元批量改到<b>当前活动图层</b>。
    /// <para>
    /// 使用顺序：先把活动图层切到目标层 → 选中一台或多台设备 → 执行命令。
    /// 只处理普通单元且 EC 属性 <c>ElementType</c> 为 <c>Equipment</c> 的元素；
    /// 管道、管件、支吊架、共享单元、参数化单元与参考文件元素全部拒绝，并在日志里写明原因。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelCommand
    {
        /// <summary>执行命令；任何异常都转成状态栏提示，不抛给宿主。</summary>
        internal static void Run()
        {
            try
            {
                if (!LicenseService.IsActivated)
                {
                    SetStatus("请先激活软件，再修改设备图层。");
                    return;
                }
                Execute();
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("命令异常：" + ex);
                SetStatus("设备图层修改失败：" + ex.Message + "（详见 " + EquipmentLevelLog.FilePath + "）");
            }
        }

        private static void Execute()
        {
            DgnModel model = EquipmentLevelReader.ActiveModel();
            if (!SelectionSetManager.IsActive() || SelectionSetManager.NumSelected() == 0)
            {
                SetStatus("请先选中要修改图层的设备（只处理 ElementType = Equipment 的普通单元）。");
                return;
            }

            var selections = ReadSelection();
            if (selections.Count == 0)
            {
                SetStatus("选择集里的元素都已失效，请重新选择。");
                return;
            }

            // 1. 先判定，再把通过判定的设备交给写入层。
            var equipmentIds = new List<ulong>();
            int rejected = 0;
            foreach (var pair in selections)
            {
                EquipmentLevelEntry entry = EquipmentLevelReader.Classify(pair.Model, pair.Id);
                EquipmentLevelLog.Write("判定 " + pair.Id + "（" + entry.Name + "）：" + entry.Verdict +
                    (string.IsNullOrEmpty(entry.Reason) ? "" : " / " + entry.Reason));
                if (entry.Verdict == EquipmentLevelVerdict.Equipment) equipmentIds.Add(pair.Id);
                else rejected++;
            }

            if (equipmentIds.Count == 0)
            {
                SetStatus("选中的 " + rejected + " 个元素都不是设备（需要 ElementType = Equipment 的普通单元），未做修改。");
                return;
            }

            // 2. 目标图层 = 当前活动图层。
            LevelHandle target = ReadActiveLevel(model);

            // 3. 写入 + 校验 + 失败回滚。
            EquipmentLevelReport report = EquipmentLevelApplier.Apply(model, equipmentIds,
                target.LevelId, target.Name);
            report.RejectedCount += rejected;

            EquipmentLevelLog.Write("结论：" + report.Summary);
            foreach (var detail in report.Details) EquipmentLevelLog.Write("  " + detail);
            foreach (var problem in report.Problems) EquipmentLevelLog.Write("  " + problem);

            string suffix = rejected > 0 ? "；跳过 " + rejected + " 个非设备元素" : string.Empty;
            SetStatus(report.Succeeded ? report.Summary + suffix : report.Summary);
        }

        /// <summary>读取活动图层；读不到就明确报错，不猜一个默认层。</summary>
        private static LevelHandle ReadActiveLevel(DgnModel model)
        {
            var cache = model.GetDgnFile().GetLevelCache() as FileLevelCache;
            if (cache == null) throw new InvalidOperationException("无法读取图层表。");
            LevelId activeId = Settings.ActiveLevelId;
            LevelHandle active = null;
            foreach (LevelHandle handle in cache.GetHandles())
            {
                if (handle == null || (uint)handle.LevelId != (uint)activeId) continue;
                active = handle;
                break;
            }
            if (active == null || !active.IsValid)
                throw new InvalidOperationException("无法读取当前活动图层，请先在图层管理器中选一个活动图层。");
            if (active.ReadOnly) throw new InvalidOperationException("当前活动图层是只读的：" + active.Name);
            return active;
        }

        private struct Selection
        {
            internal DgnModelRef Model;
            internal ulong Id;
        }

        /// <summary>把选择集里的元素转成"模型引用 + ID"，不保留元素对象。</summary>
        private static List<Selection> ReadSelection()
        {
            var list = new List<Selection>();
            uint count = SelectionSetManager.NumSelected();
            for (uint i = 0; i < count; i++)
            {
                Element element = null;
                DgnModelRef modelRef = null;
                if (SelectionSetManager.GetElement(i, ref element, ref modelRef) != StatusInt.Success) continue;
                if (element == null) continue;
                list.Add(new Selection { Model = modelRef, Id = element.ElementId });
            }
            return list;
        }

        private static void SetStatus(string text)
        {
            try { MessageCenter.Instance.StatusMessage = text; }
            catch { /* 状态栏写不进去不影响结果。 */ }
        }
    }
}
