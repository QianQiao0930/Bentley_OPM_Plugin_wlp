using System;
using System.Diagnostics;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>统一计量一次写入操作，并按 100 ms 边界选择显示单位。</summary>
    internal static class WriteDuration
    {
        internal static string Measure(Action write)
        {
            if (write == null) throw new ArgumentNullException("write");
            var watch = Stopwatch.StartNew();
            write();
            watch.Stop();
            return Format(watch.Elapsed.TotalMilliseconds);
        }

        internal static T Measure<T>(Func<T> write, out string elapsed)
        {
            if (write == null) throw new ArgumentNullException("write");
            var watch = Stopwatch.StartNew();
            T result = write();
            watch.Stop();
            elapsed = Format(watch.Elapsed.TotalMilliseconds);
            return result;
        }

        internal static string Format(double milliseconds)
        {
            if (double.IsNaN(milliseconds) || double.IsInfinity(milliseconds) || milliseconds < 0)
                throw new ArgumentOutOfRangeException("milliseconds");
            if (milliseconds >= 100)
                return (milliseconds / 1000).ToString("0.###", CultureInfo.InvariantCulture) + " s";
            if (milliseconds > 0 && milliseconds < 0.001)
                return "<0.001 ms";
            return milliseconds.ToString("0.###", CultureInfo.InvariantCulture) + " ms";
        }
    }
}
