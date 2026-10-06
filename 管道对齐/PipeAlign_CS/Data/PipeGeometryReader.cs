using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace PipeAlign
{
    /// <summary>几何读取结果。</summary>
    internal sealed class PipeGeometryResult
    {
        /// <summary>中心线（mm）；取不到时为 <c>null</c>。</summary>
        internal PipeAxis Axis { get; set; }

        /// <summary>中心线来源（中文，用于提示与 Debug）。</summary>
        internal string Source { get; set; }

        /// <summary>需要提示用户的说明（几何只能近似时），没有则为 <c>null</c>。</summary>
        internal string Warning { get; set; }

        /// <summary>包围盒范围的最长边（mm），只在走近似通道时有值，用于提示可靠性。</summary>
        internal double? RangeLongestMm { get; set; }
    }

    /// <summary>
    /// 读管道中心线（开发指南 §9、§36）。
    /// <para>
    /// 取值顺序（每一级都产出**毫米**数值，单位换算只在这里做一次）：
    /// </para>
    /// <list type="number">
    /// <item><description>元素曲线路径（<c>CurvePathQuery</c>）—— 管轴就是一条开放直线时最准；</description></item>
    /// <item><description>显示几何（<c>ElementGraphicsOutput</c>）—— 实体管道没有曲线路径时的主通道；</description></item>
    /// <item><description>活动模型的 COM 链（<c>AsChainableElement</c>）—— 与仓库既有插件一致的兜底；</description></item>
    /// <item><description>包围盒最长边近似 —— 最后手段，**必定带警告**，因为它不是工程意义上的中心线（指南 §8.1、§36）。</description></item>
    /// </list>
    /// <para>
    /// ⚠️ 显示几何回调里拿到的 <c>CurveVector</c> 只在回调期间有效，存下来再读就是野指针
    /// （实测会让 OPM 直接崩溃），所以坐标必须在回调内部就取成 <c>double</c>。
    /// </para>
    /// </summary>
    internal static class PipeGeometryReader
    {
        internal static PipeGeometryResult Read(Element element, DgnModel model, double uorPerMm)
        {
            PipeGeometryResult result = new PipeGeometryResult();
            if (element == null || uorPerMm <= 0.0) return result;

            // ---- 1) 元素曲线路径 ----
            try
            {
                CurveVector curve = CurvePathQuery.ElementToCurveVector(element);
                if (curve != null)
                {
                    DPoint3d start, end;
                    if (curve.GetStartEnd(out start, out end)
                        && IsUsable(end.X - start.X, end.Y - start.Y, end.Z - start.Z))
                    {
                        result.Axis = ToAxis(start, end, uorPerMm);
                        result.Source = "元素曲线路径";
                        return result;
                    }
                }
            }
            catch
            {
                // 曲线查询失败不是错误：OpenPlant 的实体管道本来就可能没有曲线路径。
            }

            // ---- 2) 显示几何 ----
            DisplayGeometry display = TryReadDisplayGeometry(element);
            if (display != null && display.HasAxis)
            {
                result.Axis = ToAxis(
                    new DPoint3d(display.AxisStartX, display.AxisStartY, display.AxisStartZ),
                    new DPoint3d(display.AxisEndX, display.AxisEndY, display.AxisEndZ),
                    uorPerMm);
                result.Source = "显示几何（管轴）";
                return result;
            }

            // ---- 3) 活动模型的 COM 链 ----
            try
            {
                if (!LocatedElement.IsReference(element.DgnModelRef))
                {
                    double factor = DgnUnitServiceFactory.MillimetersPerMasterUnit(model);
                    if (factor > 0.0)
                    {
                        var com = Bentley.MstnPlatformNET.InteropServices.Utilities
                            .ComApp.ActiveModelReference.GetElementByID64(checked((long)(ulong)element.ElementId));
                        if (com != null)
                        {
                            var chain = com.AsChainableElement();
                            if (chain != null && chain.Length > 0)
                            {
                                var start = chain.StartPoint;
                                var end = chain.EndPoint;
                                if (IsUsable(end.X - start.X, end.Y - start.Y, end.Z - start.Z))
                                {
                                    result.Axis = new PipeAxis(
                                        start.X * factor, start.Y * factor, start.Z * factor,
                                        end.X * factor, end.Y * factor, end.Z * factor);
                                    result.Source = "COM 链";
                                    return result;
                                }
                            }
                        }
                    }
                }
            }
            catch
            {
            }

            // ---- 4) 包围盒近似（最后手段，必须带警告）----
            if (display != null && display.HasRange)
            {
                PipeAxis diagnosticAxis = ApproximateFromRange(display, uorPerMm);
                if (diagnosticAxis != null)
                {
                    result.Source = "包围盒近似";
                    result.RangeLongestMm = LongestHorizontalSpanMm(display, uorPerMm);
                    result.Warning = "该管只能读取包围盒近似，不能确认真实中心线，未用于正式对齐。";
                }
                return result;
            }

            result.Warning = "该管取不到中心线，也未取到显示几何，无法参与对齐。";
            return result;
        }

        private static bool IsUsable(double dx, double dy, double dz)
        {
            return dx * dx + dy * dy + dz * dz > 1.0e-6;
        }

        private static PipeAxis ToAxis(DPoint3d start, DPoint3d end, double uorPerMm)
        {
            // .NET 几何坐标是 UOR，除以"每毫米多少 UOR"即得毫米。
            return new PipeAxis(start.X / uorPerMm, start.Y / uorPerMm, start.Z / uorPerMm,
                end.X / uorPerMm, end.Y / uorPerMm, end.Z / uorPerMm);
        }

        /// <summary>
        /// 由包围盒构造一条水平近似管轴：沿水平方向最长的那条边展开，标高取包围盒中心的 Z。
        /// 对水平圆管而言包围盒中心的 Z 就是管中心标高，所以这条近似在常见情况下是对的；
        /// 但自定义表示方式会改变范围，因此调用方**必须**把警告带给用户。
        /// </summary>
        private static PipeAxis ApproximateFromRange(DisplayGeometry display, double uorPerMm)
        {
            DRange3d range = display.Range;
            double spanX = Math.Abs(range.High.X - range.Low.X);
            double spanY = Math.Abs(range.High.Y - range.Low.Y);
            if (spanX <= 0.0 && spanY <= 0.0) return null;

            double centerX = (range.Low.X + range.High.X) / 2.0;
            double centerY = (range.Low.Y + range.High.Y) / 2.0;
            double centerZ = (range.Low.Z + range.High.Z) / 2.0;

            double startX = centerX, startY = centerY, endX = centerX, endY = centerY;
            if (spanX >= spanY)
            {
                startX = range.Low.X;
                endX = range.High.X;
            }
            else
            {
                startY = range.Low.Y;
                endY = range.High.Y;
            }

            return new PipeAxis(startX / uorPerMm, startY / uorPerMm, centerZ / uorPerMm,
                endX / uorPerMm, endY / uorPerMm, centerZ / uorPerMm);
        }

        private static double LongestHorizontalSpanMm(DisplayGeometry display, double uorPerMm)
        {
            DRange3d range = display.Range;
            double spanX = Math.Abs(range.High.X - range.Low.X);
            double spanY = Math.Abs(range.High.Y - range.Low.Y);
            return Math.Max(spanX, spanY) / uorPerMm;
        }

        private static DisplayGeometry TryReadDisplayGeometry(Element element)
        {
            try
            {
                DisplayGeometry geometry = new DisplayGeometry();
                ElementGraphicsOutput.Process(element, geometry);
                return geometry;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 收集显示几何：累加包围盒，并记下"第一条端点有效的曲线"的两个端点。
        /// <para>
        /// **不按 <c>isClosed</c> 过滤** —— 实测 OpenPlant 管道在显示几何通道下给的
        /// 就是一条管轴直线（包围盒 = 长 × 0 × 0，中心标高正好是管道中心），
        /// 但它的 BoundaryType / isClosed 并不可靠，一律过滤会把管轴丢掉。
        /// </para>
        /// <para>同时只保留 <c>double</c>：回调里的 Bentley 对象出了回调即失效。</para>
        /// </summary>
        private sealed class DisplayGeometry : ElementGraphicsProcessor
        {
            internal DRange3d Range = DRange3d.NullRange;
            internal bool HasRange;
            internal bool HasAxis;
            internal double AxisStartX, AxisStartY, AxisStartZ;
            internal double AxisEndX, AxisEndY, AxisEndZ;

            public override BentleyStatus ProcessCurveVector(CurveVector curves, bool isClosed)
            {
                if (curves == null) return BentleyStatus.Success;

                DRange3d range;
                if (curves.GetRange(out range))
                {
                    Range.Extend(range.Low);
                    Range.Extend(range.High);
                    HasRange = true;
                }

                if (!HasAxis)
                {
                    DPoint3d start, end;
                    if (curves.GetStartEnd(out start, out end))
                    {
                        double dx = end.X - start.X;
                        double dy = end.Y - start.Y;
                        double dz = end.Z - start.Z;
                        if (dx * dx + dy * dy + dz * dz > 1.0e-12)
                        {
                            HasAxis = true;
                            AxisStartX = start.X;
                            AxisStartY = start.Y;
                            AxisStartZ = start.Z;
                            AxisEndX = end.X;
                            AxisEndY = end.Y;
                            AxisEndZ = end.Z;
                        }
                    }
                }

                return BentleyStatus.Success;
            }
        }
    }
}
