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
    /// 只处理设备的图形子元素，<b>不动设备元素本身</b>：设备身份、EC 数据、管口与连接关系
    /// 都不参与这次修改，因此不需要"打散 → 重新生成设备"这一步。
    /// </para>
    /// <para>
    /// 写入分两种方式，按顺序尝试，都要通过"图元数不变 + 每个图元都在目标图层"的校验才算成功：
    /// </para>
    /// <list type="number">
    /// <item><b>逐个子元素替换</b>：每个图元改完属性后自己写回，保留单元身份；</item>
    /// <item><b>整台单元替换</b>：所有图元先在内存里改好，最后把整台设备单元写回一次。</item>
    /// </list>
    /// <para>
    /// 两种都失败时整批回滚（<c>CancelToPosition</c>），模型恢复到调用前的状态，
    /// 不会留下"改了一半"的设备。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelApplier
    {
        private const int MaxProblemLines = 20;

        /// <summary>
        /// 对已判定为设备的元素批量改层。
        /// </summary>
        /// <param name="model">活动模型。</param>
        /// <param name="ids">设备元素 ID（调用方已完成设备判定）。</param>
        /// <param name="targetLevel">目标图层。</param>
        /// <param name="targetLevelName">目标图层名（仅用于报告）。</param>
        internal static EquipmentLevelReport Apply(DgnModel model, IList<ulong> ids,
            LevelId targetLevel, string targetLevelName)
        {
            if (model == null) throw new InvalidOperationException("没有活动模型。");
            var report = new EquipmentLevelReport { TargetLevelName = targetLevelName };
            var tree = new EquipmentLevelTree(model);

            var counts = new Dictionary<ulong, int>();
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
                int count = tree.Count(element);
                if (count <= 0)
                {
                    string diagnosis = tree.Diagnose(element);
                    AddProblem(report.Problems, "设备 " + rawId + " 取不到图形图元（" + diagnosis + "），跳过");
                    report.RejectedCount++;
                    continue;
                }
                if (count >= EquipmentLevelTree.MaxElements)
                {
                    AddProblem(report.Problems, "设备 " + rawId + " 的图元数超过 " +
                        EquipmentLevelTree.MaxElements + "，拒绝处理");
                    report.RejectedCount++;
                    continue;
                }
                counts[rawId] = count;
                report.PlannedElementCount += count;
                report.Details.Add("设备 " + rawId + "（" + SafeName(element) + "）：" + count + " 个图元");
            }

            if (counts.Count == 0)
            {
                report.Summary = report.Problems.Count == 0
                    ? "选中的设备里没有可修改的图形图元。"
                    : "未修改：" + report.Problems[0];
                return report;
            }
            report.EquipmentCount = counts.Count;

            string failureA;
            if (Run(model, tree, counts, targetLevel, true, report, out failureA))
            {
                report.Succeeded = true;
                report.Method = "逐个子元素替换";
                report.Summary = BuildSummary(report, report.Method);
                EquipmentLevelLog.Write("成功（逐个子元素替换）：" + report.Summary);
                return report;
            }

            EquipmentLevelLog.Write("方式 A（逐个子元素替换）失败：" + failureA + "；改试整台单元替换");
            report.Problems.Clear();
            string failureB;
            if (Run(model, tree, counts, targetLevel, false, report, out failureB))
            {
                report.Succeeded = true;
                report.Method = "整台单元替换";
                report.Summary = BuildSummary(report, report.Method);
                EquipmentLevelLog.Write("成功（整台单元替换）：" + report.Summary);
                return report;
            }

            EquipmentLevelLog.Write("方式 B（整台单元替换）也失败：" + failureB);
            report.Succeeded = false;
            report.Method = string.Empty;
            report.ChangedElementCount = 0;
            report.Failure = "逐个子元素替换失败：" + failureA + "\n整台单元替换失败：" + failureB;
            report.Summary = "设备图层修改失败，模型已回滚。原因见日志：" + EquipmentLevelLog.FilePath;
            return report;
        }

        /// <summary>
        /// 尝试一种写入方式：一个事务内完成，校验通过才提交，否则回滚。
        /// </summary>
        private static bool Run(DgnModel model, EquipmentLevelTree tree, IDictionary<ulong, int> counts,
            LevelId targetLevel, bool replaceEachChild, EquipmentLevelReport report, out string failure)
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
                foreach (var pair in counts)
                {
                    ulong id = pair.Key;
                    Element device = model.FindElementById(new ElementId(ref id));
                    if (device == null || !device.IsValid)
                    {
                        AddProblem(problems, "设备 " + pair.Key + " 写入前消失了");
                        continue;
                    }
                    changed += ApplyToSubtree(model, tree, device, targetLevel, replaceEachChild, problems);
                    if (!replaceEachChild)
                    {
                        StatusInt status = device.ReplaceInModel(device);
                        if (status != StatusInt.Success)
                        {
                            AddProblem(problems, "整台设备 " + pair.Key + " 写回失败：" + status);
                        }
                    }
                }

                string verifyFailure;
                if (!Verify(model, tree, counts, targetLevel, out verifyFailure))
                {
                    failure = string.IsNullOrEmpty(verifyFailure) ? "写入后校验失败" : verifyFailure;
                    Restore(mark, problems, failure);
                    AppendProblems(report, problems);
                    return false;
                }

                Commit();
                report.ChangedElementCount = changed;
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
        /// 按"先子后父"的顺序改整棵子树：子元素先落地，父元素随后写回，
        /// 避免父元素替换后子元素句柄失效。
        /// <para>
        /// 每个图元在写入前都按 ID 重新取一次：一次替换会重写整个单元的描述记录，
        /// 事先收集到的其它子元素句柄可能已经失效，拿失效句柄去写回会把单元写坏。
        /// </para>
        /// </summary>
        private static int ApplyToSubtree(DgnModel model, EquipmentLevelTree tree, Element device,
            LevelId targetLevel, bool replaceEachChild, List<string> problems)
        {
            var postOrder = new List<Element>();
            tree.CollectPostOrder(device, postOrder, 0);
            int changed = 0;
            foreach (var original in postOrder)
            {
                Element element = original;
                if (replaceEachChild)
                {
                    Element fresh = FindByElementId(model, original);
                    if (fresh != null) element = fresh;
                }
                if (element == null || !element.IsValid)
                {
                    AddProblem(problems, "图元在写入过程中失效");
                    continue;
                }
                try
                {
                    bool applied;
                    using (var setter = new ElementPropertiesSetter())
                    {
                        setter.SetLevel(targetLevel);
                        applied = setter.Apply(element);
                    }
                    if (!applied)
                    {
                        AddProblem(problems, "设置图层失败：" + Describe(element));
                        continue;
                    }
                    if (replaceEachChild)
                    {
                        StatusInt status = element.ReplaceInModel(element);
                        if (status != StatusInt.Success)
                        {
                            AddProblem(problems, "写回失败（" + status + "）：" + Describe(element));
                            continue;
                        }
                    }
                    changed++;
                }
                catch (Exception ex)
                {
                    AddProblem(problems, "处理图元异常：" + ex.Message);
                }
            }
            return changed;
        }

        /// <summary>按元素 ID 重新取一次图元；取不到就返回 null，由调用方回退到原对象。</summary>
        private static Element FindByElementId(DgnModel model, Element element)
        {
            try
            {
                if (element == null) return null;
                ulong id = element.ElementId;
                if (id == 0) return null;
                ElementId elementId = new ElementId(ref id);
                Element found = model.FindElementById(elementId);
                return found != null && found.IsValid ? found : null;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 校验：每台设备的图元数必须与写入前一致（防止写回重复或丢失），
        /// 且每个图元都必须落在目标图层。
        /// </summary>
        private static bool Verify(DgnModel model, EquipmentLevelTree tree, IDictionary<ulong, int> counts,
            LevelId targetLevel, out string failure)
        {
            failure = null;
            foreach (var pair in counts)
            {
                ulong id = pair.Key;
                Element device = model.FindElementById(new ElementId(ref id));
                if (device == null || !device.IsValid)
                {
                    failure = "设备 " + pair.Key + " 写入后找不到";
                    return false;
                }
                var all = tree.Descendants(device);
                if (all.Count != pair.Value)
                {
                    failure = "设备 " + pair.Key + " 的图元数从 " + pair.Value + " 变成 " + all.Count +
                        "，结构被改动";
                    return false;
                }
                int mismatched = 0;
                foreach (var element in all)
                {
                    if ((uint)element.LevelId != (uint)targetLevel) mismatched++;
                }
                if (mismatched > 0)
                {
                    failure = "设备 " + pair.Key + " 仍有 " + mismatched + " 个图元没有落到目标图层";
                    return false;
                }
            }
            return true;
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

        private static string BuildSummary(EquipmentLevelReport report, string method)
        {
            return "设备图层修改完成：" + report.EquipmentCount + " 台设备、" + report.ChangedElementCount +
                " 个图元 → 图层「" + report.TargetLevelName + "」（" + method + "）";
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

        private static string Describe(Element element)
        {
            try
            {
                return element.TypeName + " " + element.ElementId;
            }
            catch
            {
                return "图元";
            }
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
