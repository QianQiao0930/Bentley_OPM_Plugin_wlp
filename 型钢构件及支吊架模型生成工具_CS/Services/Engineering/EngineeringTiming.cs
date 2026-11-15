using System;
using System.Diagnostics;

namespace SteelSectionProbe
{
    /// <summary>建模耗时统计的四个阶段。</summary>
    internal enum EngineeringTimingPhase
    {
        Shape,
        Union,
        Cut,
        Element
    }

    /// <summary>
    /// 建模耗时统计：按阶段累计（成形 / 并集 / 差集 / 封装为图元）与总数，
    /// 由 <see cref="EngineeringSolidFactory.Build"/> 每轮开始清零，
    /// 页面在状态栏里显示“建模用时 …（成形 … 并集 … 差集 … 封装 …）”，
    /// 便于判断慢在内核布尔还是形状构造。
    /// </summary>
    internal static class EngineeringTiming
    {
        private static readonly double[] Milliseconds = new double[4];

        internal static double TotalMilliseconds { get; private set; }

        internal static int BodyCount { get; private set; }

        internal static int ShapeCount { get; set; }

        internal static void Reset()
        {
            for (int index = 0; index < Milliseconds.Length; index++)
            {
                Milliseconds[index] = 0.0;
            }

            TotalMilliseconds = 0.0;
            BodyCount = 0;
            ShapeCount = 0;
        }

        internal static void Add(EngineeringTimingPhase phase, double milliseconds)
        {
            Milliseconds[(int)phase] += milliseconds;
        }

        internal static void AddBody()
        {
            BodyCount++;
        }

        internal static void SetTotal(double milliseconds)
        {
            TotalMilliseconds = milliseconds;
        }

        internal static double ShapeMilliseconds
        {
            get { return Milliseconds[(int)EngineeringTimingPhase.Shape]; }
        }

        internal static double UnionMilliseconds
        {
            get { return Milliseconds[(int)EngineeringTimingPhase.Union]; }
        }

        internal static double CutMilliseconds
        {
            get { return Milliseconds[(int)EngineeringTimingPhase.Cut]; }
        }

        internal static double ElementMilliseconds
        {
            get { return Milliseconds[(int)EngineeringTimingPhase.Element]; }
        }

        /// <summary>一行中文摘要，可直接显示在状态栏。</summary>
        internal static string Report()
        {
            return "建模用时 " + Format(TotalMilliseconds) +
                "（成形 " + Format(ShapeMilliseconds) +
                "、并集 " + Format(UnionMilliseconds) +
                "、差集 " + Format(CutMilliseconds) +
                "、封装 " + Format(ElementMilliseconds) +
                "；" + BodyCount + " 块 " + ShapeCount + " 形状）";
        }

        internal static string Format(double milliseconds)
        {
            if (milliseconds >= 1000.0)
            {
                return (milliseconds / 1000.0).ToString("0.00") + " s";
            }

            return milliseconds.ToString("0") + " ms";
        }

        /// <summary>计时执行一次内核调用（异常也会计入耗时）。</summary>
        internal static T Measure<T>(EngineeringTimingPhase phase, Func<T> action)
        {
            var watch = Stopwatch.StartNew();
            try
            {
                return action();
            }
            finally
            {
                watch.Stop();
                Add(phase, watch.Elapsed.TotalMilliseconds);
            }
        }

        /// <summary>
        /// 计时执行一段内部有 ref 参数的内核调用：把调用包成 lambda 由调用方传入，
        /// 这里只负责掐表，避免在工厂里到处写 try/finally。
        /// </summary>
        internal static void MeasureVoid(EngineeringTimingPhase phase, Action action)
        {
            var watch = Stopwatch.StartNew();
            try
            {
                action();
            }
            finally
            {
                watch.Stop();
                Add(phase, watch.Elapsed.TotalMilliseconds);
            }
        }
    }
}
