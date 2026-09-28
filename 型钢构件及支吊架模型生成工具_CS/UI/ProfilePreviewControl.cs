using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;
using SteelSectionProbe;

namespace SteelSectionProbe.UI
{
    public sealed class ProfilePreviewControl : FrameworkElement
    {
        private ModeData mode;

        internal ModeData Mode
        {
            get { return mode; }
            set { mode = value; InvalidateVisual(); }
        }

        protected override void OnRender(DrawingContext drawingContext)
        {
            base.OnRender(drawingContext);
            double width = ActualWidth;
            double height = ActualHeight;
            if (width <= 1 || height <= 1) return;

            drawingContext.DrawRoundedRectangle(
                new SolidColorBrush(Color.FromRgb(244, 247, 251)),
                new Pen(new SolidColorBrush(Color.FromRgb(227, 233, 241)), 1),
                new Rect(0.5, 0.5, width - 1, height - 1), 4, 4);

            if (mode == null || mode.Segments == null || mode.Segments.Length == 0) return;
            List<Point> outline = BuildOutline(mode);
            if (outline.Count < 3) return;

            double minX = double.MaxValue, minY = double.MaxValue;
            double maxX = double.MinValue, maxY = double.MinValue;
            foreach (Point point in outline)
            {
                minX = Math.Min(minX, point.X);
                maxX = Math.Max(maxX, point.X);
                minY = Math.Min(minY, point.Y);
                maxY = Math.Max(maxY, point.Y);
            }

            double dataWidth = Math.Max(0.001, maxX - minX);
            double dataHeight = Math.Max(0.001, maxY - minY);
            const double inset = 14;
            double availableWidth = Math.Max(1, width - inset * 2);
            double availableHeight = Math.Max(1, height - inset * 2);
            double scale = Math.Min(availableWidth / dataWidth, availableHeight / dataHeight) * 0.88;
            double centerX = (minX + maxX) * 0.5;
            double centerY = (minY + maxY) * 0.5;

            var geometry = new StreamGeometry();
            using (StreamGeometryContext context = geometry.Open())
            {
                Point first = ToScreen(outline[0], centerX, centerY, scale, width, height);
                context.BeginFigure(first, true, true);
                for (int i = 1; i < outline.Count; i++)
                    context.LineTo(ToScreen(outline[i], centerX, centerY, scale, width, height), true, false);
            }
            geometry.Freeze();

            drawingContext.DrawGeometry(
                new SolidColorBrush(Color.FromArgb(38, 224, 168, 0)),
                new Pen(new SolidColorBrush(Color.FromRgb(55, 73, 94)), 1.6),
                geometry);
        }

        private static Point ToScreen(Point point, double centerX, double centerY,
            double scale, double width, double height)
        {
            return new Point(
                width * 0.5 + (point.X - centerX) * scale,
                height * 0.5 - (point.Y - centerY) * scale);
        }

        private static List<Point> BuildOutline(ModeData currentMode)
        {
            var result = new List<Point>();
            foreach (SegmentData segment in currentMode.Segments)
            {
                if (!segment.IsArc)
                {
                    AddPoint(result, segment.X0, segment.Y0);
                    AddPoint(result, segment.X1, segment.Y1);
                    continue;
                }

                double cx, cy, radius, startAngle, sweep;
                if (!TryCircle(segment, out cx, out cy, out radius, out startAngle, out sweep))
                {
                    AddPoint(result, segment.X0, segment.Y0);
                    AddPoint(result, segment.X1, segment.Y1);
                    continue;
                }
                const int steps = 18;
                for (int i = 0; i <= steps; i++)
                {
                    double angle = startAngle + sweep * i / steps;
                    AddPoint(result, cx + radius * Math.Cos(angle), cy + radius * Math.Sin(angle));
                }
            }
            return result;
        }

        private static void AddPoint(List<Point> points, double x, double y)
        {
            var point = new Point(x, y);
            if (points.Count == 0 || (points[points.Count - 1] - point).LengthSquared > 0.000001)
                points.Add(point);
        }

        private static bool TryCircle(SegmentData segment, out double cx, out double cy,
            out double radius, out double startAngle, out double sweep)
        {
            double x0 = segment.X0, y0 = segment.Y0;
            double xm = segment.Xm, ym = segment.Ym;
            double x1 = segment.X1, y1 = segment.Y1;
            double d = 2.0 * (x0 * (ym - y1) + xm * (y1 - y0) + x1 * (y0 - ym));
            if (Math.Abs(d) < 1e-10)
            {
                cx = cy = radius = startAngle = sweep = 0;
                return false;
            }
            double q0 = x0 * x0 + y0 * y0;
            double qm = xm * xm + ym * ym;
            double q1 = x1 * x1 + y1 * y1;
            cx = (q0 * (ym - y1) + qm * (y1 - y0) + q1 * (y0 - ym)) / d;
            cy = (q0 * (x1 - xm) + qm * (x0 - x1) + q1 * (xm - x0)) / d;
            radius = Math.Sqrt((x0 - cx) * (x0 - cx) + (y0 - cy) * (y0 - cy));
            startAngle = Math.Atan2(y0 - cy, x0 - cx);
            double middleAngle = Math.Atan2(ym - cy, xm - cx);
            double endAngle = Math.Atan2(y1 - cy, x1 - cx);
            double ccwEnd = PositiveAngle(endAngle - startAngle);
            double ccwMiddle = PositiveAngle(middleAngle - startAngle);
            sweep = ccwMiddle <= ccwEnd + 1e-9 ? ccwEnd : ccwEnd - Math.PI * 2.0;
            return true;
        }

        private static double PositiveAngle(double angle)
        {
            double full = Math.PI * 2.0;
            angle %= full;
            return angle < 0 ? angle + full : angle;
        }
    }
}
