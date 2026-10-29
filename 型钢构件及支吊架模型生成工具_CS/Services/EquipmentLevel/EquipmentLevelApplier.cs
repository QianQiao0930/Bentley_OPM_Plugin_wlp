using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Bentley.DgnPlatformNET;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>
    /// 按实际包含关系制定计划，统一改层和颜色随层；重新读取同一棵树校验后才提交。
    /// 不打散、不重建，不把依赖元素或包围盒中的邻近对象当作设备内部件。
    /// </summary>
    internal static class EquipmentLevelApplier
    {
        private const int MaxPasses = 3;
        private const int MaxProblemLines = 20;
        internal static bool IsRunning { get; private set; }

        internal static EquipmentLevelReport Apply(DgnModel model, IList<ulong> ids,
            LevelId targetLevel, string targetLevelName)
        {
            return Apply(model, ids, new EquipmentAppearanceOptions { TargetLevelId = (uint)targetLevel,
                TargetLevelName = targetLevelName, ColorMode = EquipmentColorMode.ByLevel });
        }

        internal static EquipmentLevelReport Apply(DgnModel model, IList<ulong> ids,
            EquipmentAppearanceOptions options, Action<EquipmentLevelProgress> progress = null, Action validateContext = null)
        {
            if (IsRunning) return new EquipmentLevelReport { Summary = "已有设备修改任务正在运行，请等待完成。" };
            IsRunning = true;
            try { return ApplyCore(model, ids, options, new EquipmentLevelProgressReporter(progress, validateContext)); }
            finally { IsRunning = false; }
        }

        private static EquipmentLevelReport ApplyCore(DgnModel model, IList<ulong> ids,
            EquipmentAppearanceOptions options, EquipmentLevelProgressReporter progress)
        {
            string targetLevelName = options == null ? "" : options.TargetLevelName;
            var report = new EquipmentLevelReport { TargetLevelName = targetLevelName };
            var tree = new EquipmentLevelTree(progress.Scanned);
            var plan = new Dictionary<ulong, EquipmentLevelSnapshot>();
            var dump = new StringBuilder();
            Com.Level comLevel;
            int byLevelColor;
            string phase = "读取活动模型";
            // 计划阶段完全只读，任一设备读取不完整就不开始本批写入。
            try
            {
                progress.Step("检查文档与目标图层", 0, 0, force: true);
                if (options == null || string.IsNullOrWhiteSpace(options.TargetLevelName))
                    throw new InvalidOperationException("请先选择目标图层。");
                if (!Enum.IsDefined(typeof(EquipmentColorMode), options.ColorMode) || options.Rgb > 0xFFFFFF)
                    throw new InvalidOperationException("颜色设置无效。");
                if (model == null) throw new InvalidOperationException("没有活动模型。");
                var file = model.GetDgnFile();
                if (file == null) throw new InvalidOperationException("活动模型未提供 DGN 文件对象。");
                if (model.IsReadOnly || file.IsReadOnly)
                    throw new InvalidOperationException("活动模型或文件是只读的。");
                phase = "读取目标图层「" + targetLevelName + "」";
                var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
                if (app == null) throw new InvalidOperationException("OPM COM 应用对象不可用。");
                var active = app.ActiveModelReference;
                if (active == null) throw new InvalidOperationException("OPM COM 活动模型不可用。");
                var levels = active.Levels;
                if (levels == null) throw new InvalidOperationException("OPM COM 图层集合不可用。");
                comLevel = levels.Find(targetLevelName);
                if (comLevel == null || (uint)comLevel.ID != options.TargetLevelId)
                    throw new InvalidOperationException("COM 与活动模型的目标图层不一致。");
                if (comLevel.IsLocked) throw new InvalidOperationException("目标图层已锁定。");
                phase = "解析目标颜色";
                byLevelColor = options.ColorMode == EquipmentColorMode.ByLevel ? app.ByLevelColor() : 0;
                if (options.ColorMode == EquipmentColorMode.CustomRgb)
                {
                    int oleRgb = (int)(((options.Rgb >> 16) & 255) | (options.Rgb & 0x00FF00) | ((options.Rgb & 255) << 16));
                    byLevelColor = active.InternalColorFromRGBColor(oleRgb);
                    if ((active.InternalColorToRGBColor(byLevelColor) & 0xFFFFFF) != oleRgb)
                        throw new InvalidOperationException("宿主未能精确转换指定颜色。");
                }
                int equipmentIndex = 0;
                foreach (ulong id in ids)
                {
                    progress.Step("读取设备内部图元", equipmentIndex++, ids.Count, "设备 " + id, true);
                    phase = "读取设备 " + id + " 的 COM 内部图元";
                    if (plan.ContainsKey(id)) continue;
                    var root = EquipmentLevelTree.Find(id);
                    if (root.IsLocked) throw new InvalidOperationException("设备 " + id + " 已锁定。");
                    var snapshot = tree.Capture(id);
                    EquipmentLevelTree.LogModelLookup(snapshot);
                    if (!snapshot.Nodes.Values.Any(n => n.RequiresAppearance))
                        throw new InvalidOperationException("设备 " + id +
                            " 的 COM GetSubElements 未读到可修改的内部图形；未修改。请执行 STEELPROBE EQPROBE 查看结构。");
                    foreach (var node in snapshot.Nodes.Values)
                        if (node.RequiresAppearance && node.IsLocked)
                            throw new InvalidOperationException("设备 " + id + " 的图元 " + node.Id + " 已锁定。");
                    plan.Add(id, snapshot);
                    dump.Append(EquipmentLevelTree.Format(snapshot, "修改前"));
                }
                if (plan.Count == 0) throw new InvalidOperationException("没有可修改的设备。");
                // 重叠选择会使一台设备的根成为另一台的待改容器，直接拒绝歧义。
                foreach (var snapshot in plan.Values)
                    foreach (ulong rootId in plan.Keys)
                        if (snapshot.Nodes.ContainsKey(rootId))
                            throw new InvalidOperationException("选中的设备互相嵌套，请只选外层设备。");
                if (plan.Values.SelectMany(s => s.Nodes.Keys).GroupBy(id => id).Any(g => g.Count() > 1))
                    throw new InvalidOperationException("不同设备返回相同内部件，无法确认归属，未修改。");
                EquipmentLevelLog.WriteTree(dump.ToString());
            }
            catch (Exception ex)
            {
                dump.AppendLine("读取/计划失败，阶段：" + phase + "，未开始写入。" + Environment.NewLine + ex);
                EquipmentLevelLog.WriteTree(dump.ToString());
                report.Failure = phase + "：" + ex.Message;
                report.Summary = "未修改：" + report.Failure;
                EquipmentLevelLog.Write("计划异常，阶段：" + phase + Environment.NewLine + ex);
                EquipmentLevelLog.Write(report.Summary);
                return report;
            }

            int levelId = comLevel.ID;
            var all = plan.Values.SelectMany(s => s.Nodes.Values)
                .GroupBy(n => n.Id).Select(g => g.First()).ToList();
            var required = all.Where(n => n.RequiresAppearance).ToList();
            var owners = plan.Values.SelectMany(s => s.Nodes.Keys.Select(id => new { Id = id, Snapshot = s }))
                .ToDictionary(p => p.Id, p => p.Snapshot);
            var initiallyDifferent = new HashSet<ulong>(
                required.Where(n => !MatchesTarget(n, levelId, byLevelColor, options.ColorMode, n)).Select(n => n.Id));
            report.EquipmentCount = plan.Count;
            report.PlannedElementCount = required.Count;
            report.AlreadyOnTargetCount = required.Count - initiallyDifferent.Count;
            EquipmentLevelLog.Write("计划：设备 " + plan.Count + " 台，图形 " + required.Count +
                " 个，已符合 " + report.AlreadyOnTargetCount + " 个；目标层 ID=" + levelId +
                "，目标内部颜色=" + byLevelColor + "（" + options.ColorDescription + "）。");
            foreach (var snapshot in plan.Values)
                report.Details.Add("设备 " + snapshot.RootId + "：COM 内部件 " + snapshot.Nodes.Count +
                    " 个，必须校验的图形 " + snapshot.Nodes.Values.Count(n => n.RequiresAppearance) + " 个。");
            int sharedCount = required.Count(n => n.IsSharedInstance);
            if (sharedCount > 0)
                report.Details.Add("其中共享单元实例 " + sharedCount + " 个：使用实例图层/颜色覆盖；公共定义及其内部图元原始属性保持不变。");

            TransactionPosition mark = default(TransactionPosition);
            bool editStarted = false;
            try
            {
                mark = BeginEdit();
                editStarted = true;
                // 父容器先写，子图形后写，避免最后重写容器覆盖已改的子元素。
                int written = 0;
                foreach (var node in all.OrderBy(n => n.Depth))
                {
                    progress.Step("修改图层与颜色", written++, all.Count);
                    if (!node.IsGraphic || MatchesTarget(node, levelId, byLevelColor, options.ColorMode, node)) continue;
                    if (node.IsContainer)
                    {
                        if (!node.HasAppearance) continue;
                        try { Write(tree, owners[node.Id], node, comLevel, byLevelColor, options.ColorMode); }
                        catch (Exception ex) { AddProblem(report, "容器 " + node.Id + " 未改：" + ex.Message); }
                    }
                    else Write(tree, owners[node.Id], node, comLevel, byLevelColor, options.ColorMode);
                }

                Dictionary<ulong, EquipmentLevelNode> current = null;
                for (int pass = 1; pass <= MaxPasses; pass++)
                {
                    progress.Step("重新读取并校验 · 第 " + pass + " 轮", 0, 0, force: true);
                    // Capture 重新读取全部节点和属性，不用内存 setter 的结果作成功依据。
                    current = ReadAndVerifyStructure(tree, plan);
                    var pending = required.Where(n => !MatchesTarget(current[n.Id], levelId, byLevelColor, options.ColorMode, n)).ToList();
                    EquipmentLevelLog.Write("校验第 " + pass + " 轮：图形 " + required.Count +
                        " 个，图层或颜色未符合 " + pending.Count + " 个。");
                    if (pending.Count == 0) break;
                    if (pass == MaxPasses)
                    {
                        foreach (var node in pending.Take(10))
                            AddProblem(report, "未落地 id=" + node.Id + " 类型=" + node.Type +
                                " 层=" + current[node.Id].LevelId + " 颜色=" + current[node.Id].Color +
                                (node.IsSharedInstance ? " 覆盖层=" + current[node.Id].OverridesComponentLevel +
                                    " 覆盖色=" + current[node.Id].OverridesComponentColor : ""));
                        throw new InvalidOperationException("仍有 " + pending.Count + " 个图形未达到目标图层和所选颜色设置。");
                    }
                    int retried = 0;
                    foreach (var node in pending.OrderBy(n => n.Depth))
                    {
                        progress.Step("补写未符合的图形", retried++, pending.Count);
                        Write(tree, owners[node.Id], node, comLevel, byLevelColor, options.ColorMode);
                    }
                }

                int containersNotChanged = all.Count(n => n.IsGraphic && n.IsContainer &&
                    !MatchesTarget(current[n.Id], levelId, byLevelColor, options.ColorMode, n));
                progress.Step("提交修改", 0, 0, force: true);
                // 所有可能失败的读取与校验均在提交之前完成。
                EquipmentLevelLog.Write("事务提交开始：设备 " + plan.Count + " 台，图形 " + required.Count +
                    " 个，其中智能实体 " + required.Count(n => n.IsAtomicSolid) + " 个，共享实例 " + sharedCount + " 个。");
                TransactionManager.CloseCurrentTransaction(true);
                EquipmentLevelLog.Write("事务提交结束。");
                progress.SuspendContextValidation();
                report.Succeeded = true;
                report.Method = "COM 包含路径定位 + Rewrite";
                report.ChangedElementCount = initiallyDifferent.Count;
                report.VerifiedElementCount = required.Count;
                report.ContainersNotChanged = containersNotChanged;
                report.Summary = "设备图层与颜色修改完成：" + report.EquipmentCount + " 台，实际修改 " +
                    report.ChangedElementCount + " 个图形，校验 " + report.VerifiedElementCount +
                    " 个 →「" + targetLevelName + "」，" + options.ColorDescription +
                    (sharedCount > 0 ? "；含 " + sharedCount + " 个共享实例（实例覆盖，公共定义保留）" : "") +
                    (containersNotChanged > 0 ? "；" + containersNotChanged + " 个单元头属性未统一（内部图形已校验）" : "") + "。";
                EquipmentLevelLog.Write(report.Summary);
                progress.Step("处理完成", required.Count, required.Count, force: true);
                return report;
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("写入/校验异常：" + ex);
                progress.SuspendContextValidation();
                report.Failure = ex.Message;
                report.ChangedElementCount = 0;
                bool restored = false;
                string rollbackProblem = null;
                if (editStarted)
                {
                    progress.Step("失败，正在整批回滚", 0, 0, force: true);
                    try
                    {
                        StatusInt status = TransactionManager.CancelToPosition(mark, false);
                        restored = status == StatusInt.Success;
                        if (!restored) rollbackProblem = status.ToString();
                        if (restored)
                        {
                            var rolledBack = ReadAndVerifyStructure(tree, plan);
                            foreach (var original in all.Where(n => n.IsGraphic && n.HasAppearance))
                                if (!rolledBack[original.Id].Matches(original.LevelId, original.Color) ||
                                    (original.IsSharedInstance &&
                                        (rolledBack[original.Id].OverridesComponentLevel != original.OverridesComponentLevel ||
                                         rolledBack[original.Id].OverridesComponentColor != original.OverridesComponentColor)))
                                    throw new InvalidOperationException("回滚后图元 " + original.Id + " 的属性未恢复。");
                        }
                    }
                    catch (Exception rollbackError) { restored = false; rollbackProblem = rollbackError.Message; }
                }
                report.Summary = !editStarted ? "未修改：" + ex.Message :
                    restored ? "修改失败，已整批回滚：" + ex.Message :
                    "修改失败，回滚未完成，请立即用撤销恢复模型：" + ex.Message + "；" + rollbackProblem;
                EquipmentLevelLog.Write(report.Summary);
                return report;
            }
        }

        private static bool MatchesTarget(EquipmentLevelNode node, int levelId, int color, EquipmentColorMode mode, EquipmentLevelNode original)
        {
            return node.HasAppearance && node.LevelId == levelId &&
                node.Color == (mode == EquipmentColorMode.KeepOriginal ? original.Color : color) &&
                (!node.IsSharedInstance || (node.OverridesComponentLevel &&
                    node.OverridesComponentColor == (mode == EquipmentColorMode.KeepOriginal ? original.OverridesComponentColor : true)));
        }

        private static void Write(EquipmentLevelTree tree, EquipmentLevelSnapshot owner, EquipmentLevelNode original,
            Com.Level level, int byLevelColor, EquipmentColorMode mode)
        {
            ulong id = original.Id;
            // 从设备根沿原包含路径取得新组件，不能用模型级内部件查找返回的外层单元代写。
            try
            {
                var element = tree.Resolve(owner, original);
                if (element.IsLocked) throw new InvalidOperationException("元素已锁定。");
                int color = mode == EquipmentColorMode.KeepOriginal ? original.Color : byLevelColor;
                if (original.IsSharedInstance)
                {
                    var shared = element.AsSharedCellElement();
                    if (shared == null) throw new InvalidOperationException("共享实例接口不可用。");
                    if (shared.Name != original.SharedName) throw new InvalidOperationException("共享实例引用的定义已变化。");
                    shared.OverridesComponentLevel = true;
                    shared.OverridesComponentColor = mode == EquipmentColorMode.KeepOriginal ? original.OverridesComponentColor : true;
                    shared.Level = level;
                    shared.Color = color;
                    shared.Rewrite();
                }
                else if (element.IsSmartSolidElement)
                {
                    var solid = element.AsSmartSolidElement;
                    if (solid == null) throw new InvalidOperationException("SmartSolid 接口不可用。");
                    solid.Level = level;
                    solid.Color = color;
                    solid.Rewrite();
                }
                else
                {
                    element.Level = level;
                    element.Color = color;
                    element.Rewrite();
                }
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException("图元 " + id + " 写入失败：" + ex.Message, ex);
            }
        }

        private static Dictionary<ulong, EquipmentLevelNode> ReadAndVerifyStructure(EquipmentLevelTree tree,
            Dictionary<ulong, EquipmentLevelSnapshot> plan)
        {
            var map = new Dictionary<ulong, EquipmentLevelNode>();
            foreach (var before in plan.Values)
            {
                var after = tree.Capture(before.RootId);
                if (before.Nodes.Count != after.Nodes.Count)
                    throw new InvalidOperationException("设备 " + before.RootId + " 内部件数量变化，拒绝提交。");
                foreach (var original in before.Nodes.Values)
                {
                    EquipmentLevelNode node;
                    if (!after.Nodes.TryGetValue(original.Id, out node) ||
                        node.ParentId != original.ParentId || node.Type != original.Type ||
                        node.IsGraphic != original.IsGraphic || node.IsContainer != original.IsContainer ||
                        node.IsCell != original.IsCell ||
                        node.IsAtomicSolid != original.IsAtomicSolid ||
                        node.IsSharedInstance != original.IsSharedInstance || node.SharedName != original.SharedName)
                        throw new InvalidOperationException("设备 " + before.RootId + " 内部件 " + original.Id +
                            " 的身份或包含关系变化，拒绝提交。");
                    map[node.Id] = node;
                }
            }
            return map;
        }

        private static TransactionPosition BeginEdit()
        {
            if (TransactionManager.IsUndoInProgress)
                throw new InvalidOperationException("正在撤销或重做，不能修改设备。");
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销记录。");
            TransactionManager.CloseCurrentTransaction(true);
            return TransactionManager.CurrentTransactionPosition;
        }

        private static void AddProblem(EquipmentLevelReport report, string message)
        {
            EquipmentLevelLog.Write(message);
            if (report.Problems.Count < MaxProblemLines) report.Problems.Add(message);
        }
    }
}
