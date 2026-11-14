using System;

namespace SteelSectionProbe
{
    /// <summary>
    /// 花篮螺栓规格表：迁移自 AutoCAD 版 TurnbuckleSpec.Nominal 的螺母/卸扣表与派生公式。
    /// 纯计算，不依赖 Bentley；尺寸单位 mm。
    /// </summary>
    internal static class TurnbuckleCatalog
    {
        internal static readonly int[] Sizes =
        {
            10, 12, 16, 20, 24, 30, 36, 42, 48, 56, 64, 72, 80, 90, 100, 110
        };

        // size: H, h, L, B
        private static readonly double[][] NutTable =
        {
            new[] { 90.0, 50.0, 140.0, 33.0 },
            new[] { 100.0, 50.0, 150.0, 33.0 },
            new[] { 130.0, 75.0, 210.0, 43.0 },
            new[] { 150.0, 75.0, 220.0, 52.0 },
            new[] { 150.0, 75.0, 230.0, 62.0 },
            new[] { 150.0, 75.0, 250.0, 77.0 },
            new[] { 150.0, 75.0, 260.0, 91.0 },
            new[] { 170.0, 85.0, 300.0, 107.0 },
            new[] { 170.0, 85.0, 320.0, 123.0 },
            new[] { 200.0, 100.0, 340.0, 110.0 },
            new[] { 200.0, 100.0, 350.0, 125.0 },
            new[] { 200.0, 100.0, 360.0, 140.0 },
            new[] { 200.0, 100.0, 400.0, 160.0 },
            new[] { 200.0, 100.0, 420.0, 195.0 },
            new[] { 200.0, 100.0, 440.0, 220.0 },
            new[] { 200.0, 100.0, 460.0, 245.0 }
        };

        // size: pin d, H, h, B
        private static readonly double[][] ClevisTable =
        {
            new[] { 12.0, 50.0, 13.0, 35.0 },
            new[] { 16.0, 55.0, 15.0, 38.0 },
            new[] { 20.0, 60.0, 20.0, 44.0 },
            new[] { 24.0, 65.0, 25.0, 61.0 },
            new[] { 30.0, 80.0, 30.0, 70.0 },
            new[] { 36.0, 95.0, 35.0, 85.0 },
            new[] { 42.0, 110.0, 40.0, 93.0 },
            new[] { 48.0, 120.0, 50.0, 114.0 },
            new[] { 56.0, 130.0, 60.0, 136.0 },
            new[] { 64.0, 150.0, 65.0, 154.0 },
            new[] { 72.0, 150.0, 70.0, 160.0 },
            new[] { 80.0, 160.0, 80.0, 152.0 },
            new[] { 90.0, 170.0, 90.0, 166.0 },
            new[] { 100.0, 180.0, 100.0, 186.0 },
            new[] { 110.0, 200.0, 110.0, 206.0 },
            new[] { 125.0, 220.0, 120.0, 226.0 }
        };

        /// <summary>按规格与装配参数求全部尺寸；不支持的规格抛出异常。</summary>
        internal static TurnbuckleSpec Resolve(TurnbuckleParameters parameters)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            int index = Array.IndexOf(Sizes, parameters.Size);
            if (index < 0)
            {
                throw new InvalidOperationException("规格只支持 " + string.Join("、", Sizes) + "。");
            }

            double[] nut = NutTable[index];
            double[] clevis = ClevisTable[index];
            var spec = new TurnbuckleSpec
            {
                Size = parameters.Size,
                D = parameters.Size,
                H = nut[0],
                h = nut[1],
                L = nut[2],
                B = nut[3],
                Thickness = 1.5 * parameters.Size,
                Bore = parameters.Size,
                RoundedStyle = parameters.Size <= 48,
                EndGap = parameters.EndGapMm,
                StudProtrusion = parameters.StudProtrusionMm,
                PinDiameter = clevis[0],
                ClevisH = clevis[1],
                Clevish = clevis[2],
                ClevisB = clevis[3]
            };

            spec.Rail = Math.Min(0.4 * spec.D, 0.19 * spec.B);
            spec.BossWidth = Math.Min(1.6 * spec.D, spec.B - spec.Rail);
            spec.HexAcrossFlats = spec.BossWidth;
            spec.Corner = spec.Rail;
            spec.OpeningRadius = Math.Min(0.3 * spec.D, (spec.B - 2.0 * spec.Rail) / 3.0);

            spec.Leg = 0.4 * spec.D;
            spec.ClevisThickness = 1.2 * spec.PinDiameter;
            spec.HeadHeight = 0.9 * spec.D;
            spec.TopWidth = 0.7 * spec.ClevisB;
            spec.InsideRadius = Math.Min(0.4 * spec.Leg, 4.0);
            spec.PinClearance = Math.Max(0.2, 0.02 * spec.D);
            spec.WasherThickness = 0.1 * spec.PinDiameter;
            spec.WasherOd = 1.5 * spec.PinDiameter;
            spec.PinOverhang = 0.5 * spec.PinDiameter;
            spec.ClevisFullShoulder = spec.D >= 56.0;
            spec.StudExtension = spec.EndGap + spec.HeadHeight + spec.StudProtrusion;
            return spec;
        }

        /// <summary>输入校核，返回中文原因；通过时 error 为空。</summary>
        internal static bool Validate(TurnbuckleParameters parameters, out string error)
        {
            error = null;
            if (parameters == null)
            {
                error = "参数为空。";
                return false;
            }

            TurnbuckleSpec spec;
            try
            {
                spec = Resolve(parameters);
            }
            catch (InvalidOperationException exception)
            {
                error = exception.Message;
                return false;
            }

            if (double.IsNaN(parameters.EndGapMm) || double.IsInfinity(parameters.EndGapMm) ||
                parameters.EndGapMm < 0.0 || parameters.EndGapMm > 500.0)
            {
                error = "端部间隙需在 0～500 mm 之间。";
                return false;
            }

            if (double.IsNaN(parameters.StudProtrusionMm) || double.IsInfinity(parameters.StudProtrusionMm) ||
                parameters.StudProtrusionMm < 0.0 ||
                parameters.StudProtrusionMm >= spec.ClevisH - spec.PinDiameter / 2.0)
            {
                error = "拉杆伸入叉口长度应在 0 到 卸扣 H − 销轴半径 之间（不能碰销轴）。";
                return false;
            }

            if (!(0.0 < spec.h && spec.h < spec.H && spec.H < spec.L && spec.B > 2.0 * spec.Rail &&
                  spec.Rail > 0.0))
            {
                error = "花篮螺母长度/边梁参数不匹配。";
                return false;
            }

            if (!(spec.Thickness > spec.Bore && spec.Bore > 0.0 && spec.BossWidth > spec.Bore &&
                  spec.Bore < spec.B - 2.0 * spec.Rail))
            {
                error = "花篮螺母壁厚/内孔/端部六角尺寸不匹配。";
                return false;
            }

            if (spec.HexAcrossFlats <= spec.Bore ||
                2.0 * spec.HexAcrossFlats / Math.Sqrt(3.0) > spec.B)
            {
                error = "端部六角对边需大于内孔并放得进框宽。";
                return false;
            }

            if (spec.BodyLength >= spec.L)
            {
                error = "螺母总长 L 必须大于开口长 H + 2×边梁。";
                return false;
            }

            if (!(spec.ClevisB - 2.0 * spec.Leg > spec.D && spec.HeadHeight > 0.0 &&
                  spec.Clevish > spec.PinDiameter / 2.0 &&
                  spec.ClevisThickness > spec.PinDiameter + spec.PinClearance &&
                  spec.TopWidth > spec.D && spec.ClevisB > spec.TopWidth))
            {
                error = "卸扣叉口/头部/销轴尺寸不匹配。";
                return false;
            }

            return true;
        }
    }
}
