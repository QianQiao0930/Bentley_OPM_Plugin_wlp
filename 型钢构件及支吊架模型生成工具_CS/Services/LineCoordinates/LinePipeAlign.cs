using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 快速对齐的纯计算层：四个正交规整按钮（按起点/终点对齐竖直线或水平线）
    /// 与「对齐到管道」的目标坐标推演。本层不触碰 Bentley 对象；
    /// 输出只做草稿填写，写回模型仍由 LineCoordinateEditor 在确认时完成。
    /// </summary>
    internal static class LinePipeAlign
    {
        // 方向判据容差：分量相对线长的比例上限。按工程习惯取 1e-6，即每米 0.001 mm，
        // 模型里真正水平/竖直的线段都能通过，手绘歪斜的不会误判。
        private const double DirectionTolerance = 1e-6;

        internal static bool IsHorizontal(LineCoordinates coordinates)
        {
            double length = LineCoordinateCalculator.Length(coordinates);
            return Math.Abs(coordinates.End.Z - coordinates.Start.Z) <= length * DirectionTolerance;
        }

        internal static bool IsVertical(LineCoordinates coordinates)
        {
            double length = LineCoordinateCalculator.Length(coordinates);
            double max = Math.Max(Math.Abs(coordinates.End.X - coordinates.Start.X),
                Math.Abs(coordinates.End.Y - coordinates.Start.Y));
            return max <= length * DirectionTolerance;
        }

        private static bool IsHorizontalAxis(LinePipeSurvey pipe)
        {
            var length = AxisLength(pipe);
            return Math.Abs(pipe.AxisEndZ - pipe.AxisStartZ) <= length * DirectionTolerance;
        }

        private static double AxisLength(LinePipeSurvey pipe)
        {
            double dx = pipe.AxisEndX - pipe.AxisStartX, dy = pipe.AxisEndY - pipe.AxisStartY, dz = pipe.AxisEndZ - pipe.AxisStartZ;
            double maximum = Math.Max(Math.Abs(dx), Math.Max(Math.Abs(dy), Math.Abs(dz)));
            if (maximum == 0) throw new InvalidOperationException("所选管道轴线长度为 0，无法确定对齐标高。");
            return maximum * Math.Sqrt((dx / maximum) * (dx / maximum) + (dy / maximum) * (dy / maximum) + (dz / maximum) * (dz / maximum));
        }

        /// <summary>竖直规整：锚点端保持，另一端 XY 改为锚点 XY，Z 轴各自保持。</summary>
        internal static LineCoordinates AlignVertical(LineCoordinates source, bool anchorStart)
        {
            if (!ValidSource(source)) return null;
            return anchorStart
                ? new LineCoordinates(source.Start, new LineCoordinatePoint(source.Start.X, source.Start.Y, source.End.Z))
                : new LineCoordinates(new LineCoordinatePoint(source.End.X, source.End.Y, source.Start.Z), source.End);
        }

        /// <summary>水平规整：锚点端保持，另一端 Z 改为锚点 Z。</summary>
        internal static LineCoordinates AlignHorizontal(LineCoordinates source, bool anchorStart)
        {
            if (!ValidSource(source)) return null;
            return anchorStart
                ? new LineCoordinates(source.Start, new LineCoordinatePoint(source.End.X, source.End.Y, source.Start.Z))
                : new LineCoordinates(new LineCoordinatePoint(source.Start.X, source.Start.Y, source.End.Z), source.End);
        }

        private static bool ValidSource(LineCoordinates source)
        {
            if (source == null) throw new ArgumentNullException("source");
            if (LineCoordinateCalculator.Length(source) == 0)
                throw new InvalidOperationException("线段两端重合，长度为 0，无法对齐。");
            return true;
        }

        /// <summary>管道底标高（毫米）：低端轴线标高减去外表面半径；不含保温。</summary>
        internal static double PipeBottomElevationMm(LinePipeSurvey pipe)
        {
            if (pipe == null) throw new ArgumentNullException("pipe");
            if (!LineCoordinateCalculator.Finite(pipe.OutsideDiameterMm) || pipe.OutsideDiameterMm <= 0)
                throw new InvalidOperationException("未能读取所选管道的外径，无法确定管底标高。");
            if (!LineCoordinateCalculator.Finite(pipe.AxisStartZ) || !LineCoordinateCalculator.Finite(pipe.AxisEndZ)
                || !LineCoordinateCalculator.Finite(pipe.AxisStartX) || !LineCoordinateCalculator.Finite(pipe.AxisEndX)
                || !LineCoordinateCalculator.Finite(pipe.AxisStartY) || !LineCoordinateCalculator.Finite(pipe.AxisEndY))
                throw new InvalidOperationException("所选管道轴线坐标无效。");
            return Math.Min(pipe.AxisStartZ, pipe.AxisEndZ) - pipe.OutsideDiameterMm / 2.0;
        }

        /// <summary>
        /// 按点选管道推演目标坐标：
        /// 水平线 + 水平管 → 两端 Z 改为管底标高向下取整；
        /// 竖直线 → 两端 XY 改为点取位置、终点 Z 改为管底标高向下取整，起点 Z 保持；
        /// 其余方向拒绝并说明。
        /// 输出只是草稿坐标，仍须经过应用修改的完整校验与写回。
        /// </summary>
        internal static LineCoordinates ToPipe(LineCoordinates line, LinePipeSurvey pipe, bool is3d, out string summary)
        {
            summary = null;
            if (line == null) throw new ArgumentNullException("line");
            if (!is3d) throw new InvalidOperationException("二维模型只有 Z=0，不支持按管道标高对齐。");
            ValidSource(line);
            // 用户的底标高取整规则：向下取整后的整数才是写进坐标的值。
            double bottom = Math.Floor(PipeBottomElevationMm(pipe));
            if (!LineCoordinateCalculator.Finite(pipe.PickX) || !LineCoordinateCalculator.Finite(pipe.PickY)
                || !LineCoordinateCalculator.Finite(pipe.PickZ))
                throw new InvalidOperationException("点取管道的位置坐标无效，请重新点取。");
            string bottomText = bottom.ToString(CultureInfo.CurrentCulture) + " mm";
            if (IsHorizontal(line))
            {
                if (!IsHorizontalAxis(pipe))
                    throw new InvalidOperationException("水平线需要配合水平管道：所选管道不是水平管，请重新点取。");
                summary = "线段为水平线，两端 Z 已改为管底标高 " + bottomText + "，X/Y 保持。";
                return new LineCoordinates(
                    new LineCoordinatePoint(line.Start.X, line.Start.Y, bottom),
                    new LineCoordinatePoint(line.End.X, line.End.Y, bottom));
            }
            if (IsVertical(line))
            {
                summary = "竖直线两端 XY 已移到点取位置（" + FormatPoint(pipe) + "），终点 Z 已改为管底标高 " + bottomText + "，起点标高保持。";
                return new LineCoordinates(
                    new LineCoordinatePoint(pipe.PickX, pipe.PickY, line.Start.Z),
                    new LineCoordinatePoint(pipe.PickX, pipe.PickY, bottom));
            }
            throw new InvalidOperationException("当前线段既不是水平线也不是竖直线，请先按起点/终点把线规整后再对齐到管道。");
        }

        private static string FormatPoint(LinePipeSurvey pipe)
        {
            const string number = "0.###";
            return "X " + pipe.PickX.ToString(number, CultureInfo.CurrentCulture)
                + " · Y " + pipe.PickY.ToString(number, CultureInfo.CurrentCulture);
        }
    }
}
