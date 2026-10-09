using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 执行对齐（开发指南 §27 的 Apply、§28 的 Undo、§29 的错误恢复）。
    /// <para>
    /// 关键约定：
    /// </para>
    /// <list type="bullet">
    /// <item><description>**复核优先**：每一级修改接口调用之后都用独立几何通道复核，
    /// 复核不过就回退并降级到下一级；三级都不过就记为失败。</description></item>
    /// <item><description>**失败即停**（指南 §29）：任何一根管道移动失败，立即停止后续修改，
    /// 不留下"改了一半"的模型。</description></item>
    /// <item><description>**一次 Apply = 一次 Undo**（指南 §28）：整批操作包在一个 OpenPlant 撤销组里。</description></item>
    /// <item><description>**可回滚**：开始前记下 DGN 事务位置，出现异常时回退到该位置。</description></item>
    /// </list>
    /// </summary>
    internal sealed class PipeMoveService
    {
        private readonly IOpenPlantPipeAdapter _adapter;
        private readonly IPipeGeometryVerifier _verifier;
        private readonly PipeAlignOptions _options;
        private readonly IUnitService _units;
        private readonly PipeAlignLog _log;

        internal PipeMoveService(IOpenPlantPipeAdapter adapter, IPipeGeometryVerifier verifier,
            IUnitService units, PipeAlignOptions options, PipeAlignLog log)
        {
            if (adapter == null) throw new ArgumentNullException("adapter");
            _adapter = adapter;
            _verifier = verifier;
            _units = units ?? UnitService.Unavailable();
            _options = options ?? new PipeAlignOptions();
            _log = log;
        }

        /// <summary>按计划执行。返回的结果里逐根记录了成功 / 跳过 / 失败与所用的层级。</summary>
        internal AlignmentResult Apply(AlignmentPlan plan)
        {
            if (plan == null) throw new ArgumentNullException("plan");

            AlignmentResult result = new AlignmentResult(plan);
            if (!_units.IsAvailable)
            {
                result.FailureMessage = "取不到模型单位换算系数（UorPerMeter），未执行任何修改。";
                return result;
            }

            bool undoGroupOpen = false;
            bool haveTransactionMark = false;
            TransactionPosition mark = default(TransactionPosition);

            try
            {
                // 所有拒绝条件先检查，尤其直管最小安装长度，不能等水平组已改完才发现。
                foreach (AlignmentPlanItem pending in plan.Items)
                {
                    if (pending.Status != PlanItemStatus.Ready) continue;
                    string refusal;
                    bool movable = pending.IsStretch
                        ? _adapter.CanSetPipeAxis(pending.Pipe, pending.TargetAxis, _units, out refusal)
                        : _adapter.CanMove(pending.Pipe, _units, out refusal);
                    if (pending.IsRigidAdjustment && (pending.Pipe.MoveProbe == null || !pending.Pipe.MoveProbe.TransformUsable
                        || pending.Pipe.MoveProbe.ApiUnitsPerMillimeter <= 0))
                        throw new InvalidOperationException("乙字弯弯头没有可用的平移接口。");
                    if (!movable) throw new InvalidOperationException("批量预检查失败：" + pending.Pipe.DisplayName + "：" + refusal);
                }
                try
                {
                    // 全部修改使用同一套事务边界，失败尝试不能污染用户的撤销历史。
                    mark = PipeUndoScope.Begin();
                    undoGroupOpen = true;
                    haveTransactionMark = true;
                    if (_log != null) _log.Detail("撤销组已开始：IsActive=" + TransactionManager.IsActive
                        + "，HasEntries=" + TransactionManager.HasEntries);
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException("无法记录事务位置，未执行修改。", ex);
                }

                _adapter.DeferConnectionUpdates = true;

                for (int index = 0; index < plan.Items.Count; index++)
                {
                    AlignmentPlanItem item = plan.Items[index];
                    AlignmentItemResult itemResult = ExecuteItem(item);
                    result.Add(itemResult);

                    // 指南 §29：修改失败必须停止后续修改。
                    if (itemResult.Outcome != MoveOutcome.Failed) continue;

                    result.StoppedEarly = true;
                    result.FailureMessage = itemResult.Message;
                    if (_log != null)
                        _log.Error("移动失败，已停止后续修改：" + itemResult.Message);

                    // 剩下的管道**必须**也进结果列表：否则计数对不上，
                    // 用户会以为它们被处理过（或以为它们不存在）。
                    for (int rest = index + 1; rest < plan.Items.Count; rest++)
                    {
                        AlignmentPlanItem pending = plan.Items[rest];
                        result.Add(new AlignmentItemResult
                        {
                            ElementId = pending.Pipe == null ? 0UL : pending.Pipe.ElementId,
                            PipeName = pending.Pipe == null ? "?" : pending.Pipe.DisplayName,
                            Mode = pending.Mode,
                            DeltaZmm = pending.DeltaZmm,
                            Outcome = MoveOutcome.Skipped,
                            Message = "前一根管道移动失败，已停止后续修改，未处理该管道。"
                        });
                    }
                    throw new InvalidOperationException(itemResult.Message);
                }

                var changedPipes = new List<PipeInfo>();
                foreach (AlignmentPlanItem item in plan.Items)
                    if (item.Status == PlanItemStatus.Ready) changedPipes.Add(item.Pipe);
                if (changedPipes.Count > 0) _adapter.UpdateBatchConnections(changedPipes);
                // 整组全部移动之后再核对连接，不能在组内第一员移动时重判整组。
                foreach (AlignmentPlanItem item in plan.Items)
                {
                    if (item.Status != PlanItemStatus.Ready) continue;
                    PipeMoveVerification final = _verifier.Verify(item.Pipe);
                    if (final == null || !final.MatchesTarget(item,
                        Math.Max(_options.AlignmentToleranceMm * 10.0, 0.1)) || !final.MatchesConnections(item.Pipe))
                        throw new InvalidOperationException("移动后连接关系变化或无法复核，整批回退：" + item.Pipe.DisplayName);
                }
                foreach (PipeInfo fixedPipe in plan.FixedPipes)
                {
                    PipeMoveVerification final = _verifier.Verify(fixedPipe);
                    if (final == null || !final.MatchesFixed(fixedPipe, _options.RouteEndpointToleranceMm))
                        throw new InvalidOperationException("固定侧构件位置或连接变化，整批回退：" + fixedPipe.DisplayName);
                }
                PipeUndoScope.End();
                undoGroupOpen = false;
                if (_log != null) _log.Detail("撤销组已结束：IsActive=" + TransactionManager.IsActive
                    + "，HasEntries=" + TransactionManager.HasEntries);
            }
            catch (Exception ex)
            {
                result.FailureMessage = ex.Message;
                result.StoppedEarly = true;
                if (_log != null) _log.Error("执行过程中出现异常：" + ex.Message);

                if (undoGroupOpen)
                {
                    undoGroupOpen = false;
                    try { PipeUndoScope.End(); }
                    catch (Exception closeError) { result.FailureMessage += "；撤销组结束失败：" + closeError.Message; }
                }

                if (haveTransactionMark)
                {
                    try
                    {
                        PipeUndoScope.Cancel(mark);
                        result.RolledBack = true;
                        foreach (AlignmentItemResult moved in result.Items)
                        {
                            if (moved.Outcome != MoveOutcome.Moved) continue;
                            moved.Outcome = MoveOutcome.Failed;
                            moved.Message = "整批操作失败，已随事务回退。";
                        }
                        if (_log != null) _log.Warn("已回退到操作前的事务位置。");
                    }
                    catch (Exception rollbackError)
                    {
                        result.FailureMessage += "；事务回退失败：" + rollbackError.Message + "，请立即检查模型。";
                        if (_log != null) _log.Error("事务回退失败：" + rollbackError.Message);
                    }
                }
            }
            finally
            {
                _adapter.DeferConnectionUpdates = false;
                if (undoGroupOpen)
                {
                    try { PipeUndoScope.End(); }
                    catch (Exception ex)
                    {
                        result.FailureMessage = (result.FailureMessage ?? "") + "；撤销组结束失败：" + ex.Message;
                        if (_log != null) _log.Error(result.FailureMessage);
                    }
                }
            }

            return result;
        }

        private AlignmentItemResult ExecuteItem(AlignmentPlanItem item)
        {
            AlignmentItemResult itemResult = new AlignmentItemResult
            {
                ElementId = item.Pipe == null ? 0UL : item.Pipe.ElementId,
                PipeName = item.Pipe == null ? "?" : item.Pipe.DisplayName,
                Mode = item.Mode,
                DeltaZmm = item.DeltaZmm,
                OriginalCenterElevationMm = item.Pipe == null || item.Pipe.Axis == null
                    ? 0.0
                    : item.Pipe.Axis.CenterElevationMm,
                TargetCenterElevationMm = item.Pipe == null || item.Pipe.Axis == null
                    ? 0.0
                    : item.TargetAxis.CenterElevationMm
            };

            if (item.Status == PlanItemStatus.Skipped)
            {
                itemResult.Outcome = MoveOutcome.Skipped;
                itemResult.Message = item.SkipReason;
                return itemResult;
            }

            // 指南 T05：本来就对齐，不移动。
            if (item.Status == PlanItemStatus.AlreadyAligned)
            {
                itemResult.Outcome = MoveOutcome.AlreadyAligned;
                itemResult.AppliedLevel = "未修改";
                itemResult.Message = "已经对齐，无需移动。";
                return itemResult;
            }

            string reason;
            if (!_adapter.CanMove(item.Pipe, _units, out reason))
            {
                // 这是**执行前的检查**，什么都没改，所以按"跳过"处理而不是"失败" ——
                // 不能因为一根管道不可写就把整批操作中止掉（指南 §29 的"停止后续修改"
                // 针对的是"修改已经失败"，不是"事前就不该改")。
                itemResult.Outcome = MoveOutcome.Skipped;
                itemResult.Message = reason;
                if (_log != null) _log.Warn(itemResult.PipeName + "：" + reason);
                return itemResult;
            }

            double tolerance = Math.Max(_options.AlignmentToleranceMm * 10.0, 0.1);
            if (item.IsStretch)
            {
                PipeMoveAttempt stretch = _adapter.SetPipeAxis(item.Pipe, item.TargetAxis, _units);
                PipeMoveVerification verification = stretch.Succeeded ? _verifier.Verify(item.Pipe) : null;
                itemResult.Outcome = verification != null && verification.MatchesTarget(item, tolerance)
                    ? MoveOutcome.Moved : MoveOutcome.Failed;
                itemResult.AppliedLevel = stretch.Level;
                itemResult.Message = itemResult.Outcome == MoveOutcome.Failed
                    ? "直管伸缩未通过端点/固定端/EC 长度复核：" + (stretch.FailureReason ?? stretch.DescribeTraces())
                    : string.Format(CultureInfo.InvariantCulture, "直管长度 {0:F2} → {1:F2} mm，另一端固定。",
                        item.Pipe.Axis.LengthMm, item.TargetAxis.LengthMm);
                return itemResult;
            }
            if (item.IsRigidAdjustment)
            {
                var attempt = _adapter.SetRigidAxis(item.Pipe, item.TargetAxis, _units);
                var verification = attempt.Succeeded ? _verifier.Verify(item.Pipe) : null;
                itemResult.Outcome = verification != null && verification.MatchesTarget(item, tolerance)
                    ? MoveOutcome.Moved : MoveOutcome.Failed;
                itemResult.AppliedLevel = attempt.Level;
                itemResult.Message = itemResult.Outcome == MoveOutcome.Failed
                    ? "乙字弯弯头平移复核失败：" + attempt.FailureReason : "乙字弯弯头保持角度平移。";
                return itemResult;
            }
            List<string> traces = new List<string>();
            PipeMoveVerification lastVerification = null;

            foreach (PipeMoveLevel level in LevelsFor(item.Pipe))
            {
                TransactionPosition attemptMark = TransactionManager.CurrentTransactionPosition;
                PipeMoveAttempt attempt = _adapter.MovePipe(item.Pipe, item.DeltaZmm, level, _units);
                traces.Add(PipeMoveLevels.Code(level) + "：" + attempt.Describe());
                if (!string.IsNullOrEmpty(attempt.DescribeTraces()))
                    traces.Add(PipeMoveLevels.Code(level) + " 过程：" + attempt.DescribeTraces());

                if (!attempt.Succeeded)
                {
                    PipeUndoScope.Cancel(attemptMark);
                    continue;
                }

                PipeMoveVerification verification = (_verifier != null && _verifier.IsAvailable)
                    ? _verifier.Verify(item.Pipe)
                    : null;
                lastVerification = verification;

                string verificationText = verification == null
                    ? "复核不可用（取不到活动模型）"
                    : verification.Describe(item.Pipe.EcTranslationZRaw);

                if (verification != null && verification.MatchesTarget(item, tolerance))
                {
                    itemResult.Outcome = MoveOutcome.Moved;
                    itemResult.AppliedLevel = attempt.Level;
                    itemResult.Message = attempt.GraphicsOnly
                        ? "已按图形变换移动；⚠️ OpenPlant 数据可能仍停在旧标高，请在 OPM 中核对。"
                        : null;
                    if (_log != null)
                    {
                        _log.Detail(string.Format(CultureInfo.InvariantCulture,
                            "{0} 移动成功：{1}；{2}", itemResult.PipeName, attempt.Level, verificationText));
                    }
                    return itemResult;
                }

                // 复核不过：把这一级的影响退回去，再试下一级。
                traces.Add(PipeMoveLevels.Code(level) + " 复核未通过：" + verificationText);

                PipeUndoScope.Cancel(attemptMark);
                traces.Add(PipeMoveLevels.Code(level) + " 已按事务位置回退。");
            }

            itemResult.Outcome = MoveOutcome.Failed;
            itemResult.Message = BuildFailureMessage(item.Pipe, traces, lastVerification);
            if (_log != null)
            {
                _log.Error(itemResult.Message);
                _log.Detail("逐级尝试记录：" + string.Join(" | ", traces));
            }
            return itemResult;
        }

        /// <summary>
        /// 该管道可用的层级顺序。Level 3 只在用户明确打开配置项时才进候选，
        /// 因为指南 §19 明确禁止把"只改图形"当作正式实现。
        /// <para>
        /// Level 2b（EC 直写）排在 Level 2 之后：实测 Level 1 / 2 只改内存副本，
        /// 数据模型里始终是旧值。它**必须**是独立一级 —— 与 Level 2 合成一条链的话，
        /// 若 Level 2 其实写成功了，直写会把位移叠加两次。
        /// </para>
        /// </summary>
        private IEnumerable<PipeMoveLevel> LevelsFor(PipeInfo pipe)
        {
            PipeMoveProbe probe = pipe.MoveProbe;
            if (probe != null && probe.LinearPointsUsable
                && PipeConnectionClassifier.Classify(pipe.ClassName) == PipeConnectionKind.Pipe)
                yield return PipeMoveLevel.ObjectLinearPoints;
            if (probe != null && probe.TransformUsable)
                yield return PipeMoveLevel.ObjectTransform;
            if (probe != null && probe.ApiUnitsPerMillimeter > 0.0 && pipe.EcTranslationZRaw.HasValue)
                yield return PipeMoveLevel.ObjectEcTransform;
            if (_options.AllowGraphicsTransformFallback)
                yield return PipeMoveLevel.GraphicsTransform;
        }

        private static string BuildFailureMessage(PipeInfo pipe, IList<string> traces,
            PipeMoveVerification verification)
        {
            string probeDetail = pipe.MoveProbe == null ? null : pipe.MoveProbe.Detail;
            string name = pipe.DisplayName;

            if (verification == null)
                return name + "：移动尝试未成功，未通过位置复核。逐级记录：" + string.Join(" | ", traces);

            if (pipe.MoveProbe != null && !pipe.MoveProbe.AnyUsable)
            {
                return string.Format(CultureInfo.InvariantCulture,
                    "{0}：OpenPlant 对象接口不可用，未移动。{1}"
                    + "可在配置文件里打开 AllowGraphicsTransformFallback 改用图形变换，"
                    + "但那会让 OpenPlant 数据与图形不一致，需自行承担风险。",
                    name, string.IsNullOrEmpty(probeDetail) ? "" : probeDetail + " ");
            }

            // 用 EC 变换读数把失败原因**定位到具体环节**，这样下一次就能直接改对地方，
            // 而不是拿到一句"复核未通过"再猜一轮。
            string diagnosis;
            if (verification == null || !verification.EcTranslationZRaw.HasValue)
            {
                diagnosis = "读不到 EC 变换矩阵（TRANSFORMATION_MATRIX.M11），无法判断改动是否写进数据模型。";
            }
            else if (!verification.EcChanged)
            {
                diagnosis = "EC 变换矩阵没有变化 —— 说明**修改没有写进 OpenPlant 数据模型**。"
                    + "下一步要查的是「取对象的方式」（是否拿到了游离副本）与「提交 / 写回步骤」，"
                    + "而不是图形刷新。";
            }
            else
            {
                diagnosis = "EC 变换矩阵已经变化，但元素几何没变 —— 说明**数据写了、图形没重建**。"
                    + "下一步要补的是图形更新（AllowGraphicsUpdate / 重建）那一步。";
            }

            return string.Format(CultureInfo.InvariantCulture,
                "{0}：修改接口已调用但几何复核未通过，已回退，未移动。{1}"
                + "逐级记录：{2}",
                name, diagnosis, string.Join(" | ", traces));
        }
    }
}
