using System.Globalization;
using System;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 移动之后的三路读数（开发指南 §19 的"数据一致性检查"）。
    /// <para>
    /// 只用"几何变了没有"一个判据是不够的：失败时无法区分下面两种**修法完全不同**的情况，
    /// 于是每次都要再猜一轮 —— 真机实测第一轮就吃了这个亏。
    /// </para>
    /// <list type="bullet">
    /// <item><description><b>数据没写进去</b>：EC 变换矩阵没变 → 修改接口本身没生效，
    /// 要换"取对象的方式"或补提交步骤。</description></item>
    /// <item><description><b>数据写了、图形没重建</b>：EC 变了但几何没变 → 缺的是图形更新，
    /// 要补 <c>AllowGraphicsUpdate</c> / 重建那一步。</description></item>
    /// </list>
    /// </summary>
    internal sealed class PipeMoveVerification
    {
        /// <summary>元素几何读出的中心线标高（mm）；取不到为 <c>null</c>。</summary>
        internal double? GeometryCenterElevationMm { get; set; }

        /// <summary>元素上 EC 变换矩阵的 Z 平移分量原始值；读不到为 <c>null</c>。</summary>
        internal double? EcTranslationZRaw { get; set; }

        /// <summary>EC 原始值按"每子单位多少 UOR"换算成毫米的结果；无法换算为 <c>null</c>。</summary>
        internal double? EcTranslationZmm { get; set; }

        /// <summary>EC 的 Z 平移相对**移动前**是否真的变了。数据没写进去时为 <c>false</c>。</summary>
        internal bool EcChanged { get; set; }

        /// <summary>读取过程中的说明（失败原因等），没有则为 <c>null</c>。</summary>
        internal string Warning { get; set; }

        internal PipeTopology Topology { get; set; }
        internal PipeAxis GeometryAxis { get; set; }
        internal double? EcLengthRaw { get; set; }

        internal bool MatchesTarget(AlignmentPlanItem item, double toleranceMm)
        {
            if (!item.IsStretch) return MatchesPosition(item.Pipe, item.DeltaZmm, toleranceMm)
                && SameAxis(GeometryAxis, item.TargetAxis, toleranceMm);
            PipeInfo pipe = item.Pipe;
            double scale = pipe.MoveProbe == null ? 0.0 : pipe.MoveProbe.ApiUnitsPerMillimeter;
            if (!SameAxis(GeometryAxis, item.TargetAxis, toleranceMm) || scale <= 0.0
                || !pipe.EcTranslationZRaw.HasValue || !EcTranslationZRaw.HasValue
                || !EcLengthRaw.HasValue || !pipe.EcLengthRaw.HasValue || pipe.PropertyLengthScale <= 0.0)
                return false;
            double origin = pipe.EcTranslationZRaw.Value / scale;
            double expectedOrigin;
            if (Math.Abs(origin - pipe.Axis.StartZmm) <= toleranceMm) expectedOrigin = item.TargetAxis.StartZmm;
            else if (Math.Abs(origin - pipe.Axis.EndZmm) <= toleranceMm) expectedOrigin = item.TargetAxis.EndZmm;
            else return false;
            return Math.Abs(EcTranslationZRaw.Value / scale - expectedOrigin) <= toleranceMm
                && Math.Abs(EcLengthRaw.Value * pipe.PropertyLengthScale - item.TargetAxis.LengthMm) <= toleranceMm;
        }

        internal bool MatchesFixed(PipeInfo pipe, double toleranceMm)
        {
            return SameAxis(GeometryAxis, pipe.Axis, toleranceMm) && MatchesConnections(pipe)
                && EcTranslationZRaw.HasValue && pipe.EcTranslationZRaw.HasValue
                && Math.Abs(EcTranslationZRaw.Value - pipe.EcTranslationZRaw.Value) <= 1.0e-6
                && (!pipe.EcLengthRaw.HasValue || (EcLengthRaw.HasValue
                    && Math.Abs(EcLengthRaw.Value - pipe.EcLengthRaw.Value) <= 1.0e-6));
        }

        internal static bool SameAxis(PipeAxis a, PipeAxis b, double toleranceMm)
        {
            if (a == null || b == null) return false;
            return (SamePoint(a, true, b, true, toleranceMm) && SamePoint(a, false, b, false, toleranceMm))
                || (SamePoint(a, true, b, false, toleranceMm) && SamePoint(a, false, b, true, toleranceMm));
        }

        private static bool SamePoint(PipeAxis a, bool s, PipeAxis b, bool t, double tol)
        {
            return Math.Abs((s ? a.StartXmm : a.EndXmm) - (t ? b.StartXmm : b.EndXmm)) <= tol
                && Math.Abs((s ? a.StartYmm : a.EndYmm) - (t ? b.StartYmm : b.EndYmm)) <= tol
                && Math.Abs((s ? a.StartZmm : a.EndZmm) - (t ? b.StartZmm : b.EndZmm)) <= tol;
        }

        internal bool MatchesPosition(PipeInfo pipe, double deltaZmm, double toleranceMm)
        {
            double scale = pipe.MoveProbe == null ? 0.0 : pipe.MoveProbe.ApiUnitsPerMillimeter;
            return GeometryCenterElevationMm.HasValue && pipe.Axis != null
                && Math.Abs(GeometryCenterElevationMm.Value - pipe.Axis.CenterElevationMm - deltaZmm) <= toleranceMm
                && EcTranslationZRaw.HasValue && pipe.EcTranslationZRaw.HasValue && scale > 0.0
                && Math.Abs((EcTranslationZRaw.Value - pipe.EcTranslationZRaw.Value) / scale - deltaZmm) <= toleranceMm;
        }

        internal bool MatchesConnections(PipeInfo pipe)
        {
            if (Topology == null || !Topology.IsKnown || pipe.Topology == null || !pipe.Topology.IsKnown)
                return false;
            var before = new System.Collections.Generic.HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var after = new System.Collections.Generic.HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (PipeConnection connection in pipe.Topology.Connections) before.Add(connection.OtherInstanceId);
            foreach (PipeConnection connection in Topology.Connections) after.Add(connection.OtherInstanceId);
            return before.SetEquals(after);
        }

        /// <summary>一行中文读数，直接进日志 / 结果。</summary>
        internal string Describe(double? baselineEcRaw)
        {
            string geometry = GeometryCenterElevationMm.HasValue
                ? GeometryCenterElevationMm.Value.ToString("F3", CultureInfo.InvariantCulture) + " mm"
                : "取不到";
            string ec = EcTranslationZmm.HasValue
                ? EcTranslationZmm.Value.ToString("F3", CultureInfo.InvariantCulture) + " mm"
                    + "（原始 " + EcTranslationZRaw.Value.ToString("G", CultureInfo.InvariantCulture) + "）"
                : "取不到";

            string verdict;
            if (!EcTranslationZRaw.HasValue || !baselineEcRaw.HasValue)
                verdict = "EC 变换读数不可用，无法判定数据是否写回";
            else if (EcChanged)
                verdict = "EC 变换已改变（数据模型接受过修改）";
            else
                verdict = "EC 变换未改变（修改没写进数据模型）";

            return string.Format(CultureInfo.InvariantCulture,
                "几何复核 {0}；EC 变换 {1}；{2}{3}",
                geometry, ec, verdict,
                string.IsNullOrEmpty(Warning) ? "" : "；" + Warning);
        }
    }
}
