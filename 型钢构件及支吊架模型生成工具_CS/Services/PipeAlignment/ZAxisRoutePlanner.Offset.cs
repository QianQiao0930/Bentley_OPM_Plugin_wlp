using System;
using System.Collections.Generic;
namespace SteelSectionProbe.PipeAlignment
{
    internal static partial class ZAxisRoutePlanner
    {
        // 水平管—弯头—斜管—弯头—固定水平管，保持弯头角度和斜管方向。
        private static AlignmentPlan TryBuildOffset(PipeInfo seed, double delta, Func<string, PipeInfo> read, PipeAlignOptions options)
        {
            Known(seed);
            var cache = new Dictionary<string, PipeInfo>(StringComparer.OrdinalIgnoreCase) { { Id(seed), seed } };
            PipeInfo elbow = null, slope = null;
            foreach (var link in seed.Topology.Connections)
            {
                var candidate = Load(link.OtherInstanceId, cache, read);
                if (!IsElbow(candidate)) continue;
                Known(candidate);
                foreach (var next in candidate.Topology.Connections)
                {
                    if (string.Equals(next.OtherInstanceId, Id(seed), StringComparison.OrdinalIgnoreCase)) continue;
                    var pipe = Load(next.OtherInstanceId, cache, read);
                    if (pipe.Axis == null || PipeConnectionClassifier.Classify(pipe.ClassName) != PipeConnectionKind.Pipe
                        || pipe.Axis.IsHorizontal(options.HorizontalToleranceMm) || IsVertical(pipe, options.HorizontalToleranceMm)) continue;
                    if (slope != null) throw new PipeAlignValidationException("选中管连接多个斜管乙字弯，暂不支持。");
                    elbow = candidate; slope = pipe;
                }
            }
            if (slope == null) return null;
            Writable(seed); Writable(elbow); Writable(slope); Known(slope);
            if (seed.Topology.ConnectionCount != 1)
                throw new PipeAlignValidationException("乙字弯选中水平管的另一端还有连接，升降会影响该连接；请先调整该边界。");
            RequireTwoLinks(elbow); RequireTwoLinks(slope);
            OtherNeighbor(elbow, seed, cache, read);
            var fixedElbow = OtherNeighbor(slope, elbow, cache, read);
            if (!IsElbow(fixedElbow)) throw new PipeAlignValidationException("斜管固定端必须连接乙字弯弯头。");
            Known(fixedElbow); RequireTwoLinks(fixedElbow);
            var fixedPipe = OtherNeighbor(fixedElbow, slope, cache, read);
            Known(fixedPipe);
            bool reciprocal = false;
            foreach (var connection in fixedPipe.Topology.Connections)
                if (string.Equals(connection.OtherInstanceId, Id(fixedElbow), StringComparison.OrdinalIgnoreCase)) reciprocal = true;
            if (!reciprocal) throw new PipeAlignValidationException("固定水平管连接不是互反链。");
            if (fixedPipe.Axis == null || PipeConnectionClassifier.Classify(fixedPipe.ClassName) != PipeConnectionKind.Pipe
                || !fixedPipe.Axis.IsHorizontal(options.HorizontalToleranceMm))
                throw new PipeAlignValidationException("乙字弯另一侧必须是固定水平直管。");
            int seedEnd = ContactEndpoint(seed.Axis, elbow.Axis, options.RouteEndpointToleranceMm);
            int slopeEnd = ContactEndpoint(slope.Axis, elbow.Axis, options.RouteEndpointToleranceMm);
            if (ContactEndpoint(slope.Axis, fixedElbow.Axis, options.RouteEndpointToleranceMm) == slopeEnd)
                throw new PipeAlignValidationException("斜管两端连接归属有歧义。");
            if (ContactEndpoint(elbow.Axis, slope.Axis, options.RouteEndpointToleranceMm)
                == ContactEndpoint(elbow.Axis, seed.Axis, options.RouteEndpointToleranceMm))
                throw new PipeAlignValidationException("移动弯头端点匹配有歧义。");
            if (ContactEndpoint(fixedElbow.Axis, slope.Axis, options.RouteEndpointToleranceMm)
                == ContactEndpoint(fixedElbow.Axis, fixedPipe.Axis, options.RouteEndpointToleranceMm))
                throw new PipeAlignValidationException("固定弯头端点匹配有歧义。");
            var a = slope.Axis;
            double dx = delta * (a.EndXmm - a.StartXmm) / a.DeltaZmm;
            double dy = delta * (a.EndYmm - a.StartYmm) / a.DeltaZmm;
            RequireParallel(seed.Axis, fixedPipe.Axis);
            double cross = dx * (seed.Axis.EndYmm-seed.Axis.StartYmm) - dy * (seed.Axis.EndXmm-seed.Axis.StartXmm);
            if (Math.Abs(cross) > 0.001 * seed.Axis.HorizontalRunMm)
                throw new PipeAlignValidationException("斜管水平投影不沿选中水平管轴线，无法仅靠伸缩保持连接。");
            var seedTarget = ShiftEnd(seed.Axis.ShiftedByZ(delta), seedEnd, dx, dy, 0);
            var slopeTarget = ShiftEnd(a, slopeEnd, dx, dy, delta);
            CheckLengthDirection(seed.Axis, seedTarget, options);
            CheckLengthDirection(a, slopeTarget, options);
            var plan = new AlignmentPlan(seed, AlignmentMode.Center, SurfaceMode.Pipe, seed.Axis.CenterElevationMm+delta) { IsZStretch=true };
            plan.Add(Item(seed, delta, seedTarget, seed, options));
            var elbowItem = Item(elbow, delta, ShiftAll(elbow.Axis, dx, dy, delta), seed, options);
            elbowItem.IsRigidAdjustment = true;
            plan.Add(elbowItem);
            plan.Add(Item(slope, delta, slopeTarget, seed, options));
            // 固定侧全链只读快照，防止连接重建顺带拖动未授权对象。
            var fixedQueue = new Queue<PipeInfo>(); fixedQueue.Enqueue(fixedElbow);
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            while (fixedQueue.Count > 0)
            {
                var pipe = fixedQueue.Dequeue();
                if (!seen.Add(Id(pipe))) continue;
                if (PipeIdentity.SamePipe(pipe, seed) || PipeIdentity.SamePipe(pipe, elbow))
                    throw new PipeAlignValidationException("乙字弯存在回路，固定侧与移动侧重叠。");
                Known(pipe);
                if (pipe.Axis == null || pipe.Axis.IsDegenerate) throw new PipeAlignValidationException("固定侧缺少可复核几何。");
                plan.FixedPipes.Add(pipe);
                if (seen.Count + 3 > options.MoveGroupMaxMembers)
                    throw new PipeAlignValidationException("乙字弯固定侧复核范围超过成员上限。");
                foreach (var link in pipe.Topology.Connections)
                {
                    if (string.Equals(link.OtherInstanceId, Id(slope), StringComparison.OrdinalIgnoreCase)) continue;
                    fixedQueue.Enqueue(Load(link.OtherInstanceId, cache, read));
                }
            }
            return plan;
        }
        private static bool IsElbow(PipeInfo pipe)
        { return pipe != null && pipe.ClassName != null && pipe.ClassName.IndexOf("ELBOW",StringComparison.OrdinalIgnoreCase)>=0; }
        private static void RequireTwoLinks(PipeInfo pipe)
        { if (pipe.Topology.ConnectionCount != 2) throw new PipeAlignValidationException("乙字弯成员必须恰好连接两个对象，无分支："+pipe.DisplayName); }
        private static PipeInfo OtherNeighbor(PipeInfo pipe, PipeInfo previous, IDictionary<string,PipeInfo> cache, Func<string,PipeInfo> read)
        {
            bool back=false; PipeInfo other=null;
            foreach(var link in pipe.Topology.Connections)
                if(string.Equals(link.OtherInstanceId,Id(previous),StringComparison.OrdinalIgnoreCase)) back=true;
                else if(other==null) other=Load(link.OtherInstanceId,cache,read);
                else throw new PipeAlignValidationException("乙字弯连接有分支。");
            if(!back || other==null) throw new PipeAlignValidationException("乙字弯连接不是互反链。");
            return other;
        }
        private static void RequireParallel(PipeAxis a, PipeAxis b)
        {
            double cross=(a.EndXmm-a.StartXmm)*(b.EndYmm-b.StartYmm)-(a.EndYmm-a.StartYmm)*(b.EndXmm-b.StartXmm);
            if(a.IsDegenerate || b.IsDegenerate || Math.Abs(cross)>1e-6*a.HorizontalRunMm*b.HorizontalRunMm)
                throw new PipeAlignValidationException("乙字弯两侧水平管不平行，暂不支持。");
        }
        private static PipeAxis ShiftEnd(PipeAxis a,int end,double dx,double dy,double dz)
        { return new PipeAxis(a.StartXmm+(end==0?dx:0),a.StartYmm+(end==0?dy:0),a.StartZmm+(end==0?dz:0),a.EndXmm+(end==1?dx:0),a.EndYmm+(end==1?dy:0),a.EndZmm+(end==1?dz:0)); }
        private static PipeAxis ShiftAll(PipeAxis a,double dx,double dy,double dz)
        { return new PipeAxis(a.StartXmm+dx,a.StartYmm+dy,a.StartZmm+dz,a.EndXmm+dx,a.EndYmm+dy,a.EndZmm+dz); }
        private static void CheckLengthDirection(PipeAxis a, PipeAxis b, PipeAlignOptions options)
        {
            double dot=(a.EndXmm-a.StartXmm)*(b.EndXmm-b.StartXmm)+(a.EndYmm-a.StartYmm)*(b.EndYmm-b.StartYmm)+a.DeltaZmm*b.DeltaZmm;
            if(double.IsNaN(b.LengthMm)||double.IsInfinity(b.LengthMm)||b.LengthMm<options.MinimumStretchLengthMm||dot<=0)
                throw new PipeAlignValidationException("乙字弯调整会使直管过短或方向翻转。");
        }
    }
}
