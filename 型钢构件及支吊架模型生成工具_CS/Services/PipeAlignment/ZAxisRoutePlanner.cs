using System;
using System.Collections.Generic;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>锁 Z 的受限路由：水平管/管件随动，遇竖直直管截止并固定另一端。</summary>
    internal static partial class ZAxisRoutePlanner
    {
        internal static AlignmentPlan BuildBatch(PipeInfo reference, IList<PipeInfo> seeds,
            AlignmentMode mode, SurfaceMode surface, Func<string, PipeInfo> read, PipeAlignOptions options)
        {
            if (seeds == null || seeds.Count == 0 || seeds.Count > 15)
                throw new PipeAlignValidationException("请选择 1～15 根起点水平管。");
            var valid = PipeValidationService.ValidateReferencePipe(reference, surface, options);
            if (!valid.IsValid) throw new PipeAlignValidationException(valid.Reason);
            var result = new AlignmentPlan(reference, mode, surface,
                ElevationCalculator.GetAlignmentElevation(reference, mode, surface)) { IsZStretch = true };
            var routes = new List<AlignmentPlan>();
            var blocked = new HashSet<int>();
            var snapshots = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            Func<string, PipeInfo> readOnce = delegate(string id)
            {
                PipeInfo pipe;
                if (!snapshots.TryGetValue(id, out pipe)) { pipe = read(id); snapshots.Add(id, pipe); }
                return pipe;
            };
            foreach (var seed in seeds)
            {
                try { routes.Add(BuildAligned(reference, seed, mode, surface, readOnce, options)); }
                catch (PipeAlignValidationException ex)
                { result.Add(new AlignmentPlanItem(seed, mode, surface) { Status = PlanItemStatus.Skipped, SkipReason = ex.Message }); }
            }
            for (int i = 0; i < routes.Count; i++)
                for (int j = i + 1; j < routes.Count; j++)
                    if (Conflicts(routes[i], routes[j])) { blocked.Add(i); blocked.Add(j); }
            // 冲突组的重叠路由必须一并停止，不能由另一起点重新带入。
            bool changed;
            do
            {
                changed = false;
                for (int i = 0; i < routes.Count; i++) if (blocked.Contains(i))
                    for (int j = 0; j < routes.Count; j++) if (!blocked.Contains(j))
                        foreach (var x in routes[i].Items) foreach (var y in routes[j].Items)
                            if (PipeIdentity.SamePipe(x.Pipe, y.Pipe)) changed |= blocked.Add(j);
            } while (changed);
            var seen = new HashSet<string>();
            var fixedSeen = new HashSet<string>();
            var seedKeys = new HashSet<string>();
            foreach (var seed in seeds) seedKeys.Add(PipeIdentity.Key(seed));
            for (int i = 0; i < routes.Count; i++)
            {
                foreach (var item in routes[i].Items)
                {
                    if (blocked.Contains(i))
                    { item.Status = PlanItemStatus.Skipped; item.SkipReason = "起点展开范围存在位移或固定端冲突，相关组全部跳过。"; }
                    item.AddedByGroup = !seedKeys.Contains(PipeIdentity.Key(item.Pipe));
                    if (seen.Add(PipeIdentity.Key(item.Pipe))) result.Add(item);
                }
                if (!blocked.Contains(i)) foreach (var pipe in routes[i].FixedPipes)
                    if (fixedSeen.Add(PipeIdentity.Key(pipe))) result.FixedPipes.Add(pipe);
            }
            int pipes = 0;
            foreach (var item in result.Items)
                if (item.WillMove && PipeConnectionClassifier.Classify(item.Pipe.ClassName) == PipeConnectionKind.Pipe) pipes++;
            if (pipes > 15) throw new PipeAlignValidationException("本批实际需要修改 " + pipes + " 根直管（含随动水平管和伸缩立管），超过 15 根上限。请减少起点或分批操作。");
            return result;
        }

        private static bool Conflicts(AlignmentPlan a, AlignmentPlan b)
        {
            foreach (var x in a.Items) foreach (var y in b.Items)
                if (PipeIdentity.Key(x.Pipe) == PipeIdentity.Key(y.Pipe) && !SameAxis(x.TargetAxis, y.TargetAxis)) return true;
            foreach (var x in a.Items) foreach (var y in b.FixedPipes)
                if (x.WillMove && PipeIdentity.Key(x.Pipe) == PipeIdentity.Key(y)) return true;
            foreach (var x in b.Items) foreach (var y in a.FixedPipes)
                if (x.WillMove && PipeIdentity.Key(x.Pipe) == PipeIdentity.Key(y)) return true;
            return false;
        }

        private static bool SameAxis(PipeAxis a, PipeAxis b)
        {
            return a != null && b != null && Math.Abs(a.StartXmm-b.StartXmm)<0.001
                && Math.Abs(a.StartYmm-b.StartYmm)<0.001 && Math.Abs(a.StartZmm-b.StartZmm)<0.001
                && Math.Abs(a.EndXmm-b.EndXmm)<0.001 && Math.Abs(a.EndYmm-b.EndYmm)<0.001
                && Math.Abs(a.EndZmm-b.EndZmm)<0.001;
        }

        internal static AlignmentPlan BuildAligned(PipeInfo reference, PipeInfo seed,
            AlignmentMode mode, SurfaceMode surface, Func<string, PipeInfo> read, PipeAlignOptions options)
        {
            options = options ?? new PipeAlignOptions();
            ValidationOutcome valid = PipeValidationService.ValidateReferencePipe(reference, surface, options);
            if (!valid.IsValid) throw new PipeAlignValidationException(valid.Reason);
            valid = PipeValidationService.ValidateTargetPipe(seed, mode, surface, options);
            if (!valid.IsValid) throw new PipeAlignValidationException(valid.Reason);
            double elevation = ElevationCalculator.GetAlignmentElevation(reference, mode, surface);
            double delta = ElevationCalculator.ComputeDeltaZ(elevation,
                ElevationCalculator.GetAlignmentElevation(seed, mode, surface));
            AlignmentPlan route = Build(seed, delta, read, options);
            var plan = new AlignmentPlan(reference, mode, surface, elevation) { IsZStretch = true };
            foreach (AlignmentPlanItem item in route.Items)
            {
                if (PipeIdentity.Key(item.Pipe) == PipeIdentity.Key(reference)
                    || (!reference.IsFromReference && !string.IsNullOrEmpty(reference.InstanceId) && reference.InstanceId == item.Pipe.InstanceId))
                    throw new PipeAlignValidationException("基准管处于随动或伸缩范围，不能保持固定，请选择范围外的基准管。");
                double current = ElevationCalculator.GetAlignmentElevation(item.Pipe, mode, surface);
                plan.Add(new AlignmentPlanItem(item.Pipe, mode, surface)
                {
                    Status = item.Status, SkipReason = item.SkipReason, DeltaZmm = item.DeltaZmm,
                    AdjustedAxis = item.AdjustedAxis, IsRigidAdjustment = item.IsRigidAdjustment, AddedByGroup = item.AddedByGroup,
                    OutsideDiameterMm = item.OutsideDiameterMm,
                    EffectiveDiameterMm = item.Pipe.EffectiveDiameterMm(surface),
                    CurrentElevationMm = current,
                    ReferenceElevationMm = current + (item.TargetAxis.CenterElevationMm - item.Pipe.Axis.CenterElevationMm)
                });
            }
            foreach (PipeInfo fixedPipe in route.FixedPipes) plan.FixedPipes.Add(fixedPipe);
            return plan;
        }

        internal static AlignmentPlan Build(PipeInfo seed, double deltaZmm,
            Func<string, PipeInfo> read, PipeAlignOptions options)
        {
            options = options ?? new PipeAlignOptions();
            if (double.IsNaN(deltaZmm) || double.IsInfinity(deltaZmm))
                throw new PipeAlignValidationException("Z 位移必须是有限数值。");
            ValidationOutcome valid = PipeValidationService.ValidateTargetPipe(seed,
                AlignmentMode.Center, SurfaceMode.Pipe, options);
            if (!valid.IsValid) throw new PipeAlignValidationException(valid.Reason);
            var offset = TryBuildOffset(seed, deltaZmm, read, options);
            if (offset != null) return offset;
            var all = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            var moving = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            var vertical = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase);
            var queue = new Queue<PipeInfo>();
            all.Add(Id(seed), seed);
            queue.Enqueue(seed);
            while (queue.Count > 0)
            {
                PipeInfo pipe = queue.Dequeue();
                string id = Id(pipe);
                if (moving.ContainsKey(id)) continue;
                Writable(pipe);
                Known(pipe);
                PipeConnectionKind kind = PipeConnectionClassifier.Classify(pipe.ClassName);
                // 配置不能把设备/未知类变成路由随动对象。
                if (kind != PipeConnectionKind.Pipe && kind != PipeConnectionKind.Fitting
                    && kind != PipeConnectionKind.Flange && kind != PipeConnectionKind.Valve)
                    throw new PipeAlignValidationException("移动范围遇到固定边界：" + pipe.DisplayName);
                if (kind == PipeConnectionKind.Pipe && !pipe.Axis.IsHorizontal(options.HorizontalToleranceMm))
                    throw new PipeAlignValidationException("随动范围包含斜管，不能只沿 Z 调整：" + pipe.DisplayName);
                moving.Add(id, pipe);
                if (moving.Count + vertical.Count > options.MoveGroupMaxMembers)
                    throw new PipeAlignValidationException("锁 Z 移动范围超过 MoveGroupMaxMembers。");
                foreach (PipeConnection connection in pipe.Topology.Connections)
                {
                    PipeInfo neighbor = Load(connection.OtherInstanceId, all, read);
                    if (moving.ContainsKey(Id(neighbor))) continue;
                    if (IsVertical(neighbor, options.HorizontalToleranceMm))
                    {
                        Writable(neighbor);
                        Known(neighbor);
                        if (neighbor.Topology.ConnectionCount > 2)
                            throw new PipeAlignValidationException("立管有复杂分支，无法确定固定端：" + neighbor.DisplayName);
                        vertical[Id(neighbor)] = neighbor;
                        if (moving.Count + vertical.Count > options.MoveGroupMaxMembers)
                            throw new PipeAlignValidationException("锁 Z 移动范围超过 MoveGroupMaxMembers。");
                    }
                    else if (!vertical.ContainsKey(Id(neighbor))) queue.Enqueue(neighbor);
                }
            }
            var plan = new AlignmentPlan(seed, AlignmentMode.Center, SurfaceMode.Pipe,
                seed.Axis.CenterElevationMm + deltaZmm) { IsZStretch = true };
            foreach (PipeInfo pipe in moving.Values)
                plan.Add(Item(pipe, deltaZmm, null, seed, options));
            foreach (PipeInfo pipe in vertical.Values)
            {
                int movingEnd = -1;
                int movingLinks = 0;
                var fixedNeighbors = new List<PipeInfo>();
                foreach (PipeConnection connection in pipe.Topology.Connections)
                {
                    PipeInfo neighbor = Load(connection.OtherInstanceId, all, read);
                    int endpoint = ContactEndpoint(pipe.Axis, neighbor.Axis, options.RouteEndpointToleranceMm);
                    if (moving.ContainsKey(Id(neighbor)))
                    {
                        movingLinks++;
                        movingEnd = endpoint;
                    }
                    else fixedNeighbors.Add(neighbor);
                }
                if (movingLinks != 1 || movingEnd < 0)
                    throw new PipeAlignValidationException("立管两端随动或连接有歧义，不能确定唯一固定端：" + pipe.DisplayName);
                foreach (PipeInfo fixedPipe in fixedNeighbors)
                {
                    if (ContactEndpoint(pipe.Axis, fixedPipe.Axis, options.RouteEndpointToleranceMm) == movingEnd)
                        throw new PipeAlignValidationException("立管移动端同时连到固定对象：" + pipe.DisplayName);
                    Known(fixedPipe);
                    plan.FixedPipes.Add(fixedPipe);
                }
                PipeAxis a = pipe.Axis;
                PipeAxis target = new PipeAxis(a.StartXmm, a.StartYmm,
                    a.StartZmm + (movingEnd == 0 ? deltaZmm : 0.0), a.EndXmm, a.EndYmm,
                    a.EndZmm + (movingEnd == 1 ? deltaZmm : 0.0));
                if (target.LengthMm < options.MinimumStretchLengthMm
                    || target.DeltaZmm * a.DeltaZmm <= 0.0)
                    throw new PipeAlignValidationException("位移会使立管过短或方向翻转：" + pipe.DisplayName);
                plan.Add(Item(pipe, deltaZmm, target, seed, options));
            }
            return plan;
        }

        private static AlignmentPlanItem Item(PipeInfo pipe, double delta, PipeAxis target,
            PipeInfo seed, PipeAlignOptions options)
        {
            return new AlignmentPlanItem(pipe, AlignmentMode.Center, SurfaceMode.Pipe)
            {
                DeltaZmm = delta, AdjustedAxis = target,
                CurrentElevationMm = pipe.Axis.CenterElevationMm,
                ReferenceElevationMm = (target ?? pipe.Axis.ShiftedByZ(delta)).CenterElevationMm,
                AddedByGroup = !PipeIdentity.SamePipe(pipe, seed),
                OutsideDiameterMm = pipe.OutsideDiameterMm ?? 0.0,
                EffectiveDiameterMm = pipe.OutsideDiameterMm ?? 0.0,
                Status = Math.Abs(delta) <= options.AlignmentToleranceMm
                    ? PlanItemStatus.AlreadyAligned : PlanItemStatus.Ready
            };
        }

        internal static bool IsVertical(PipeInfo pipe, double toleranceMm)
        {
            return pipe != null && pipe.Axis != null
                && PipeConnectionClassifier.Classify(pipe.ClassName) == PipeConnectionKind.Pipe
                && pipe.Axis.HorizontalRunMm <= toleranceMm && Math.Abs(pipe.Axis.DeltaZmm) > toleranceMm;
        }

        private static void Writable(PipeInfo pipe)
        {
            if (pipe == null || pipe.Axis == null || pipe.Axis.IsDegenerate || pipe.IsReadOnly
                || pipe.IsFromReference || pipe.IsLocked)
                throw new PipeAlignValidationException("路由成员不存在、无可信几何或不可写：" + (pipe == null ? "未知" : pipe.DisplayName));
        }

        private static void Known(PipeInfo pipe)
        {
            if (pipe.Topology == null || !pipe.Topology.IsKnown)
                throw new PipeAlignValidationException("连接关系未知，不能确定随动与固定范围：" + pipe.DisplayName);
        }

        private static string Id(PipeInfo pipe)
        {
            if (pipe == null || string.IsNullOrEmpty(pipe.InstanceId))
                throw new PipeAlignValidationException("连接对象缺少实例 ID。");
            return pipe.InstanceId;
        }

        private static PipeInfo Load(string id, IDictionary<string, PipeInfo> cache, Func<string, PipeInfo> read)
        {
            if (string.IsNullOrEmpty(id)) throw new PipeAlignValidationException("连接对象身份未知。");
            PipeInfo pipe;
            if (cache.TryGetValue(id, out pipe)) return pipe;
            try { pipe = read == null ? null : read(id); }
            catch (Exception ex) { throw new PipeAlignValidationException("连通对象读取失败：" + ex.Message); }
            if (pipe == null || !string.Equals(Id(pipe), id, StringComparison.OrdinalIgnoreCase))
                throw new PipeAlignValidationException("连通对象读取身份不一致：" + id);
            cache.Add(id, pipe);
            return pipe;
        }

        // 用独立几何端点核对连接归属，不凭类名或列表顺序猜立管端点。
        private static int ContactEndpoint(PipeAxis vertical, PipeAxis other, double tolerance)
        {
            if (other == null) throw new PipeAlignValidationException("连接对象缺少端点几何，不能确定固定端。");
            double toStart = Math.Min(Distance(vertical, 0, other, 0), Distance(vertical, 0, other, 1));
            double toEnd = Math.Min(Distance(vertical, 1, other, 0), Distance(vertical, 1, other, 1));
            if ((toStart <= tolerance) == (toEnd <= tolerance))
                throw new PipeAlignValidationException("立管与连接构件端点不能唯一匹配，未修改模型。");
            return toStart <= tolerance ? 0 : 1;
        }

        private static double Distance(PipeAxis a, int i, PipeAxis b, int j)
        {
            double x = (i == 0 ? a.StartXmm : a.EndXmm) - (j == 0 ? b.StartXmm : b.EndXmm);
            double y = (i == 0 ? a.StartYmm : a.EndYmm) - (j == 0 ? b.StartYmm : b.EndYmm);
            double z = (i == 0 ? a.StartZmm : a.EndZmm) - (j == 0 ? b.StartZmm : b.EndZmm);
            return Math.Sqrt(x * x + y * y + z * z);
        }
    }
}
