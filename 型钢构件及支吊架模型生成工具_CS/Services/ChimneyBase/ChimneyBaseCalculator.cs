using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱（排气筒）底座三维计划：迁移自 AutoCAD 版 <c>ChimneyBaseSolidService</c>。
    /// 局部原点 = 环形预埋钢板底面中心，Z 向上，单位 mm；
    /// 基础自 z = −基础厚 到 z = 0，预埋板 0～10，风管 10～1510。
    /// 只做三维建模，不生成俯视/剖面二维图形。
    /// </summary>
    internal static class ChimneyBaseCalculator
    {
        /// <summary>混凝土基础颜色（灰）。</summary>
        internal const int ConcreteRed = 128;
        internal const int ConcreteGreen = 128;
        internal const int ConcreteBlue = 128;

        /// <summary>钢板、加劲肋、风管颜色（钢灰）。</summary>
        internal const int SteelRed = 174;
        internal const int SteelGreen = 185;
        internal const int SteelBlue = 194;

        /// <summary>螺栓、螺母、垫圈、弯钩颜色（深灰）。</summary>
        internal const int MetalRed = 120;
        internal const int MetalGreen = 130;
        internal const int MetalBlue = 140;

        /// <summary>按参数生成完整三维计划；参数不合法时抛出带中文原因的计划异常。</summary>
        internal static EngineeringPlan Calculate(ChimneyBaseParameters parameters)
        {
            string error;
            if (!ChimneyBaseCatalog.Validate(parameters, out error))
            {
                throw new InvalidOperationException(error);
            }

            double d1, d2, d3;
            ChimneyBaseCatalog.ResolveDiameters(parameters, out d1, out d2, out d3);

            var plan = new EngineeringPlan
            {
                CellName = "CHIMNEY_BASE_D" + Math.Round(d1).ToString("0", CultureInfo.InvariantCulture),
                HeadingDegrees = parameters.HeadingDegrees,
                RotateXDegrees = 0.0
            };

            AddFoundation(plan, parameters, d3);
            AddRingPlate(plan, d1, d3);
            AddDuct(plan, d1);
            AddRibs(plan, d1, parameters.BoltCount);
            AddAnchorBolts(plan, d2, parameters);
            AddCleanout(plan, d1);
            return plan;
        }

        /// <summary>中文摘要：三个直径、螺栓数、基础尺寸与实体数。</summary>
        internal static string Describe(EngineeringPlan plan, ChimneyBaseParameters parameters)
        {
            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            if (parameters == null)
            {
                throw new ArgumentNullException("parameters");
            }

            double d1, d2, d3;
            ChimneyBaseCatalog.ResolveDiameters(parameters, out d1, out d2, out d3);
            double side = ChimneyBaseCatalog.FoundationSide(parameters, d3);

            return string.Format(CultureInfo.CurrentCulture,
                "D1 {0:0.###}、D2 {1:0.###}{2}、D3 {3:0.###}{4}；地脚螺栓 {5} 颗、露出板面 {6:0.###} mm；" +
                "混凝土基础 {7:0.###}×{7:0.###}×{8:0.###} mm；共 {9} 个实体；" +
                "+Y 面圆形清扫口为简化表达（门板 + 接管座 + 铰链/锁扣，非原 400×600 弧形门）。",
                d1,
                d2, parameters.BoltCircleDiameterMm > 0.0 ? "" : "（自动 D1+350）",
                d3, parameters.EmbeddedPlateDiameterMm > 0.0 ? "" : "（自动 D1+700）",
                parameters.BoltCount,
                parameters.AbovePlateMm,
                side,
                parameters.FoundationThicknessMm,
                plan.PartCount);
        }

        /// <summary>方形混凝土基础：顶面在预埋板底面 z = 0，向下挖到 −基础厚。</summary>
        private static void AddFoundation(
            EngineeringPlan plan, ChimneyBaseParameters parameters, double plateDiameter)
        {
            double side = ChimneyBaseCatalog.FoundationSide(parameters, plateDiameter);
            double half = side / 2.0;
            double bottom = -parameters.FoundationThicknessMm;
            double depth = parameters.FoundationThicknessMm;

            var outline = new[]
            {
                new EngineeringPoint(-half, -half, bottom),
                new EngineeringPoint(half, -half, bottom),
                new EngineeringPoint(half, half, bottom),
                new EngineeringPoint(-half, half, bottom)
            };

            var body = plan.Add("混凝土基础");
            body.Color(ConcreteRed, ConcreteGreen, ConcreteBlue);
            body.Add.Add(EngineeringShape.Extrude(outline, new EngineeringPoint(0.0, 0.0, depth)));
        }

        /// <summary>
        /// 环形预埋钢板：外径 D3、内径 D1−100、厚 10，用径向矩形绕 Z 轴回转，
        /// 板底位于原点 z = 0。
        /// </summary>
        private static void AddRingPlate(EngineeringPlan plan, double exhaustDiameter, double plateDiameter)
        {
            double inner = exhaustDiameter / 2.0 - ChimneyBaseConstants.PlateInnerInsetRadius;
            if (inner < 1.0)
            {
                inner = 1.0;
            }

            double outer = plateDiameter / 2.0;
            double top = ChimneyBaseConstants.BasePlateThickness;

            var profile = new[]
            {
                new EngineeringPoint(inner, 0.0, 0.0),
                new EngineeringPoint(outer, 0.0, 0.0),
                new EngineeringPoint(outer, 0.0, top),
                new EngineeringPoint(inner, 0.0, top)
            };

            var body = plan.Add("环形预埋钢板");
            body.Color(SteelRed, SteelGreen, SteelBlue);
            body.Add.Add(EngineeringShape.Revolve(profile));
        }

        /// <summary>
        /// 风管：壁厚 10、高 1500 的空心圆筒（自预埋板顶面 z = 10 起），
        /// 再用顶部台阶切割体减出 175/100 的断管台阶。
        /// </summary>
        private static void AddDuct(EngineeringPlan plan, double exhaustDiameter)
        {
            double outer = exhaustDiameter / 2.0;
            double inner = outer - ChimneyBaseConstants.DuctWallThickness;
            double bottom = ChimneyBaseConstants.BasePlateThickness;
            double top = bottom + ChimneyBaseConstants.DuctHeight;

            var profile = new[]
            {
                new EngineeringPoint(inner, 0.0, bottom),
                new EngineeringPoint(outer, 0.0, bottom),
                new EngineeringPoint(outer, 0.0, top),
                new EngineeringPoint(inner, 0.0, top)
            };

            var body = plan.Add("排气筒风管");
            body.Color(SteelRed, SteelGreen, SteelBlue);
            body.Add.Add(EngineeringShape.Revolve(profile));

            // 切割体：轮廓的 X（横向）→ 世界 Y，Y（高度）→ 世界 Z，沿世界 X 拉伸 2×reach。
            // reach 在常规直径下就是 2000；直径超过 4000 时按筒半径放大，保证台阶横贯整个截面。
            double reach = ChimneyBaseConstants.TopCutReach;
            if (exhaustDiameter + 200.0 > 2.0 * reach)
            {
                reach = outer + 100.0;
            }

            EngineeringPoint[] step = ChimneyBaseCatalog.StepBreakProfilePoints(
                top, ChimneyBaseConstants.TopStepHeight, ChimneyBaseConstants.TopStepWidth, reach);

            var cutter = new EngineeringPoint[step.Length];
            for (int index = 0; index < step.Length; index++)
            {
                cutter[index] = new EngineeringPoint(-reach, step[index].X, step[index].Y);
            }

            body.Cut.Add(EngineeringShape.Extrude(cutter, new EngineeringPoint(2.0 * reach, 0.0, 0.0)));
        }

        /// <summary>
        /// 加劲肋：按 RibAngle 均布 N 块梯形板。
        /// 局部 X 为径向（自筒壁起算）、Y 为高度（自预埋板顶面起算），
        /// 厚 10 沿切向拉伸，轮廓先沿切向偏移 −5 使板厚居中。
        /// </summary>
        private static void AddRibs(EngineeringPlan plan, double exhaustDiameter, int boltCount)
        {
            double ductRadius = exhaustDiameter / 2.0;
            double halfThickness = ChimneyBaseConstants.RibThickness / 2.0;

            EngineeringPoint[] profile = ChimneyBaseCatalog.RibProfilePoints(
                ChimneyBaseConstants.RibHeight,
                ChimneyBaseConstants.RibTopWidth,
                ChimneyBaseConstants.RibLength,
                ChimneyBaseConstants.RibOuterHeight);

            for (int index = 0; index < boltCount; index++)
            {
                double angle = Radians(ChimneyBaseCatalog.RibAngle(index, boltCount));
                double cosine = Math.Cos(angle);
                double sine = Math.Sin(angle);

                var points = new EngineeringPoint[profile.Length];
                for (int vertex = 0; vertex < profile.Length; vertex++)
                {
                    double radius = ductRadius + profile[vertex].X;
                    points[vertex] = new EngineeringPoint(
                        cosine * radius + sine * halfThickness,
                        sine * radius - cosine * halfThickness,
                        ChimneyBaseConstants.BasePlateThickness + profile[vertex].Y);
                }

                var body = plan.Add("加劲肋");
                body.Color(SteelRed, SteelGreen, SteelBlue);
                body.Add.Add(EngineeringShape.Extrude(points, new EngineeringPoint(
                    -sine * ChimneyBaseConstants.RibThickness,
                    cosine * ChimneyBaseConstants.RibThickness,
                    0.0)));
            }
        }

        /// <summary>
        /// 地脚螺栓 N 颗：直杆 + 垫圈 + 六角螺母 + 底部 J 形弯钩。
        /// 位置 = (D2/2·cosθ, D2/2·sinθ, 0)，θ 取 BoltAngle；
        /// 杆下端弯心 z = −(钩顶距板底 50) − (弯钩直段 40) = −90。
        /// </summary>
        private static void AddAnchorBolts(
            EngineeringPlan plan, double boltCircleDiameter, ChimneyBaseParameters parameters)
        {
            double rodRadius = ChimneyBaseConstants.AnchorRodDiameter / 2.0;
            double plateTop = ChimneyBaseConstants.BasePlateThickness;
            double rodTop = plateTop + parameters.AbovePlateMm;
            double bendCenterZ = -ChimneyBaseConstants.HookTopClearance - ChimneyBaseConstants.AnchorHookLength;

            for (int index = 0; index < parameters.BoltCount; index++)
            {
                double angle = Radians(ChimneyBaseCatalog.BoltAngle(index, parameters.BoltCount));
                double cosine = Math.Cos(angle);
                double sine = Math.Sin(angle);

                double x = boltCircleDiameter / 2.0 * cosine;
                double y = boltCircleDiameter / 2.0 * sine;

                var rod = plan.Add("地脚螺栓螺杆");
                rod.Color(MetalRed, MetalGreen, MetalBlue);
                rod.Add.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(x, y, bendCenterZ),
                    new EngineeringPoint(x, y, rodTop),
                    rodRadius));

                var washer = plan.Add("地脚螺栓垫圈");
                washer.Color(MetalRed, MetalGreen, MetalBlue);
                washer.Add.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(x, y, plateTop),
                    new EngineeringPoint(x, y, plateTop + ChimneyBaseConstants.WasherThickness),
                    ChimneyBaseConstants.WasherDiameter / 2.0));

                double nutBottom = plateTop + ChimneyBaseConstants.WasherThickness;
                var nut = plan.Add("地脚螺栓螺母");
                nut.Color(MetalRed, MetalGreen, MetalBlue);
                nut.Add.Add(EngineeringShape.HexPrism(
                    new EngineeringPoint(x, y, nutBottom),
                    new EngineeringPoint(x, y, nutBottom + ChimneyBaseConstants.NutHeight),
                    ChimneyBaseConstants.NutAcrossFlats));

                var hook = plan.Add("J 形弯钩");
                hook.Color(MetalRed, MetalGreen, MetalBlue);
                hook.Add.Add(EngineeringShape.Sweep(
                    HookPath(x, y, -cosine, -sine, bendCenterZ), rodRadius));
            }
        }

        /// <summary>
        /// J 形弯钩路径：自直杆下端起的半圆（半径 40，向下 180°，采样 32 段）+
        /// 向上直段 40。弯心沿 inward = (−cosθ, −sinθ, 0) 方向偏移一个弯曲半径。
        /// </summary>
        private static EngineeringPoint[] HookPath(
            double x, double y, double inwardX, double inwardY, double startZ)
        {
            double radius = ChimneyBaseConstants.HookBendRadius;
            int steps = ChimneyBaseConstants.HookSampleCount;

            double centerX = x + inwardX * radius;
            double centerY = y + inwardY * radius;

            var path = new EngineeringPoint[steps + 2];
            for (int sample = 0; sample <= steps; sample++)
            {
                double phi = Math.PI + Math.PI * sample / steps;
                double offset = Math.Cos(phi) * radius;
                path[sample] = new EngineeringPoint(
                    centerX + inwardX * offset,
                    centerY + inwardY * offset,
                    startZ + Math.Sin(phi) * radius);
            }

            path[steps + 1] = new EngineeringPoint(
                centerX + inwardX * radius,
                centerY + inwardY * radius,
                startZ + ChimneyBaseConstants.AnchorHookLength);
            return path;
        }

        /// <summary>
        /// 圆风管弧形清扫口的简化三维表达：装在 +Y 外壁、门底距筒底 400。
        /// 只做“短接管座 + 圆形门板 + 铰链与锁扣”，不还原原 400×600 弧形门框、
        /// 密封垫、五段交错轴节与压紧锁内部结构。
        /// </summary>
        private static void AddCleanout(EngineeringPlan plan, double exhaustDiameter)
        {
            double ductRadius = exhaustDiameter / 2.0;
            double doorRadius = Math.Min(
                ChimneyBaseConstants.CleanoutMaxDoorRadius,
                Math.Max(ChimneyBaseConstants.CleanoutMinDoorRadius, ductRadius * 0.5));
            double collarWall = Math.Min(
                ChimneyBaseConstants.CleanoutCollarWall,
                Math.Max(ChimneyBaseConstants.CleanoutMinCollarWall, doorRadius * 0.25));
            double centerZ = ChimneyBaseConstants.BasePlateThickness +
                ChimneyBaseConstants.CleanoutDoorBottomOffset + doorRadius;

            double face = ductRadius;
            double doorFront = face + collarWall;
            double doorBack = doorFront + ChimneyBaseConstants.CleanoutDoorThickness;

            var neck = plan.Add("清扫口接管座");
            neck.Color(SteelRed, SteelGreen, SteelBlue);
            neck.Add.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0.0, face - 2.0, centerZ),
                new EngineeringPoint(0.0, doorFront, centerZ),
                doorRadius + collarWall));
            neck.Cut.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0.0, face - 4.0, centerZ),
                new EngineeringPoint(0.0, doorBack + 2.0, centerZ),
                doorRadius + 1.0));

            var door = plan.Add("清扫口门板");
            door.Color(SteelRed, SteelGreen, SteelBlue);
            door.Add.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0.0, doorFront, centerZ),
                new EngineeringPoint(0.0, doorBack, centerZ),
                doorRadius));

            // 铰链与锁扣互不相交，各自单独成体，避免对分离实体做布尔相并。
            double knuckle = Math.Min(24.0, doorRadius * 0.35);
            double hingeX = -(doorRadius + 2.0);
            double hingeY = doorFront + ChimneyBaseConstants.CleanoutDoorThickness / 2.0;
            foreach (double sign in new[] { -1.0, 1.0 })
            {
                double z = centerZ + sign * doorRadius * 0.55;
                var hinge = plan.Add("清扫口铰链");
                hinge.Color(MetalRed, MetalGreen, MetalBlue);
                hinge.Add.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(hingeX, hingeY, z - knuckle / 2.0),
                    new EngineeringPoint(hingeX, hingeY, z + knuckle / 2.0),
                    ChimneyBaseConstants.CleanoutHingeRadius));
            }

            double latchX = doorRadius * 0.8;
            var latch = plan.Add("清扫口锁扣");
            latch.Color(MetalRed, MetalGreen, MetalBlue);
            latch.Add.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(latchX, doorBack, centerZ),
                new EngineeringPoint(latchX, doorBack + 10.0, centerZ),
                6.0));
            latch.Add.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(latchX - 18.0, doorBack + 6.0, centerZ),
                new EngineeringPoint(latchX + 18.0, doorBack + 6.0, centerZ),
                3.0));
        }

        private static double Radians(double degrees)
        {
            return degrees * Math.PI / 180.0;
        }
    }
}
