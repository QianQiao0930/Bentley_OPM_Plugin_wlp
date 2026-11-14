using System;

namespace SteelSectionProbe
{
    /// <summary>
    /// 锥形风帽尺寸族：迁移自 AutoCAD 版 ConicalVentCapFamily 的 14K117-3 表值与派生公式。
    /// 纯计算、不依赖 Bentley 或 AutoCAD；尺寸单位 mm。
    /// 规则：D1 = D + 20、D2 = 1.9·D1、D3 = 1.2·D1、H1 = 0.7·D1、H2 = 0.9·D1；
    /// 图集表列规格（200～1250）直接用表值；表间非标直径的连续尺寸按相邻两档线性插值、
    /// H 与 H5 取上邻档构造值；大于 1250 按外推规则（建模假定，非图集数据）。
    /// </summary>
    internal static class ConicalVentCapCatalog
    {
        /// <summary>连接短管外径下限（mm）。</summary>
        internal const double MinDiameterMm = 200.0;

        /// <summary>连接短管外径上限（mm）。</summary>
        internal const double MaxDiameterMm = 2500.0;

        /// <summary>板厚上限（mm）；更厚板材需重新设计连接间隙。</summary>
        internal const double MaxWallThicknessMm = 3.0;

        /// <summary>支撑组数下限。</summary>
        internal const int MinSupportCount = 3;

        /// <summary>支撑组数上限。</summary>
        internal const int MaxSupportCount = 8;

        /// <summary>图集表列直径（mm）。</summary>
        internal static readonly double[] Sizes =
        {
            200.0, 220.0, 250.0, 280.0, 320.0, 360.0, 400.0, 450.0, 500.0,
            560.0, 630.0, 700.0, 800.0, 900.0, 1000.0, 1120.0, 1250.0
        };

        /// <summary>按外推规则补充的直径（mm），非图集规格。</summary>
        internal static readonly double[] ExtendedSizes =
        {
            1320.0, 1400.0, 1500.0, 1600.0, 1700.0, 1800.0, 1900.0,
            2000.0, 2100.0, 2200.0, 2300.0, 2400.0, 2500.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的外下锥下端竖直段高度 H。</summary>
        internal static readonly double[] Heights =
        {
            110.0, 110.0, 110.0, 110.0, 110.0, 110.0, 110.0, 110.0, 110.0,
            110.0, 115.0, 115.0, 115.0, 145.0, 145.0, 145.0, 145.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的内上锥（雨帽）高度 H3。</summary>
        internal static readonly double[] InnerTopHeights =
        {
            132.0, 144.0, 162.0, 180.0, 204.0, 228.0, 252.0, 282.0, 312.0,
            348.0, 423.0, 468.0, 533.0, 598.0, 663.0, 741.0, 826.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的内下锥（雨水锥）高度 H4。</summary>
        internal static readonly double[] InnerBottomHeights =
        {
            143.0, 156.0, 175.0, 195.0, 221.0, 247.0, 273.0, 353.0, 390.0,
            435.0, 488.0, 540.0, 656.0, 736.0, 816.0, 912.0, 1016.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的连接短管高度 H5。</summary>
        internal static readonly double[] DuctHeights =
        {
            165.0, 165.0, 165.0, 165.0, 165.0, 165.0, 165.0, 165.0, 165.0,
            165.0, 190.0, 190.0, 236.0, 236.0, 236.0, 260.0, 260.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的件⑧安装站位 E。</summary>
        internal static readonly double[] InnerStations =
        {
            61.0, 67.0, 75.0, 84.0, 95.0, 106.0, 117.0, 129.0, 143.0,
            159.0, 178.0, 197.0, 224.0, 251.0, 279.0, 311.0, 347.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的件⑧外侧站位 F。</summary>
        internal static readonly double[] OuterStations =
        {
            93.0, 102.0, 114.0, 127.0, 144.0, 161.0, 178.0, 199.0, 221.0,
            246.0, 275.0, 305.0, 348.0, 391.0, 434.0, 484.0, 540.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的件⑧中间跨长 A。</summary>
        internal static readonly double[] Spans =
        {
            76.0, 84.0, 95.0, 107.0, 123.0, 138.0, 154.0, 164.0, 182.0,
            204.0, 230.0, 256.0, 286.0, 322.0, 359.0, 402.0, 449.0
        };

        /// <summary>与 <see cref="Sizes"/> 同序的件⑧内侧腿夹角 φ（°）。</summary>
        internal static readonly double[] Angles =
        {
            106.1, 106.1, 106.2, 106.1, 106.1, 106.1, 106.1,
            102.1, 102.1, 102.1, 102.1, 102.1,
            100.3, 100.3, 100.3, 100.3, 100.3
        };

        /// <summary>全部预设直径（图集表列 + 外推），供页面下拉选择。</summary>
        internal static double[] PresetDiameters
        {
            get
            {
                var result = new double[Sizes.Length + ExtendedSizes.Length];
                Sizes.CopyTo(result, 0);
                ExtendedSizes.CopyTo(result, Sizes.Length);
                return result;
            }
        }

        /// <summary>指定直径是否为图集表列规格。</summary>
        internal static bool IsCatalog(double diameter)
        {
            return Array.IndexOf(Sizes, diameter) >= 0;
        }

        /// <summary>模型实体总数：7 个壳体/接口件 + 2 个支撑 × 组数。</summary>
        internal static int PartCount(int supportCount)
        {
            return 7 + 2 * Math.Max(supportCount, 0);
        }

        /// <summary>尺寸依据说明：图集表列、表间插值或超范围外推。</summary>
        internal static string BasisText(double diameter)
        {
            if (IsCatalog(diameter))
            {
                return "图集表列尺寸";
            }

            return diameter < 1250.0 ? "非标插值尺寸" : "非标外推尺寸";
        }

        /// <summary>
        /// 按连接短管外径求全部尺寸。直径必须是 200～2500 mm 之间的有限值，
        /// 否则抛出中文 <see cref="InvalidOperationException"/>；不做静默替换。
        /// </summary>
        internal static ConicalVentCapDimensions Dimensions(double diameter)
        {
            if (double.IsNaN(diameter) || double.IsInfinity(diameter) ||
                diameter < MinDiameterMm || diameter > MaxDiameterMm)
            {
                throw new InvalidOperationException("连接短管外径 D 需在 " + MinDiameterMm.ToString("0") +
                    "～" + MaxDiameterMm.ToString("0") + " mm 之间。");
            }

            double d1 = diameter + 20.0;
            var dimensions = new ConicalVentCapDimensions
            {
                Diameter = diameter,
                D1 = d1,
                D2 = 1.9 * d1,
                D3 = 1.2 * d1,
                H1 = 0.7 * d1,
                H2 = 0.9 * d1
            };

            int index = Array.IndexOf(Sizes, diameter);
            if (index >= 0)
            {
                dimensions.H = Heights[index];
                dimensions.H3 = InnerTopHeights[index];
                dimensions.H4 = InnerBottomHeights[index];
                dimensions.H5 = DuctHeights[index];
                dimensions.E = InnerStations[index];
                dimensions.F = OuterStations[index];
                dimensions.A = Spans[index];
                dimensions.Phi = Angles[index];
                dimensions.IsCatalog = true;
                return dimensions;
            }

            if (diameter > 1250.0)
            {
                dimensions.H = 145.0;
                dimensions.H3 = Math.Round(0.65 * d1);
                dimensions.H4 = 0.8 * d1;
                dimensions.H5 = 260.0;
                dimensions.IsExtended = true;
                return dimensions;
            }

            // 表间非标直径：连续尺寸线性插值，H/H5 取上邻档构造值。
            int upper = 0;
            while (upper < Sizes.Length && Sizes[upper] <= diameter)
            {
                upper++;
            }

            int lower = upper - 1;
            double lo = Sizes[lower];
            double hi = Sizes[upper];
            double k = (diameter - lo) / (hi - lo);

            dimensions.H = Heights[upper];
            dimensions.H5 = DuctHeights[upper];
            dimensions.H3 = Lerp(InnerTopHeights[lower], InnerTopHeights[upper], k);
            dimensions.H4 = Lerp(InnerBottomHeights[lower], InnerBottomHeights[upper], k);
            dimensions.E = Lerp(InnerStations[lower], InnerStations[upper], k);
            dimensions.F = Lerp(OuterStations[lower], OuterStations[upper], k);
            dimensions.A = Lerp(Spans[lower], Spans[upper], k);
            dimensions.Phi = Lerp(Angles[lower], Angles[upper], k);
            return dimensions;
        }

        /// <summary>
        /// 输入校核：D 在 200～2500、板厚大于 0 且不超过 3、支撑组数 3～8。
        /// 通过时返回 true 且 error 为空；否则给出可显示的中文原因。
        /// </summary>
        internal static bool Validate(ConicalVentCapParameters parameters, out string error)
        {
            error = null;
            if (parameters == null)
            {
                error = "参数为空。";
                return false;
            }

            if (double.IsNaN(parameters.DiameterMm) || double.IsInfinity(parameters.DiameterMm) ||
                parameters.DiameterMm < MinDiameterMm || parameters.DiameterMm > MaxDiameterMm)
            {
                error = "连接短管外径 D 需在 " + MinDiameterMm.ToString("0") + "～" +
                        MaxDiameterMm.ToString("0") + " mm 之间。";
                return false;
            }

            if (double.IsNaN(parameters.WallThicknessMm) || double.IsInfinity(parameters.WallThicknessMm) ||
                parameters.WallThicknessMm <= 0.0 || parameters.WallThicknessMm > MaxWallThicknessMm)
            {
                error = "板厚需大于 0 且不超过 " + MaxWallThicknessMm.ToString("0") +
                        " mm；更厚板材需重新设计连接间隙。";
                return false;
            }

            if (parameters.SupportCount < MinSupportCount || parameters.SupportCount > MaxSupportCount)
            {
                error = "支撑数量需为 " + MinSupportCount + "～" + MaxSupportCount + " 的整数。";
                return false;
            }

            if (double.IsNaN(parameters.HeadingDegrees) || double.IsInfinity(parameters.HeadingDegrees))
            {
                error = "绕竖轴旋转角必须是有限数字。";
                return false;
            }

            return true;
        }

        private static double Lerp(double a, double b, double k)
        {
            return a + (b - a) * k;
        }
    }
}
