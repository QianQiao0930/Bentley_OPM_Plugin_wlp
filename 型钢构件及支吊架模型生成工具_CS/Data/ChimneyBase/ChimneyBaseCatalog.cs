using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱底座的规则表与输入校核：迁移自 AutoCAD 版 <c>ChimneyBaseOptions.ResolveDiameters</c>、
    /// <c>ChimneyBaseGeometry</c> 的角度/轮廓公式与 <c>ChimneyBaseOptions.Validate</c>。
    /// 纯计算，不依赖 Bentley；角度单位为度，长度单位为 mm。
    /// </summary>
    internal static class ChimneyBaseCatalog
    {
        /// <summary>解析实际使用的三个直径：D2、D3 为 0 时按 D1 推导。</summary>
        internal static void ResolveDiameters(
            ChimneyBaseParameters parameters, out double exhaust, out double boltCircle, out double embeddedPlate)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            exhaust = parameters.ExhaustDiameterMm;
            boltCircle = parameters.BoltCircleDiameterMm > 0.0
                ? parameters.BoltCircleDiameterMm
                : parameters.ExhaustDiameterMm + ChimneyBaseConstants.AutoBoltCircleMargin;
            embeddedPlate = parameters.EmbeddedPlateDiameterMm > 0.0
                ? parameters.EmbeddedPlateDiameterMm
                : parameters.ExhaustDiameterMm + ChimneyBaseConstants.AutoPlateDiameterMargin;
        }

        /// <summary>混凝土基础边长：宽度 &gt; 0 时取用户值，否则取 D3 + 200。</summary>
        internal static double FoundationSide(ChimneyBaseParameters parameters, double embeddedPlateDiameter)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            return parameters.FoundationWidthMm > 0.0
                ? parameters.FoundationWidthMm
                : embeddedPlateDiameter + ChimneyBaseConstants.FoundationMargin;
        }

        /// <summary>
        /// 第 index 颗地脚螺栓的角度（°）：自 +Y（90°）起沿逆时针均布，
        /// 保证任意螺栓数（含奇数）俯视图都关于竖向中心线对称。
        /// </summary>
        internal static double BoltAngle(int index, int boltCount)
        {
            if (boltCount <= 0)
            {
                throw new InvalidOperationException("螺栓个数需大于 0。");
            }

            return 90.0 + index * 360.0 / boltCount;
        }

        /// <summary>
        /// 第 index 块加劲肋的角度（°）：固定取相邻两颗螺栓的正中间（半齿距）。
        /// 不能用“90° + 半齿距”，否则齿距不能整除 90°（例如 18 颗螺栓、齿距 20°）时
        /// 肋板会正好落在螺栓角度上，三维里与螺栓、螺母相碰。
        /// </summary>
        internal static double RibAngle(int index, int boltCount)
        {
            if (boltCount <= 0)
            {
                throw new InvalidOperationException("螺栓个数需大于 0。");
            }

            return 90.0 + (index + 0.5) * 360.0 / boltCount;
        }

        /// <summary>
        /// 梯形加劲肋轮廓（局部坐标：X = 距筒壁的径向距离，Y = 高度）。
        /// 与 AutoCAD 版 <c>ChimneyBaseGeometry.RibProfilePoints</c> 逐点一致：
        /// 筒壁处高 height，顶部平台 topWidth，斜边下降到外端 outerHeight，径向总长 length。
        /// </summary>
        internal static EngineeringPoint[] RibProfilePoints(
            double height, double topWidth, double length, double outerHeight)
        {
            return new[]
            {
                new EngineeringPoint(0.0, 0.0, 0.0),
                new EngineeringPoint(0.0, height, 0.0),
                new EngineeringPoint(topWidth, height, 0.0),
                new EngineeringPoint(length, outerHeight, 0.0),
                new EngineeringPoint(length, 0.0, 0.0)
            };
        }

        /// <summary>
        /// 顶部断管台阶轮廓（局部坐标：X = 横向，Y = 高度）。
        /// 高侧在 −reach 保持 topZ，经 stepWidth 水平过渡下降 stepHeight，低侧延伸到 +reach，
        /// 上方再围到 topZ + 2000，形成“切掉上半个空间”的切割体。
        /// 与 AutoCAD 版 <c>ChimneyBaseGeometry.StepBreakProfilePoints</c> 同形。
        /// </summary>
        internal static EngineeringPoint[] StepBreakProfilePoints(
            double topZ, double stepHeight, double stepWidth, double reach)
        {
            double half = stepWidth / 2.0;
            return new[]
            {
                new EngineeringPoint(-reach, topZ, 0.0),
                new EngineeringPoint(-half, topZ, 0.0),
                new EngineeringPoint(half, topZ - stepHeight, 0.0),
                new EngineeringPoint(reach, topZ - stepHeight, 0.0),
                new EngineeringPoint(reach, topZ + 2000.0, 0.0),
                new EngineeringPoint(-reach, topZ + 2000.0, 0.0)
            };
        }

        /// <summary>输入校核，返回中文原因；通过时 error 为空。</summary>
        internal static bool Validate(ChimneyBaseParameters parameters, out string error)
        {
            error = null;
            if (parameters == null)
            {
                error = "参数为空。";
                return false;
            }

            if (!Finite(parameters.ExhaustDiameterMm) ||
                parameters.ExhaustDiameterMm < ChimneyBaseConstants.MinDiameterMm ||
                parameters.ExhaustDiameterMm > ChimneyBaseConstants.MaxDiameterMm)
            {
                error = "排气筒直径 D1 需在 " + ChimneyBaseConstants.MinDiameterMm + "～" +
                    ChimneyBaseConstants.MaxDiameterMm + " mm 之间。";
                return false;
            }

            if (!Finite(parameters.BoltCircleDiameterMm) || parameters.BoltCircleDiameterMm < 0.0 ||
                parameters.BoltCircleDiameterMm > ChimneyBaseConstants.MaxDiameterMm)
            {
                error = "螺栓路径直径 D2 需为 0（自动 D1+350）或 0～" +
                    ChimneyBaseConstants.MaxDiameterMm + " mm。";
                return false;
            }

            if (!Finite(parameters.EmbeddedPlateDiameterMm) || parameters.EmbeddedPlateDiameterMm < 0.0 ||
                parameters.EmbeddedPlateDiameterMm > ChimneyBaseConstants.MaxDiameterMm)
            {
                error = "预埋钢板直径 D3 需为 0（自动 D1+700）或 0～" +
                    ChimneyBaseConstants.MaxDiameterMm + " mm。";
                return false;
            }

            if (parameters.BoltCount < ChimneyBaseConstants.MinBoltCount ||
                parameters.BoltCount > ChimneyBaseConstants.MaxBoltCount)
            {
                error = "螺栓个数需在 " + ChimneyBaseConstants.MinBoltCount + "～" +
                    ChimneyBaseConstants.MaxBoltCount + " 之间。";
                return false;
            }

            if (!Finite(parameters.AbovePlateMm) ||
                parameters.AbovePlateMm < ChimneyBaseConstants.MinAbovePlateMm ||
                parameters.AbovePlateMm > ChimneyBaseConstants.MaxAbovePlateMm)
            {
                error = "螺栓露出长度需在 " + ChimneyBaseConstants.MinAbovePlateMm + "～" +
                    ChimneyBaseConstants.MaxAbovePlateMm + " mm 之间。";
                return false;
            }

            if (!Finite(parameters.FoundationThicknessMm) ||
                parameters.FoundationThicknessMm < ChimneyBaseConstants.MinFoundationThicknessMm ||
                parameters.FoundationThicknessMm > ChimneyBaseConstants.MaxFoundationThicknessMm)
            {
                error = "混凝土基础厚度需在 " + ChimneyBaseConstants.MinFoundationThicknessMm + "～" +
                    ChimneyBaseConstants.MaxFoundationThicknessMm + " mm 之间（需容纳 J 形弯钩）。";
                return false;
            }

            if (!Finite(parameters.FoundationWidthMm) || parameters.FoundationWidthMm < 0.0 ||
                parameters.FoundationWidthMm > ChimneyBaseConstants.MaxFoundationWidthMm)
            {
                error = "混凝土基础宽度需为 0（自动 D3+200）或 " +
                    ChimneyBaseConstants.MinFoundationWidthMm + "～" +
                    ChimneyBaseConstants.MaxFoundationWidthMm + " mm。";
                return false;
            }

            if (!Finite(parameters.HeadingDegrees))
            {
                error = "绕竖轴旋转角必须是有效数字。";
                return false;
            }

            double d1, d2, d3;
            ResolveDiameters(parameters, out d1, out d2, out d3);

            if (parameters.FoundationWidthMm > 0.0 && parameters.FoundationWidthMm < d3)
            {
                error = "混凝土基础宽度不能小于预埋钢板直径 D3（" + Format(d3) + " mm）。";
                return false;
            }

            if (d3 / 2.0 <= d1 / 2.0 - ChimneyBaseConstants.PlateInnerInsetRadius)
            {
                error = "预埋钢板直径 D3（" + Format(d3) + " mm）需大于 D1 − 100 mm，否则环形板没有宽度。";
                return false;
            }

            if (d1 / 2.0 - ChimneyBaseConstants.DuctWallThickness <= 1.0)
            {
                error = "排气筒直径过小：扣除壁厚 " + Format(ChimneyBaseConstants.DuctWallThickness) +
                    " mm 后内腔不足。";
                return false;
            }

            if (d2 <= 0.0)
            {
                error = "螺栓路径直径 D2 解析后必须大于 0。";
                return false;
            }

            return true;
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
