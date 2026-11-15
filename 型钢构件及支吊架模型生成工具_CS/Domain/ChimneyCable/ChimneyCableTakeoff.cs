using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱拉索的材料用量（排气筒钢管、拉索、附件），全部由几何与规格表算出，
    /// 只读、不改计划。拉索长度按**建模出来的实际路径**累加（含两端绳眼），
    /// 不是按挂点直线距离估算。
    /// </summary>
    internal sealed class ChimneyCableMaterials
    {
        /// <summary>排气筒壁厚（mm）。</summary>
        internal double StackThicknessMm;

        /// <summary>排气筒每米钢管重量（kg/m）。</summary>
        internal double StackMassKgPerMeter;

        /// <summary>排气筒钢管总重（kg）。</summary>
        internal double StackMassKg;

        /// <summary>排气筒外表面面积（m²）。</summary>
        internal double StackSurfaceSquareMeters;

        /// <summary>单根拉索长度（m，含两端绳眼）。</summary>
        internal double StrandLengthM;

        /// <summary>拉索根数。</summary>
        internal int StrandCount;

        /// <summary>拉索总长（m）。</summary>
        internal double RopeTotalLengthM;

        /// <summary>拉索总重（kg）。</summary>
        internal double RopeMassKg;

        /// <summary>连接环板件数。</summary>
        internal int CollarCount;

        /// <summary>单件连接环板重量（kg）。</summary>
        internal double CollarMassKg;

        /// <summary>M20 U 形螺栓套数。</summary>
        internal int CollarUboltCount;

        /// <summary>M20 螺母个数。</summary>
        internal int CollarNutCount;

        /// <summary>鸡心环件数。</summary>
        internal int ThimbleCount;

        /// <summary>绳夹套数（每套含 U 形螺栓 1、螺母 2）。</summary>
        internal int ClipCount;

        /// <summary>锚墩个数。</summary>
        internal int AnchorCount;

        /// <summary>单件锚墩重量（kg）。</summary>
        internal double AnchorMassKg;

        /// <summary>地面 U 形钢筋根数。</summary>
        internal int GroundRebarCount;

        /// <summary>单根地面 U 形钢筋展开长度（m）。</summary>
        internal double GroundRebarLengthM;

        /// <summary>单根地面 U 形钢筋重量（kg）。</summary>
        internal double GroundRebarMassKg;

        /// <summary>展示用文本行（页面直接显示）。</summary>
        internal List<string> Lines = new List<string>();

        /// <summary>单行摘要（写进 Describe 与日志）。</summary>
        internal string Summary()
        {
            return string.Format(CultureInfo.CurrentCulture,
                "材料：排气筒钢管 {0:0.###} kg（{1:0.#} kg/m）、拉索 {2} 根共 {3:0.##} m / {4:0.##} kg、环板 {5} 件、M20 U 形螺栓 {6} 套、鸡心环 {7} 件、绳夹 {8} 套、锚墩 {9} 个、地面 U 形钢筋 {10} 根",
                StackMassKg, StackMassKgPerMeter, StrandCount, RopeTotalLengthM, RopeMassKg,
                CollarCount, CollarUboltCount, ThimbleCount, ClipCount, AnchorCount, GroundRebarCount);
        }
    }

    /// <summary>
    /// 材料用量计算：钢管按环形截面、拉索按建模路径、附件按规格表计数。
    /// 钢密度 7850 kg/m³；φ16 6×19+FC 钢丝绳名义重量 0.857 kg/m（GB/T 20118 近似值）。
    /// </summary>
    internal static class ChimneyCableTakeoff
    {
        /// <summary>钢密度（kg/m³）。</summary>
        internal const double SteelDensityKgPerCubicMeter = 7850.0;

        /// <summary>φ16 6×19+FC 钢丝绳名义重量（kg/m）。</summary>
        internal const double RopeKilogramPerMeter = 0.857;

        /// <summary>φ20 钢筋理论重量（kg/m）。</summary>
        internal const double RebarKilogramPerMeter = 2.47;

        internal static ChimneyCableMaterials Of(ChimneyCableSpec spec, EngineeringPlan plan)
        {
            if (spec == null)
            {
                throw new ArgumentNullException("spec");
            }

            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            var materials = new ChimneyCableMaterials();

            // ---- 排气筒钢管：环形截面（外径 D、壁厚 t）
            double thickness = spec.WallThicknessMm;
            double meanDiameter = spec.DiameterMm - thickness;
            double areaSquareMeters = Math.PI * meanDiameter * thickness / 1e6;
            double heightM = spec.HeightMm / 1000.0;
            materials.StackThicknessMm = thickness;
            materials.StackMassKgPerMeter = areaSquareMeters * SteelDensityKgPerCubicMeter;
            materials.StackMassKg = materials.StackMassKgPerMeter * heightM;
            materials.StackSurfaceSquareMeters = Math.PI * spec.DiameterMm / 1000.0 * heightM;

            // ---- 拉索：按建模路径累加，单根 = 两挂点距离 + 两端绳眼（绕鸡心环到绳尾）
            materials.StrandCount = spec.CableCount;
            materials.StrandLengthM = StrandLengthMm(plan) / 1000.0;
            materials.RopeTotalLengthM = materials.StrandLengthM * materials.StrandCount;
            materials.RopeMassKg = materials.RopeTotalLengthM * RopeKilogramPerMeter;

            // ---- 连接环板：每根拉索一件环形板（内缘 R−3、外缘 R+100、厚 20）
            materials.CollarCount = spec.CableCount;
            materials.CollarMassKg = AnnulusMassKg(
                spec.RadiusMm - ChimneyCableCatalog.CollarEmbedMm,
                spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm,
                ChimneyCableCatalog.CollarThicknessMm);

            // ---- 上端吊筋：每根拉索一套 M20 U 形螺栓 + 2 个 M20 螺母
            materials.CollarUboltCount = spec.CableCount;
            materials.CollarNutCount = spec.CableCount * 2;

            // ---- 绳眼配件：每根拉索 2 个鸡心环、2 套绳夹（每个绳眼 3 只）
            materials.ThimbleCount = spec.CableCount * 2;
            materials.ClipCount = spec.CableCount * 2 * ChimneyCableCatalog.ClipCount;

            // ---- 地面固定：锚墩 + 埋入的 ∩ 形 φ20 钢筋
            materials.AnchorCount = spec.AnchorCount;
            materials.AnchorMassKg = Math.PI * ChimneyCableCatalog.AnchorRadiusMm *
                ChimneyCableCatalog.AnchorRadiusMm * ChimneyCableCatalog.AnchorHeightMm /
                1e9 * SteelDensityKgPerCubicMeter;
            materials.GroundRebarCount = spec.AnchorCount;
            materials.GroundRebarLengthM = GroundRebarLengthMm() / 1000.0;
            materials.GroundRebarMassKg = materials.GroundRebarLengthM * RebarKilogramPerMeter;

            materials.Lines = BuildLines(materials, spec);
            return materials;
        }

        private static List<string> BuildLines(ChimneyCableMaterials materials, ChimneyCableSpec spec)
        {
            var lines = new List<string>();
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "排气筒钢管  φ{0:0.#}×{1:0.#}，高 {2:0.##} m：{3:0.#} kg/m，共 {4:0} kg；外表面积 {5:0.##} m²",
                spec.DiameterMm, materials.StackThicknessMm, spec.HeightMm / 1000.0,
                materials.StackMassKgPerMeter, materials.StackMassKg, materials.StackSurfaceSquareMeters));
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "钢丝绳      φ16（6×19+FC），单根 {0:0.##} m × {1} 根 = {2:0.##} m，共 {3:0.##} kg",
                materials.StrandLengthM, materials.StrandCount, materials.RopeTotalLengthM,
                materials.RopeMassKg));
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "连接环板    {0} 件（外径 φ{1:0}、宽 {2:0}、厚 {3:0}），单件 {4:0.#} kg，共 {5:0.#} kg",
                materials.CollarCount, 2.0 * (spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm),
                ChimneyCableCatalog.CollarWidthMm, ChimneyCableCatalog.CollarThicknessMm,
                materials.CollarMassKg, materials.CollarMassKg * materials.CollarCount));
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "上端吊筋    M20 U 形螺栓 {0} 套、M20 螺母 {1} 个",
                materials.CollarUboltCount, materials.CollarNutCount));
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "绳眼配件    鸡心环 φ38 {0} 件；绳夹 {1} 套（每套 M14 U 形螺栓 1 + 螺母 2，共螺栓 {1}、螺母 {2}）",
                materials.ThimbleCount, materials.ClipCount, materials.ClipCount * 2));
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "地面固定    锚墩 {0} 个（φ{1:0}×{2:0}，单件 {3:0.#} kg）；∩ 形 φ20 钢筋 {4} 根（单根 {5:0.##} m、{6:0.##} kg，共 {7:0.##} kg）",
                materials.AnchorCount, ChimneyCableCatalog.AnchorRadiusMm * 2.0,
                ChimneyCableCatalog.AnchorHeightMm,
                materials.AnchorMassKg, materials.GroundRebarCount, materials.GroundRebarLengthM,
                materials.GroundRebarMassKg, materials.GroundRebarMassKg * materials.GroundRebarCount));
            return lines;
        }

        /// <summary>圆环板重量（kg）：内半径、外半径、厚度均为 mm。</summary>
        private static double AnnulusMassKg(double innerRadiusMm, double outerRadiusMm, double thicknessMm)
        {
            double area = Math.PI * (outerRadiusMm * outerRadiusMm - innerRadiusMm * innerRadiusMm);
            return area * thicknessMm / 1e9 * SteelDensityKgPerCubicMeter;
        }

        /// <summary>地面 U 形钢筋展开长度（mm）：两腿直段 + 弯拱 + 两端外撇弯头与上翘。</summary>
        private static double GroundRebarLengthMm()
        {
            double half = ChimneyCableCatalog.GroundRebarLegSpacingMm / 2.0;
            double crown = ChimneyCableCatalog.GroundRebarCrownMm;
            double legBottom = ChimneyCableCatalog.GroundRebarLegBottomMm;
            double bend = ChimneyCableCatalog.GroundRebarHookRadiusMm;
            double run = ChimneyCableCatalog.GroundRebarHookRunMm;
            double curl = ChimneyCableCatalog.GroundRebarHookCurlRadiusMm;
            double up = ChimneyCableCatalog.GroundRebarHookCurlUpMm;

            double legs = 2.0 * ((crown - half) - legBottom);
            double arch = Math.PI * half;
            double hooks = 2.0 * (0.5 * Math.PI * bend + run + 0.5 * Math.PI * curl + up);
            return legs + arch + hooks;
        }

        /// <summary>
        /// 单根拉索长度（mm）：两绳眼顶点之间的距离 + 两端“顶点→绳尾”的路径长度。
        /// 直接读建模出来的绳圈路径，绳眼绕鸡心环的那一段不会漏算。
        /// </summary>
        private static double StrandLengthMm(EngineeringPlan plan)
        {
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("拉索 ", StringComparison.Ordinal) != 0 ||
                    body.Name.IndexOf("绳眼", StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                EngineeringShape cylinder = null;
                var eyes = new List<EngineeringShape>();
                foreach (EngineeringShape shape in body.Add)
                {
                    if (shape.Kind == EngineeringShapeKind.Cone)
                    {
                        cylinder = shape;
                    }
                    else if (shape.Kind == EngineeringShapeKind.Loft ||
                             shape.Kind == EngineeringShapeKind.Sweep)
                    {
                        eyes.Add(shape);
                    }
                }

                if (cylinder == null)
                {
                    continue;
                }

                if (eyes.Count == 0)
                {
                    // 短索退化成一个圆柱，没有绳眼。
                    return Distance(cylinder.Start, cylinder.End);
                }

                double best = 0.0;
                for (int index = 0; index < eyes.Count; index++)
                {
                    for (int other = index + 1; other < eyes.Count; other++)
                    {
                        double length = EyeLengthMm(eyes[index], eyes[other]);
                        if (length > best)
                        {
                            best = length;
                        }
                    }
                }

                if (best > 0.0)
                {
                    return best;
                }
            }

            return 0.0;
        }

        /// <summary>两只绳眼之间的拉索长度：两顶点距离 + 两个“顶点→绳尾”的路径长度。</summary>
        private static double EyeLengthMm(EngineeringShape first, EngineeringShape second)
        {
            int crownFirst;
            int crownSecond;
            double tailFirst = CrownToTailMm(first, out crownFirst);
            double tailSecond = CrownToTailMm(second, out crownSecond);
            return Distance(first.Points[crownFirst], second.Points[crownSecond]) + tailFirst + tailSecond;
        }

        /// <summary>
        /// 从绳眼顶点到绳尾末端沿路径的长度（mm）：顶点取“离路径末点最远”的路径点，
        /// 因为绳尾末端与顶点正好在绳圈两侧。
        /// </summary>
        private static double CrownToTailMm(EngineeringShape eye, out int crown)
        {
            crown = 0;
            int last = eye.Points.Length - 1;
            double farthest = -1.0;
            for (int index = 0; index < eye.Points.Length; index++)
            {
                double distance = Distance(eye.Points[index], eye.Points[last]);
                if (distance > farthest)
                {
                    farthest = distance;
                    crown = index;
                }
            }

            double length = 0.0;
            for (int index = crown; index < last; index++)
            {
                length += SegmentLengthMm(eye, index);
            }

            return length;
        }

        private static double SegmentLengthMm(EngineeringShape shape, int index)
        {
            EngineeringPoint start = shape.Points[index];
            EngineeringPoint end = shape.Points[index + 1];
            EngineeringPoint? middle = shape.ArcMiddles == null || index >= shape.ArcMiddles.Length
                ? null
                : shape.ArcMiddles[index];
            if (!middle.HasValue)
            {
                return Distance(start, end);
            }

            // 三点定圆：用外接圆半径与弦长求真圆弧长度。
            double chord = Distance(start, end);
            double sideA = Distance(start, middle.Value);
            double sideB = Distance(middle.Value, end);
            double area2 = CrossMagnitude(Subtract(start, middle.Value), Subtract(end, middle.Value));
            if (chord < 1e-9 || sideA < 1e-9 || sideB < 1e-9 || area2 < 1e-9)
            {
                return chord;
            }

            double radius = sideA * sideB * chord / (2.0 * area2);
            double ratio = chord / (2.0 * radius);
            if (ratio >= 1.0)
            {
                return chord;
            }

            return radius * 2.0 * Math.Asin(ratio);
        }

        private static double CrossMagnitude(EngineeringPoint first, EngineeringPoint second)
        {
            double x = first.Y * second.Z - first.Z * second.Y;
            double y = first.Z * second.X - first.X * second.Z;
            double z = first.X * second.Y - first.Y * second.X;
            return Math.Sqrt(x * x + y * y + z * z);
        }

        private static EngineeringPoint Subtract(EngineeringPoint first, EngineeringPoint second)
        {
            return new EngineeringPoint(
                first.X - second.X, first.Y - second.Y, first.Z - second.Z);
        }

        private static double Distance(EngineeringPoint first, EngineeringPoint second)
        {
            double x = first.X - second.X;
            double y = first.Y - second.Y;
            double z = first.Z - second.Z;
            return Math.Sqrt(x * x + y * y + z * z);
        }
    }
}
