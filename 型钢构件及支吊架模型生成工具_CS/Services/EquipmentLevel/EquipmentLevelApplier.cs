using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 把设备的图形图元批量改到目标图层。
    /// <para>
    /// 只处理设备的图形图元，<b>不动设备元素本身</b>：设备身份、EC 数据、管口与连接关系
    /// 都不参与这次修改，因此不需要"打散 → 重新生成设备"。
    /// </para>
    /// <para>
    /// 写入方式按顺序尝试，任何一种都必须通过"候选图元全部落到目标图层"的校验才算成功：
    /// </para>
    /// <list type="number">
    /// <item>
    /// <b>COM Rewrite</b>（<c>Element.Level</c> + <c>Element.Rewrite()</c>）：
    /// OpenPlant 设备的图形是单元内部件，.NET 的 <c>ReplaceInModel</c> 一律返回 69645 拒绝，
    /// 而 COM 的 Rewrite 走的是另一条写入实现。
    /// </item>
    /// <item><b>逐个子元素替换</b>（.NET <c>ReplaceInModel</c>）：普通单元可用。</item>
    /// <item><b>整台单元替换</b>：所有图元先在内存改好，最后把整台设备单元写回一次。</item>
    /// </list>
    /// <para>
    /// 全部失败时整批回滚（<c>CancelToPosition</c>），不会留下"改了一半"的设备。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelApplier
    {
        private const int MaxProblemLines = 20;

        /// <summary>写入方式。</summary>
        private enum WriteMode
        {
            ComRewrite = 0,
            ReplaceEach = 1,
            ReplaceDevice = 2
        }

        /// <summary>对已判定为设备的元素批量改层。</summary>
        internal static EquipmentLevelReport Apply(DgnModel model, IList<ulong> ids,
            LevelId targetLevel, string targetLevelName)
        {
            if (model == null) throw new InvalidOperationException("没有活动模型。");
            var report = new EquipmentLevelReport { TargetLevelName = targetLevelName };
            var tree = new EquipmentLevelTree(model);

            // 1. 收集每台设备的候选图元：设置器接受不了的元素（Datum、Type66 这类控制元素）不算；
            //    有子元素的"容器单元"单独归类——实测它们本身不接受改层，但内部图元可以改。
            var plan = new Dictionary<ulong, DeviceTargets>();
            foreach (ulong rawId in ids)
            {
                ulong id = rawId;
                Element element = model.FindElementById(new ElementId(ref id));
                if (element == null || !element.IsValid)
                {
                    AddProblem(report.Problems, "元素 " + rawId + " 已不存在，跳过");
                    report.RejectedCount++;
                    continue;
                }
                var all = tree.Descendants(element);
                // 设备本体的几何是模型里的独立元素，不在依赖树里，只能按"完全落在设备范围内"补进来。
                var extras = tree.ElementsInsideRange(element);
                if (extras.Count > 0)
                {
                    var seen = new HashSet<ulong>();
                    foreach (var known in all) seen.Add(SafeId(known));
                    int added = 0;
                    foreach (var extra in extras)
                    {
                        ulong extraId = SafeId(extra);
                        if (extraId == 0 || seen.Contains(extraId)) continue;
                        seen.Add(extraId);
                        all.Add(extra);
                        added++;
                    }
                    EquipmentLevelLog.Write("范围补集：新增 " + added + " 个设备本体图元，图元总数 " + all.Count);
                }
                if (all.Count == 0)
                {
                    AddProblem(report.Problems, "设备 " + rawId + " 取不到图形图元（" + tree.Diagnose(element) + "），跳过");
                    report.RejectedCount++;
                    continue;
                }
                if (all.Count >= EquipmentLevelTree.MaxElements)
                {
                    AddProblem(report.Problems, "设备 " + rawId + " 的图元数超过 " +
                        EquipmentLevelTree.MaxElements + "，拒绝处理");
                    report.RejectedCount++;
                    continue;
                }

                var targets = new DeviceTargets();
                int rejected = 0;
                foreach (var candidate in all)
                {
                    ulong candidateId = SafeId(candidate);
                    if (candidateId == 0) { rejected++; continue; }
                    if (!CanSetLevel(candidate, targetLevel)) { rejected++; continue; }
                    if (tree.Children(candidate).Count > 0) targets.Containers.Add(candidateId);
                    else targets.Leaves.Add(candidateId);
                }
                if (targets.Leaves.Count == 0 && targets.Containers.Count == 0)
                {
                    AddProblem(report.Problems, "设备 " + rawId + " 的 " + all.Count +
                        " 个图元都不接受图层修改，跳过");
                    report.RejectedCount++;
                    continue;
                }
                plan[rawId] = targets;
                report.PlannedElementCount += targets.Leaves.Count + targets.Containers.Count;
                report.Details.Add("设备 " + rawId + "（" + SafeName(element) + "）：" + targets.Leaves.Count +
                    " 个图元、" + targets.Containers.Count + " 个容器单元" +
                    (rejected > 0 ? "，跳过 " + rejected + " 个非图形元素" : string.Empty));
                tree.Dump(element, "设备 " + rawId + "（" + SafeName(element) + "）图元树");
            }

            if (plan.Count == 0)
            {
                report.Summary = report.Problems.Count == 0
                    ? "选中的设备里没有可修改的图形图元。"
                    : "未修改：" + report.Problems[0];
                return report;
            }
            report.EquipmentCount = plan.Count;

            // 2. 依次尝试三种写入方式。
            var modes = new[]
            {
                new ModePlan { Mode = WriteMode.ComRewrite, Name = "COM Rewrite" },
                new ModePlan { Mode = WriteMode.ReplaceEach, Name = "逐个子元素替换" },
                new ModePlan { Mode = WriteMode.ReplaceDevice, Name = "整台单元替换" }
            };
            var failures = new List<string>();
            foreach (var modePlan in modes)
            {
                report.Problems.Clear();
                string failure;
                if (Run(model, tree, plan, targetLevel, targetLevelName, modePlan.Mode, report, out failure))
                {
                    report.Succeeded = true;
                    report.Method = modePlan.Name;
                    report.ContainersNotChanged = CountNotChangedContainers(tree, plan, targetLevel, model);
                    report.Summary = "设备图层修改完成：" + report.EquipmentCount + " 台设备、" +
                        report.ChangedElementCount + " 个图元 → 图层「" + targetLevelName + "」（" +
                        modePlan.Name + "）" +
                        (report.ContainersNotChanged > 0
                            ? "；" + report.ContainersNotChanged + " 个容器单元本身不接受改层（其内部图元已改）"
                            : string.Empty);
                    EquipmentLevelLog.Write("成功（" + modePlan.Name + "）：" + report.Summary);
                    return report;
                }
                failures.Add(modePlan.Name + " 失败：" + failure);
                EquipmentLevelLog.Write("方式「" + modePlan.Name + "」失败：" + failure);
            }

            report.Succeeded = false;
            report.Method = string.Empty;
            report.ChangedElementCount = 0;
            report.Failure = string.Join("\n", failures.ToArray());
            report.Summary = "设备图层修改失败，模型已回滚。原因见日志：" + EquipmentLevelLog.FilePath;
            return report;
        }

        private struct ModePlan
        {
            internal WriteMode Mode;
            internal string Name;
        }

        /// <summary>尝试一种写入方式：一个事务内完成，校验通过才提交，否则回滚。</summary>
        private static bool Run(DgnModel model, EquipmentLevelTree tree, Dictionary<ulong, DeviceTargets> plan,
            LevelId targetLevel, string targetLevelName, WriteMode mode, EquipmentLevelReport report,
            out string failure)
        {
            failure = null;
            TransactionPosition mark;
            try
            {
                mark = BeginEdit();
            }
            catch (Exception ex)
            {
                failure = ex.Message;
                return false;
            }

            try
            {
                int changed = 0;
                var problems = new List<string>();
                object comLevel = mode == WriteMode.ComRewrite ? ResolveComLevel(targetLevelName, problems) : null;
                foreach (var pair in plan)
                {
                    ulong deviceId = pair.Key;
                    Element device = model.FindElementById(new ElementId(ref deviceId));
                    if (device == null || !device.IsValid)
                    {
                        AddProblem(problems, "设备 " + pair.Key + " 写入前消失了");
                        continue;
                    }
                    switch (mode)
                    {
                        case WriteMode.ComRewrite:
                            changed += RunComPasses(tree, device, AllTargets(pair.Value), targetLevel, comLevel, problems);
                            break;

                        case WriteMode.ReplaceEach:
                            {
                                var map = MapById(tree, device);
                                foreach (ulong id in AllTargets(pair.Value))
                                {
                                    if (ReplaceOne(model, map, id, targetLevel, problems)) changed++;
                                }
                            }
                            break;

                        default:
                            {
                                var map = MapById(tree, device);
                                foreach (ulong id in AllTargets(pair.Value))
                                {
                                    Element element;
                                    if (!map.TryGetValue(id, out element)) { AddProblem(problems, "图元 " + id + " 找不到"); continue; }
                                    if (SetLevelInMemory(element, targetLevel, problems)) changed++;
                                }
                                StatusInt status = device.ReplaceInModel(device);
                                if (status != StatusInt.Success)
                                    AddProblem(problems, "整台设备 " + pair.Key + " 写回失败：" + status);
                            }
                            break;
                    }
                }

                string verifyFailure;
                if (!Verify(tree, plan, targetLevel, model, out verifyFailure))
                {
                    failure = string.IsNullOrEmpty(verifyFailure) ? "写入后校验失败" : verifyFailure;
                    Restore(mark, problems, failure);
                    AppendProblems(report, problems);
                    return false;
                }

                Commit();
                report.ChangedElementCount = CountOnTarget(tree, plan, targetLevel, model);
                return true;
            }
            catch (Exception ex)
            {
                failure = ex.Message;
                try
                {
                    if (TransactionManager.CancelToPosition(mark, false) != StatusInt.Success)
                        failure += "；回滚也失败，请用撤销恢复模型";
                }
                catch (Exception rollbackError)
                {
                    failure += "；回滚异常：" + rollbackError.Message;
                }
                return false;
            }
        }

        /// <summary>
        /// COM 通道的迭代收敛：一次写回可能被父单元的重写覆盖回去，
        /// 因此反复只改"还没落到目标图层"的图元，直到没有新的变化为止。
        /// <para>实测：第一轮 97 个里 60 个生效、37 个被父单元写回带回；靠迭代把它们补齐。</para>
        /// </summary>
        private static int RunComPasses(EquipmentLevelTree tree, Element device, List<ulong> candidates,
            LevelId targetLevel, object comLevel, List<string> problems)
        {
            int changed = 0;
            int previous = int.MaxValue;
            for (int pass = 1; pass <= 4; pass++)
            {
                var map = MapById(tree, device);
                var pending = new List<ulong>();
                foreach (ulong id in candidates)
                {
                    Element element;
                    if (!map.TryGetValue(id, out element)) continue;
                    if ((uint)element.LevelId == (uint)targetLevel) continue;
                    pending.Add(id);
                }
                if (pending.Count == 0)
                {
                    EquipmentLevelLog.Write("COM 第 " + pass + " 轮：已全部落到目标图层");
                    break;
                }
                if (pending.Count >= previous)
                {
                    EquipmentLevelLog.Write("COM 第 " + pass + " 轮：没有新的进展（剩 " + pending.Count + " 个），停止");
                    var map2 = MapById(tree, device);
                    int logged = 0;
                    foreach (ulong id in pending)
                    {
                        if (logged++ >= 10) break;
                        Element stuck;
                        EquipmentLevelLog.Write("  仍改不动：" +
                            (map2.TryGetValue(id, out stuck) ? Describe(stuck) : ("图元 " + id)));
                    }
                    break;
                }
                previous = pending.Count;
                int ok = 0;
                foreach (ulong id in pending)
                {
                    if (ComRewrite(id, comLevel, problems)) ok++;
                }
                changed += ok;
                EquipmentLevelLog.Write("COM 第 " + pass + " 轮：本轮写回 " + ok + " 个，开始前待改 " +
                    pending.Count + " 个");
            }
            return changed;
        }

        /// <summary>设置器能不能接受这个图元（控制元素如 Datum、Type66 不接受，直接排除）。</summary>
        private static bool CanSetLevel(Element element, LevelId targetLevel)
        {
            try
            {
                using (var setter = new ElementPropertiesSetter())
                {
                    setter.SetLevel(targetLevel);
                    return setter.Apply(element);
                }
            }
            catch
            {
                return false;
            }
        }

        private static bool SetLevelInMemory(Element element, LevelId targetLevel, List<string> problems)
        {
            try
            {
                using (var setter = new ElementPropertiesSetter())
                {
                    setter.SetLevel(targetLevel);
                    if (setter.Apply(element)) return true;
                }
                AddProblem(problems, "设置图层失败：" + Describe(element));
            }
            catch (Exception ex)
            {
                AddProblem(problems, "设置图层异常：" + ex.Message);
            }
            return false;
        }

        private static bool ReplaceOne(DgnModel model, Dictionary<ulong, Element> map, ulong id,
            LevelId targetLevel, List<string> problems)
        {
            Element element;
            if (!map.TryGetValue(id, out element))
            {
                AddProblem(problems, "图元 " + id + " 找不到");
                return false;
            }
            if (!SetLevelInMemory(element, targetLevel, problems)) return false;
            try
            {
                StatusInt status = element.ReplaceInModel(element);
                if (status == StatusInt.Success) return true;
                AddProblem(problems, "写回失败（" + status + "）：" + Describe(element));
            }
            catch (Exception ex)
            {
                AddProblem(problems, "写回异常：" + ex.Message);
            }
            return false;
        }

        /// <summary>
        /// COM 通道：<c>Element.Level = ...</c> 后 <c>Element.Rewrite()</c>。
        /// 这是单元内部件唯一被实测允许的写法（.NET 侧一律 69645）。
        /// </summary>
        private static bool ComRewrite(ulong id, object comLevel, List<string> problems)
        {
            if (comLevel == null)
            {
                AddProblem(problems, "COM 图层对象不可用，无法写回 " + id);
                return false;
            }
            try
            {
                var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
                var comElement = app.ActiveModelReference.GetElementByID64(checked((long)id));
                if (comElement == null)
                {
                    AddProblem(problems, "COM 取不到图元 " + id);
                    return false;
                }
                comElement.Level = (Bentley.Interop.MicroStationDGN.Level)comLevel;
                comElement.Rewrite();
                return true;
            }
            catch (Exception ex)
            {
                AddProblem(problems, "COM 写回失败（" + id + "）：" + ex.Message);
                return false;
            }
        }

        /// <summary>按名称取 COM 图层对象；找不到就直接判本次方式不可用。</summary>
        private static object ResolveComLevel(string levelName, List<string> problems)
        {
            try
            {
                var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
                var levels = app.ActiveModelReference.Levels;
                var level = levels.Find(levelName);
                if (level != null) return level;
                foreach (Bentley.Interop.MicroStationDGN.Level candidate in levels)
                {
                    if (candidate != null && string.Equals(candidate.Name, levelName, StringComparison.OrdinalIgnoreCase))
                        return candidate;
                }
                AddProblem(problems, "COM 找不到图层「" + levelName + "」");
            }
            catch (Exception ex)
            {
                AddProblem(problems, "读取 COM 图层失败：" + ex.Message);
            }
            return null;
        }

        /// <summary>后序映射：元素 ID → 元素。</summary>
        private static Dictionary<ulong, Element> MapById(EquipmentLevelTree tree, Element device)
        {
            var map = new Dictionary<ulong, Element>();
            foreach (var element in tree.Descendants(device))
            {
                ulong id = SafeId(element);
                if (id == 0 || map.ContainsKey(id)) continue;
                map[id] = element;
            }
            return map;
        }

        /// <summary>
        /// 校验：重新遍历一次设备。
        /// <para>
        /// <b>真实几何图元（叶子）必须全部落到目标图层</b>——这是成功的判据。
        /// 有子元素的"容器单元"实测在 COM/.NET 两条通道上都不接受改层，
        /// 因此它们只统计、不算失败（它们的内部图元已经改好了，外观已跟随）。
        /// </para>
        /// </summary>
        private static bool Verify(EquipmentLevelTree tree, Dictionary<ulong, DeviceTargets> plan,
            LevelId targetLevel, DgnModel model, out string failure)
        {
            failure = null;
            foreach (var pair in plan)
            {
                ulong deviceId = pair.Key;
                Element device = model.FindElementById(new ElementId(ref deviceId));
                if (device == null || !device.IsValid)
                {
                    failure = "设备 " + pair.Key + " 写入后找不到";
                    return false;
                }
                var map = MapById(tree, device);
                int mismatched = 0;
                int missing = 0;
                foreach (ulong id in pair.Value.Leaves)
                {
                    Element element;
                    if (!map.TryGetValue(id, out element)) { missing++; continue; }
                    if ((uint)element.LevelId != (uint)targetLevel) mismatched++;
                }
                if (missing > 0)
                {
                    failure = "设备 " + pair.Key + " 有 " + missing + " 个图元写入后找不到";
                    return false;
                }
                if (mismatched > 0)
                {
                    failure = "设备 " + pair.Key + " 仍有 " + mismatched + " 个几何图元没有落到目标图层";
                    return false;
                }
            }
            return true;
        }

        /// <summary>统计真正落在目标图层上的图元数（按最终状态算，不累加各轮写入次数）。</summary>
        private static int CountOnTarget(EquipmentLevelTree tree, Dictionary<ulong, DeviceTargets> plan,
            LevelId targetLevel, DgnModel model)
        {
            int count = 0;
            foreach (var pair in plan)
            {
                ulong deviceId = pair.Key;
                Element device = model.FindElementById(new ElementId(ref deviceId));
                if (device == null || !device.IsValid) continue;
                var map = MapById(tree, device);
                foreach (ulong id in AllTargets(pair.Value))
                {
                    Element element;
                    if (!map.TryGetValue(id, out element)) continue;
                    if ((uint)element.LevelId == (uint)targetLevel) count++;
                }
            }
            return count;
        }

        /// <summary>统计仍然没有被改层的容器单元数量（不算失败，只如实报告）。</summary>
        private static int CountNotChangedContainers(EquipmentLevelTree tree, Dictionary<ulong, DeviceTargets> plan,
            LevelId targetLevel, DgnModel model)
        {
            int count = 0;
            foreach (var pair in plan)
            {
                ulong deviceId = pair.Key;
                Element device = model.FindElementById(new ElementId(ref deviceId));
                if (device == null || !device.IsValid) continue;
                var map = MapById(tree, device);
                foreach (ulong id in pair.Value.Containers)
                {
                    Element element;
                    if (!map.TryGetValue(id, out element)) { count++; continue; }
                    if ((uint)element.LevelId != (uint)targetLevel) count++;
                }
            }
            return count;
        }

        /// <summary>一台设备的待改清单：叶子图元与容器单元分开。</summary>
        private sealed class DeviceTargets
        {
            internal readonly List<ulong> Leaves = new List<ulong>();
            internal readonly List<ulong> Containers = new List<ulong>();
        }

        /// <summary>叶子图元与容器单元合成一条写入序列（容器在后，避免它覆盖子元素）。</summary>
        private static List<ulong> AllTargets(DeviceTargets targets)
        {
            var all = new List<ulong>(targets.Leaves.Count + targets.Containers.Count);
            all.AddRange(targets.Leaves);
            all.AddRange(targets.Containers);
            return all;
        }

        /// <summary>开始一次可撤销的修改：结束上一个动作、记录撤销位置。</summary>
        private static TransactionPosition BeginEdit()
        {
            if (TransactionManager.IsUndoInProgress)
                throw new InvalidOperationException("正在撤销或重做，不能修改图层。");
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive)
                throw new InvalidOperationException("无法启用模型撤销记录。");
            TransactionManager.CloseCurrentTransaction(true);
            return TransactionManager.CurrentTransactionPosition;
        }

        /// <summary>把本次修改封成一个撤销步骤，保留宿主 Ctrl+Z / Redo 历史。</summary>
        private static void Commit()
        {
            TransactionManager.CloseCurrentTransaction(true);
        }

        /// <summary>校验失败时回滚，并把过程中的问题一起写进日志。</summary>
        private static void Restore(TransactionPosition mark, List<string> problems, string failure)
        {
            EquipmentLevelLog.Write("校验失败：" + failure);
            foreach (var problem in problems) EquipmentLevelLog.Write("  写入问题：" + problem);
            StatusInt status = TransactionManager.CancelToPosition(mark, false);
            if (status != StatusInt.Success)
                EquipmentLevelLog.Write("回滚失败：" + status + "，请用撤销恢复模型");
        }

        private static void AppendProblems(EquipmentLevelReport report, List<string> problems)
        {
            foreach (var problem in problems)
            {
                if (report.Problems.Count >= MaxProblemLines) return;
                report.Problems.Add(problem);
            }
        }

        private static void AddProblem(List<string> problems, string message)
        {
            EquipmentLevelLog.Write("问题：" + message);
            if (problems != null && problems.Count < MaxProblemLines) problems.Add(message);
        }

        private static ulong SafeId(Element element)
        {
            try { return element.ElementId; }
            catch { return 0; }
        }

        private static string Describe(Element element)
        {
            try { return element.TypeName + " " + element.ElementId; }
            catch { return "图元"; }
        }

        private static string SafeName(Element element)
        {
            try
            {
                var cell = element as CellHeaderElement;
                if (cell != null && !string.IsNullOrWhiteSpace(cell.CellName)) return cell.CellName;
                string description = element.Description;
                return string.IsNullOrWhiteSpace(description) ? element.TypeName : description;
            }
            catch
            {
                return "未命名";
            }
        }
    }
}
