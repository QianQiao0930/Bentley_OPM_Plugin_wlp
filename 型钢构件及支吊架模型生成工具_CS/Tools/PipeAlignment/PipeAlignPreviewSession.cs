using System;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Com = Bentley.Interop.MicroStationDGN;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 对齐预览：用**临时直线**把"当前中心线"和"对齐后中心线"画在活动模型里
    /// （开发指南 §25）。
    /// <para>
    /// 约定（与本仓库其它预览一致）：
    /// </para>
    /// <list type="bullet">
    /// <item><description>预览元素只由本会话创建、也只由本会话删除；</description></item>
    /// <item><description>重建时**先把新的一组全部写完，成功了再删旧的一组** ——
    /// 否则中途失败会连旧预览都没了；</description></item>
    /// <item><description>取消 / 重置 / 关闭窗口 / 应用完成都必须 <see cref="Clear"/>；</description></item>
    /// <item><description>预览**不改动管道对象本身**，只画线，因此不会留下"改了一半"的模型。</description></item>
    /// </list>
    /// </summary>
    internal sealed class PipeAlignPreviewSession
    {
        /// <summary>当前中心线颜色（蓝色，MicroStation 颜色索引 1）。</summary>
        private const uint CurrentColor = 1;

        /// <summary>对齐后中心线颜色（红色，MicroStation 颜色索引 3），用户一眼能看出要挪到哪。</summary>
        private const uint TargetColor = 3;

        private readonly System.Collections.Generic.List<Com.TransientElementContainer> _containers =
            new System.Collections.Generic.List<Com.TransientElementContainer>();

        internal int Count { get { return _containers.Count; } }

        /// <summary>
        /// 按计划重建预览。任何一根线写失败都不影响已有预览（旧的保留）。
        /// </summary>
        internal void Rebuild(AlignmentPlan plan, IUnitService units, bool showCurrent, bool showTarget)
        {
            if (units == null || !units.IsAvailable)
                throw new InvalidOperationException("取不到模型单位换算系数，无法绘制预览。");

            System.Collections.Generic.List<Com.TransientElementContainer> created = new System.Collections.Generic.List<Com.TransientElementContainer>();
            try
            {
                if (plan != null)
                {
                    foreach (AlignmentPlanItem item in plan.Items)
                    {
                        if (item.Status != PlanItemStatus.Ready) continue;
                        if (item.Pipe == null || item.Pipe.Axis == null) continue;

                        if (showCurrent)
                            created.Add(CreateLine(item.Pipe.Axis, units, CurrentColor));

                        PipeAxis target = item.TargetAxis;
                        if (showTarget && target != null)
                            created.Add(CreateLine(target, units, TargetColor));
                    }
                }
            }
            catch
            {
                // 新预览没建全：把已经建出来的部分删掉，保留旧预览。
                DeleteAll(created);
                throw;
            }

            // 新预览全部成功，再删旧的。
            DeleteAll(_containers);
            _containers.Clear();
            _containers.AddRange(created);
        }

        /// <summary>删除全部预览元素。可重复调用，不抛异常。</summary>
        internal void Clear()
        {
            DeleteAll(_containers);
            _containers.Clear();
        }

        private static Com.TransientElementContainer CreateLine(PipeAxis axis, IUnitService units, uint color)
        {
            DgnModel model = Session.Instance.GetActiveDgnModel();
            if (model == null) throw new InvalidOperationException("没有活动模型，无法绘制预览。");

            DPoint3d start = new DPoint3d(
                units.MillimeterToUor(axis.StartXmm),
                units.MillimeterToUor(axis.StartYmm),
                units.MillimeterToUor(axis.StartZmm));
            DPoint3d end = new DPoint3d(
                units.MillimeterToUor(axis.EndXmm),
                units.MillimeterToUor(axis.EndYmm),
                units.MillimeterToUor(axis.EndZmm));

            double dx = end.X - start.X, dy = end.Y - start.Y, dz = end.Z - start.Z;
            if (dx * dx + dy * dy + dz * dz <= 1.0e-12) return null;

            double mmPerMaster = DgnUnitServiceFactory.MillimetersPerMasterUnit(model);
            if (mmPerMaster <= 0.0)
                throw new InvalidOperationException("无法换算预览主单位，未创建预览。");
            var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            Com.Point3d comStart = app.Point3dFromXYZ(axis.StartXmm / mmPerMaster,
                axis.StartYmm / mmPerMaster, axis.StartZmm / mmPerMaster);
            Com.Point3d comEnd = app.Point3dFromXYZ(axis.EndXmm / mmPerMaster,
                axis.EndYmm / mmPerMaster, axis.EndZmm / mmPerMaster);
            Com.LineElement line = app.CreateLineElement2(null, ref comStart, ref comEnd);
            line.Color = (int)color;
            // 容器只显示元素副本，不进入模型保存或 Undo 历史。
            return app.CreateTransientElementContainer1(line,
                Com.MsdTransientFlags.Overlay | Com.MsdTransientFlags.DontIncludeInFit,
                Com.MsdViewMask.AllViews, Com.MsdDrawingMode.Normal);
        }

        private static void DeleteAll(System.Collections.Generic.IEnumerable<Com.TransientElementContainer> containers)
        {
            foreach (Com.TransientElementContainer container in containers)
            {
                if (container == null) continue;
                try { container.Reset(); }
                catch { }
            }
        }
        internal string Describe()
        {
            return string.Format(CultureInfo.InvariantCulture, "预览线 {0} 条", _containers.Count);
        }
    }
}
