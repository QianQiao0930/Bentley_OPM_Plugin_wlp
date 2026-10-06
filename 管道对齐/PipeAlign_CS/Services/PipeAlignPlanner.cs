using System;
using System.Collections.Generic;
using System.Globalization;

namespace PipeAlign
{
    /// <summary>
    /// 对齐计划（开发指南 §16、§27 的第 1～9 步）。
    /// <para>
    /// 本类是**纯计算**：输入是已读取完成的 <see cref="PipeInfo"/> 快照，输出是
    /// 每根目标管的 ΔZ 或跳过原因。它不引用任何 Bentley 类型，因此可以在
    /// <c>Development/PipeAlignCheck</c> 里离线断言（对应指南 §38 的 T01～T20）。
    /// </para>
    /// <para>
    /// 拓扑校验要按 Safe Mode（指南 §22）迭代到不动点：一根目标管被跳过后，
    /// 原本"只与它相连"的另一根目标管就多出了一条固定连接，也必须跟着跳过。
    /// </para>
    /// </summary>
    internal static class PipeAlignPlanner
    {
        internal static AlignmentPlan BuildPlan(AlignmentRequest request)
        {
            if (request == null) throw new ArgumentNullException("request");

            PipeAlignOptions options = request.Options ?? new PipeAlignOptions();

            ValidationOutcome referenceCheck = PipeValidationService.ValidateReferencePipe(
                request.ReferencePipe, request.SurfaceMode, options);
            if (!referenceCheck.IsValid)
                throw new PipeAlignValidationException("基准管不可用：" + referenceCheck.Reason);

            double referenceElevation = ElevationCalculator.GetAlignmentElevation(
                request.ReferencePipe, request.Mode, request.SurfaceMode);

            AlignmentPlan plan = new AlignmentPlan(request.ReferencePipe, request.Mode,
                request.SurfaceMode, referenceElevation);

            if (request.TargetPipes == null || request.TargetPipes.Count == 0)
                throw new PipeAlignValidationException("尚未选择目标管。");

            if (request.TargetPipes.Count > options.MaxTargetPipes)
                throw new PipeAlignValidationException(string.Format(CultureInfo.InvariantCulture,
                    "一次最多处理 {0} 根目标管（当前 {1} 根）。请分批操作，或修改配置项 MaxTargetPipes。",
                    options.MaxTargetPipes, request.TargetPipes.Count));

            if (request.SeedInstanceIds != null)
            {
                BuildGroupItems(plan, request, options);
                EnrichConnectionNames(plan, request);
                ApplyTopologyFilter(plan, options.TopologyCheckMode, options.AlignmentToleranceMm);
                return plan;
            }

            List<string> seen = new List<string>();

            // ---- 第 1 遍：逐根做与拓扑无关的校验，并算出各自的对齐标高 ----
            foreach (PipeInfo target in request.TargetPipes)
            {
                if (target == null) continue;

                // 去重必须带上"是不是参考文件"，不能只用 ElementId：两个文件的 ID 空间各自编号，
                // 同号元素不是同一根管（见 PipeIdentity）。
                string key = PipeIdentity.Key(target);
                if (seen.Contains(key))
                    continue;
                seen.Add(key);

                if (PipeIdentity.SamePipe(target, request.ReferencePipe))
                {
                    AlignmentPlanItem selfItem = new AlignmentPlanItem(target, request.Mode, request.SurfaceMode);
                    selfItem.Status = PlanItemStatus.Skipped;
                    selfItem.SkipReason = "该管道就是基准管，未移动。";
                    plan.Add(selfItem);
                    continue;
                }

                AlignmentPlanItem item = new AlignmentPlanItem(target, request.Mode, request.SurfaceMode);
                ValidationOutcome check = PipeValidationService.ValidateTargetPipe(
                    target, request.Mode, request.SurfaceMode, options);
                if (!check.IsValid)
                {
                    item.Status = PlanItemStatus.Skipped;
                    item.SkipReason = check.Reason;
                    plan.Add(item);
                    continue;
                }

                double currentElevation = ElevationCalculator.GetAlignmentElevation(
                    target, request.Mode, request.SurfaceMode);
                item.OutsideDiameterMm = target.OutsideDiameterMm ?? 0.0;
                item.EffectiveDiameterMm = target.EffectiveDiameterMm(request.SurfaceMode);
                item.AddedByGroup = request.SeedInstanceIds != null
                    && !string.IsNullOrEmpty(target.InstanceId)
                    && !Contains(request.SeedInstanceIds, target.InstanceId);
                item.CurrentElevationMm = currentElevation;
                item.ReferenceElevationMm = referenceElevation;
                item.DeltaZmm = ElevationCalculator.ComputeDeltaZ(referenceElevation, currentElevation);
                plan.Add(item);
            }

            // ---- 第 1.5 遍：用已知管道给连接对象补上可读的名字 ----
            EnrichConnectionNames(plan, request);

            // ---- 第 2 遍：先标出"本来就对齐、不会移动"的管道 ----
            // ⚠️ 必须排在拓扑校验**之前**：拓扑校验用的"移动集合"只包含真正会动的管道
            // （AlignmentPlan.ReadyInstanceIds 只看 PlanItemStatus.Ready）。
            // 若把"已对齐"的管子也算进移动集合，与它相连的另一根目标管就会被误判为
            // "连接的对象也会一起移动"而放行 —— 但它其实不动，移动后接头会断。
            foreach (AlignmentPlanItem item in plan.Items)
            {
                if (item.Status != PlanItemStatus.Ready) continue;
                if (Math.Abs(item.DeltaZmm) <= options.AlignmentToleranceMm)
                    item.Status = PlanItemStatus.AlreadyAligned;
            }

            // ---- 第 3 遍：Safe Mode 拓扑校验，迭代到不动点 ----
            ApplyTopologyFilter(plan, options.TopologyCheckMode, options.AlignmentToleranceMm);

            return plan;
        }

        // 按连通分量求种子的位移，再将同一位移赋给所有成员。
        // 管件/竖向管只跟随平移，不拿它们的外径或端点标高计算对齐。
        private static void BuildGroupItems(AlignmentPlan plan, AlignmentRequest request, PipeAlignOptions options)
        {
            var members = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            var edges = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
            foreach (PipeInfo pipe in request.TargetPipes)
            {
                if (pipe == null || string.IsNullOrEmpty(pipe.InstanceId))
                    throw new PipeAlignValidationException("整组成员缺少实例 ID，未生成移动计划。");
                members[pipe.InstanceId] = pipe;
                edges[pipe.InstanceId] = new List<string>();
            }
            foreach (PipeInfo pipe in members.Values)
            {
                if (pipe.Topology == null || !pipe.Topology.IsKnown)
                    throw new PipeAlignValidationException("整组成员连接关系未知：" + pipe.DisplayName);
                foreach (PipeConnection connection in pipe.Topology.Connections)
                {
                    if (!members.ContainsKey(connection.OtherInstanceId ?? ""))
                        throw new PipeAlignValidationException("整组仍连接到未移动对象：" + connection.DisplayName);
                    edges[pipe.InstanceId].Add(connection.OtherInstanceId);
                    edges[connection.OtherInstanceId].Add(pipe.InstanceId);
                }
            }
            var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string root in members.Keys)
            {
                if (!visited.Add(root)) continue;
                var group = new List<PipeInfo>();
                var pending = new Queue<string>();
                pending.Enqueue(root);
                while (pending.Count > 0)
                {
                    string id = pending.Dequeue();
                    group.Add(members[id]);
                    foreach (string other in edges[id])
                        if (visited.Add(other)) pending.Enqueue(other);
                }
                double? delta = null;
                foreach (PipeInfo pipe in group)
                {
                    if (PipeIdentity.SamePipe(pipe, request.ReferencePipe))
                        throw new PipeAlignValidationException("连通组包含基准管，基准管不能一起移动。");
                    if (pipe.IsFromReference || pipe.IsReadOnly || pipe.IsLocked || pipe.Axis == null
                        || pipe.Axis.IsDegenerate || !options.BuildGroupPolicy().IsMovable(
                            PipeConnectionClassifier.Classify(pipe.ClassName)))
                        throw new PipeAlignValidationException("整组成员不可平移：" + pipe.DisplayName);
                    if (!Contains(request.SeedInstanceIds, pipe.InstanceId)) continue;
                    ValidationOutcome check = PipeValidationService.ValidateTargetPipe(pipe, request.Mode,
                        request.SurfaceMode, options);
                    if (!check.IsValid) throw new PipeAlignValidationException(check.Reason);
                    double required = plan.ReferenceElevationMm - ElevationCalculator.GetAlignmentElevation(
                        pipe, request.Mode, request.SurfaceMode);
                    if (delta.HasValue && Math.Abs(delta.Value - required) > options.AlignmentToleranceMm)
                        throw new PipeAlignValidationException("同一连通组的选中管道需要不同 ΔZ，无法同时对齐。请只选一根作为整组移动起点。");
                    delta = required;
                }
                if (!delta.HasValue)
                    throw new PipeAlignValidationException("连通组没有用户选中的起点管道。");
                foreach (PipeInfo pipe in group)
                {
                    double current = ElevationCalculator.GetAlignmentElevation(pipe, request.Mode, request.SurfaceMode);
                    plan.Add(new AlignmentPlanItem(pipe, request.Mode, request.SurfaceMode)
                    {
                        AddedByGroup = !Contains(request.SeedInstanceIds, pipe.InstanceId),
                        CurrentElevationMm = current,
                        ReferenceElevationMm = current + delta.Value,
                        DeltaZmm = delta.Value,
                        OutsideDiameterMm = pipe.OutsideDiameterMm ?? 0.0,
                        EffectiveDiameterMm = pipe.EffectiveDiameterMm(request.SurfaceMode),
                        Status = Math.Abs(delta.Value) <= options.AlignmentToleranceMm
                            ? PlanItemStatus.AlreadyAligned : PlanItemStatus.Ready
                    });
                }
            }
        }

        /// <summary>实例 ID 是否落在集合里（不区分大小写）。</summary>
        private static bool Contains(IList<string> values, string candidate)
        {
            if (values == null || string.IsNullOrEmpty(candidate)) return false;
            foreach (string value in values)
            {
                if (string.Equals(value, candidate, StringComparison.OrdinalIgnoreCase)) return true;
            }
            return false;
        }

        /// <summary>
        /// 连接对象的类名对用户没有意义（"连接 PIPE"）；能对上本次已读取的管道时，
        /// 改用它的管线号（"连接 P-101"）。纯查表，不改动任何 Bentley 数据。
        /// </summary>
        private static void EnrichConnectionNames(AlignmentPlan plan, AlignmentRequest request)
        {
            Dictionary<string, string> byInstanceId = new Dictionary<string, string>(StringComparer.Ordinal);
            AddKnownPipe(byInstanceId, request.ReferencePipe);
            foreach (PipeInfo pipe in request.TargetPipes)
                AddKnownPipe(byInstanceId, pipe);
            if (byInstanceId.Count == 0) return;

            foreach (AlignmentPlanItem item in plan.Items)
            {
                if (item.Pipe == null || item.Pipe.Topology == null) continue;
                foreach (PipeConnection connection in item.Pipe.Topology.Connections)
                {
                    if (string.IsNullOrEmpty(connection.OtherInstanceId)) continue;
                    string number;
                    if (byInstanceId.TryGetValue(connection.OtherInstanceId, out number))
                        connection.OtherPipeNumber = number;
                }
            }
        }

        private static void AddKnownPipe(IDictionary<string, string> map, PipeInfo pipe)
        {
            if (pipe == null || string.IsNullOrEmpty(pipe.InstanceId)) return;
            if (string.IsNullOrEmpty(pipe.PipeNumber)) return;
            map[pipe.InstanceId] = pipe.PipeNumber;
        }

        /// <summary>
        /// 反复剔除"连到不移动对象"的目标管，直到集合不再变化。
        /// 循环次数上限为目标管数量 + 1：每轮至少剔除一根，否则立即退出。
        /// </summary>
        private static void ApplyTopologyFilter(AlignmentPlan plan, PipeTopologyCheckMode checkMode, double deltaToleranceMm = 0.001)
        {
            if (checkMode == PipeTopologyCheckMode.Off) return;

            int guard = plan.Items.Count + 1;
            for (int round = 0; round < guard; round++)
            {
                List<string> movingInstanceIds = plan.ReadyInstanceIds();
                bool changed = false;

                foreach (AlignmentPlanItem item in plan.Items)
                {
                    if (item.Status != PlanItemStatus.Ready) continue;
                    ValidationOutcome topology = PipeValidationService.ValidateTopology(
                        item.Pipe, movingInstanceIds, checkMode);
                    if (topology.IsValid && item.Pipe.Topology != null)
                    {
                        foreach (PipeConnection connection in item.Pipe.Topology.Connections)
                            foreach (AlignmentPlanItem other in plan.Items)
                                if (other.Status == PlanItemStatus.Ready && other.Pipe != null
                                    && string.Equals(other.Pipe.InstanceId, connection.OtherInstanceId, StringComparison.OrdinalIgnoreCase)
                                    && Math.Abs(other.DeltaZmm - item.DeltaZmm) > deltaToleranceMm)
                                    topology = ValidationOutcome.Invalid("相连目标管的 ΔZ 不一致，移动会产生断口。请改用整组移动并选择一个起点。");
                    }
                    if (topology.IsValid) continue;
                    item.Status = PlanItemStatus.Skipped;
                    item.SkipReason = topology.Reason;
                    changed = true;
                }

                if (!changed) return;
            }
        }
    }
}
