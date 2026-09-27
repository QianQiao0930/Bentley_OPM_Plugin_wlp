using System;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Check(bool condition, string name)
        {
            if (!condition) throw new Exception(name);
        }

        private static void Main()
        {
            Check(ComponentPropertyCalculator.LengthScale(2.5, 2500, "auto") == 1000, "米标定");
            Check(ComponentPropertyCalculator.LengthScale(2500, 2500, "auto") == 1, "毫米标定");
            Check(ComponentPropertyCalculator.LengthScale(2500, 2500, "m") == 1000, "手动覆盖");
            Check(ComponentPropertyCalculator.NearestDn(168.3) == 150, "外径反查");
            Check(ComponentPropertyCalculator.NearestDn(1700) == null, "非标准外径");
            Check(ComponentPropertyCalculator.Number(new System.Collections.Generic.Dictionary<string, string> { { "LENGTH", "NaN" } }, "LENGTH") == null, "非法数值");
            var snapshot = new ComponentSnapshot { StartX = 0, StartY = 0, StartZ = 0,
                EndX = 1000, EndY = 0, EndZ = 100 };
            Check(ComponentPropertyCalculator.Orientation(snapshot).StartsWith("倾斜"), "倾斜走向");
            snapshot.EndZ = 0;
            Check(ComponentPropertyCalculator.Orientation(snapshot) == "水平", "水平走向");
            Console.WriteLine("构件特性纯计算检查通过。");
        }
    }
}
