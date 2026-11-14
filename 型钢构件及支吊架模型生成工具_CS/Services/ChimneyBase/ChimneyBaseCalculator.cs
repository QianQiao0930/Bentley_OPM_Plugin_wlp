using System;
using System.Collections.Generic;
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
                "+Y 面清扫口按原 400×600 弧形门框、密封垫、五段交错合页与压紧锁生成（风管过小时不生成）。",
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
        /// 圆风管弧形清扫口：400×600 弧形门框、密封垫、门板、两组合页（五段交错轴节 +
        /// 销轴 + 弧底垫座）与两把压紧锁（锁壳/旋钮/锁舌/调整环），装在 +Y 外壁，
        /// 门底距风管底部 400 mm；风管直径不足以放下 450 宽门框时不生成。
        /// 与 AutoCAD 版 DuctCleanoutSolidService 同一尺寸与构成。
        /// </summary>
        private static void AddCleanout(EngineeringPlan plan, double exhaustDiameter)
        {
            double ductRadius = exhaustDiameter / 2.0;
            double frameWidth = ChimneyBaseConstants.CleanoutDoorWidth +
                2.0 * ChimneyBaseConstants.CleanoutFrameMargin;
            if (2.0 * ductRadius <= frameWidth + 2.0)
            {
                return;
            }

            double doorCenterZ = ChimneyBaseConstants.BasePlateThickness +
                ChimneyBaseConstants.CleanoutDoorBottomOffset +
                ChimneyBaseConstants.CleanoutDoorHeight / 2.0;
            double frameHeight = ChimneyBaseConstants.CleanoutDoorHeight +
                2.0 * ChimneyBaseConstants.CleanoutFrameMargin;
            double openingWidth = ChimneyBaseConstants.CleanoutDoorWidth -
                2.0 * ChimneyBaseConstants.CleanoutOverlap;
            double openingHeight = ChimneyBaseConstants.CleanoutDoorHeight -
                2.0 * ChimneyBaseConstants.CleanoutOverlap;
            double innerRadius = ductRadius + ChimneyBaseConstants.CleanoutFrameThickness +
                ChimneyBaseConstants.CleanoutGasketThickness;
            double doorOuterRadius = innerRadius + ChimneyBaseConstants.CleanoutDoorThickness;

            EngineeringBody frame = AddCurvedPatch(plan, "清扫口门框", ductRadius,
                ductRadius + ChimneyBaseConstants.CleanoutFrameThickness, frameWidth, frameHeight,
                doorCenterZ, 0.0, SteelRed, SteelGreen, SteelBlue);
            CutOpening(frame, openingWidth, openingHeight, doorCenterZ, ductRadius + 50.0);

            EngineeringBody gasket = AddCurvedPatch(plan, "清扫口密封垫",
                ductRadius + ChimneyBaseConstants.CleanoutFrameThickness,
                ductRadius + ChimneyBaseConstants.CleanoutFrameThickness +
                    ChimneyBaseConstants.CleanoutGasketThickness,
                ChimneyBaseConstants.CleanoutDoorWidth, ChimneyBaseConstants.CleanoutDoorHeight,
                doorCenterZ, 0.0, 60, 65, 70);
            CutOpening(gasket, openingWidth, openingHeight, doorCenterZ, ductRadius + 50.0);

            EngineeringBody door = AddCurvedPatch(plan, "清扫口门板", innerRadius, doorOuterRadius,
                ChimneyBaseConstants.CleanoutDoorWidth, ChimneyBaseConstants.CleanoutDoorHeight,
                doorCenterZ, 0.0, SteelRed, SteelGreen, SteelBlue);
            double lockX = ChimneyBaseConstants.CleanoutDoorWidth / 2.0 -
                ChimneyBaseConstants.CleanoutLockEdgeOffset;
            foreach (int sign in new[] { -1, 1 })
            {
                double z = doorCenterZ + sign * ChimneyBaseConstants.CleanoutLockVerticalOffset;
                door.Cut.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(lockX, -10.0, z),
                    new EngineeringPoint(lockX, doorOuterRadius + 10.0, z), 10.3));
            }

            AddHinges(plan, ductRadius, innerRadius, doorOuterRadius, doorCenterZ);
            AddLocks(plan, ductRadius, doorOuterRadius, doorCenterZ);
        }

        /// <summary>弧形板：圆环与“y≥0、宽度为 width 的矩形”求交后的截面沿 Z 拉伸。</summary>
        private static EngineeringBody AddCurvedPatch(
            EngineeringPlan plan, string name, double innerRadius, double outerRadius,
            double width, double height, double zCenter, double xCenter, int red, int green, int blue)
        {
            var body = plan.Add(name);
            body.Color(red, green, blue);
            body.BestEffortCut = true;
            double zBottom = zCenter - height / 2.0 - 1.0;
            body.Add.Add(EngineeringShape.Extrude(
                CurvedPatchProfile(innerRadius, outerRadius, width, xCenter, zBottom),
                new EngineeringPoint(0.0, 0.0, height + 2.0)));
            return body;
        }

        /// <summary>矩形门洞：从弧形板厚度方向整块挖穿。</summary>
        private static void CutOpening(
            EngineeringBody body, double width, double height, double zCenter, double depth)
        {
            double zBottom = zCenter - height / 2.0;
            body.Cut.Add(EngineeringShape.Extrude(new[]
            {
                new EngineeringPoint(-width / 2.0, 0.0, zBottom),
                new EngineeringPoint(width / 2.0, 0.0, zBottom),
                new EngineeringPoint(width / 2.0, depth, zBottom),
                new EngineeringPoint(-width / 2.0, depth, zBottom)
            }, new EngineeringPoint(0.0, 0.0, height)));
        }

        /// <summary>
        /// 弧形板平面轮廓（XY，z 固定）：y≥0 半环被 x∈[xCenter±width/2] 截出的区域，
        /// 内外圆弧按约 1.5° 采样，两侧为竖直平面（与 CAD 的“圆环 ∩ 矩形块”一致）。
        /// </summary>
        private static EngineeringPoint[] CurvedPatchProfile(
            double innerRadius, double outerRadius, double width, double xCenter, double z)
        {
            if (outerRadius <= 0.0 || width <= 0.0)
            {
                throw new InvalidOperationException("清扫口弧形板尺寸无效。");
            }

            double xLeft = xCenter - width / 2.0;
            double xRight = xCenter + width / 2.0;
            if (xLeft >= outerRadius || xRight <= -outerRadius)
            {
                throw new InvalidOperationException("清扫口弧形板超出风管外圆。");
            }

            double left = Math.Max(xLeft, -outerRadius);
            double right = Math.Min(xRight, outerRadius);
            double startAngle = Math.Acos(right / outerRadius);
            double endAngle = Math.Acos(left / outerRadius);
            int outerSteps = Math.Max(8, (int)Math.Ceiling((endAngle - startAngle) / (1.5 * Math.PI / 180.0)));

            var points = new List<EngineeringPoint>(outerSteps + 64);
            for (int index = 0; index <= outerSteps; index++)
            {
                double angle = startAngle + (endAngle - startAngle) * index / outerSteps;
                AddUnique(points, new EngineeringPoint(
                    outerRadius * Math.Cos(angle), outerRadius * Math.Sin(angle), z));
            }

            int innerSteps = Math.Max(8, (int)Math.Ceiling(width / 2.0));
            for (int index = 0; index <= innerSteps; index++)
            {
                double x = left + (right - left) * index / innerSteps;
                double y = 0.0;
                if (innerRadius > 0.0 && Math.Abs(x) < innerRadius)
                {
                    y = Math.Sqrt(innerRadius * innerRadius - x * x);
                }

                AddUnique(points, new EngineeringPoint(x, y, z));
            }

            if (points.Count < 3)
            {
                throw new InvalidOperationException("清扫口弧形板轮廓点不足。");
            }

            return points.ToArray();
        }

        private static void AddUnique(List<EngineeringPoint> points, EngineeringPoint point)
        {
            if (points.Count == 0)
            {
                points.Add(point);
                return;
            }

            EngineeringPoint last = points[points.Count - 1];
            if (Math.Abs(last.X - point.X) > 1e-9 || Math.Abs(last.Y - point.Y) > 1e-9 ||
                Math.Abs(last.Z - point.Z) > 1e-9)
            {
                points.Add(point);
            }
        }

        // ============================================================
        // 合页：局部 X=切向、Y=径向、Z=轴向
        // ============================================================

        private static void AddHinges(
            EngineeringPlan plan, double ductRadius, double innerRadius,
            double doorOuterRadius, double doorCenterZ)
        {
            double hx = -ChimneyBaseConstants.CleanoutDoorWidth / 2.0;
            double mountRadius = doorOuterRadius + 2.0;
            double hy = Math.Sqrt(mountRadius * mountRadius - hx * hx);
            EngineeringPoint radial = Unit(hx, hy);
            EngineeringPoint tangent = new EngineeringPoint(radial.Y, -radial.X, 0.0);

            foreach (int sign in new[] { -1, 1 })
            {
                var axisPoint = new EngineeringPoint(
                    hx, hy, doorCenterZ + sign * ChimneyBaseConstants.CleanoutHingeOffset);

                AddHingeLeaf(plan, axisPoint, tangent, radial, -20.0, -3.0,
                    ChimneyBaseConstants.CleanoutFixedSegments,
                    ductRadius + ChimneyBaseConstants.CleanoutFrameThickness);
                AddHingeLeaf(plan, axisPoint, tangent, radial, 3.0, 20.0,
                    ChimneyBaseConstants.CleanoutMovingSegments,
                    innerRadius + ChimneyBaseConstants.CleanoutDoorThickness);

                var pin = plan.Add("清扫口合页销轴");
                pin.Color(MetalRed, MetalGreen, MetalBlue);
                pin.BestEffortCut = true;
                double half = ChimneyBaseConstants.CleanoutHingeLength / 2.0;
                pin.Add.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, 0.0, 3.5, -half - 1.0),
                    Local(axisPoint, tangent, radial, 0.0, 3.5, half + 1.0),
                    ChimneyBaseConstants.CleanoutPinRadius));
                pin.Add.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, 0.0, 3.5, -half - 1.5),
                    Local(axisPoint, tangent, radial, 0.0, 3.5, -half - 0.5), 2.3));
            }
        }

        private static void AddHingeLeaf(
            EngineeringPlan plan, EngineeringPoint axisPoint, EngineeringPoint tangent,
            EngineeringPoint radial, double low, double high, int[] segments, double skinRadius)
        {
            double mid = (low + high) / 2.0;
            double length = ChimneyBaseConstants.CleanoutHingeLength;
            double pitch = length / 5.0;
            double knuckleLength = pitch - 0.4;

            var leaf = plan.Add("清扫口合页叶");
            leaf.Color(MetalRed, MetalGreen, MetalBlue);
            leaf.BestEffortCut = true;
            leaf.Add.Add(BoxFrame(axisPoint, tangent, radial, mid, 1.0, 0.0,
                high - low, 2.0, length));

            foreach (int segment in segments)
            {
                double dz = -length / 2.0 + (segment + 0.5) * pitch;
                leaf.Add.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, 0.0, 3.5, dz - knuckleLength / 2.0),
                    Local(axisPoint, tangent, radial, 0.0, 3.5, dz + knuckleLength / 2.0),
                    ChimneyBaseConstants.CleanoutKnuckleRadius));
            }

            for (int segment = 0; segment < 5; segment++)
            {
                if (Array.IndexOf(segments, segment) >= 0)
                {
                    continue;
                }

                double dz = -length / 2.0 + (segment + 0.5) * pitch;
                leaf.Cut.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, 0.0, 3.5, dz - (pitch + 0.1) / 2.0),
                    Local(axisPoint, tangent, radial, 0.0, 3.5, dz + (pitch + 0.1) / 2.0),
                    ChimneyBaseConstants.CleanoutKnuckleRadius + 0.2));
            }

            leaf.Cut.Add(EngineeringShape.Cylinder(
                Local(axisPoint, tangent, radial, 0.0, 3.5, -length / 2.0 - 1.0),
                Local(axisPoint, tangent, radial, 0.0, 3.5, length / 2.0 + 1.0), 1.7));

            foreach (double dz in new[] { -length * 0.3, length * 0.3 })
            {
                leaf.Cut.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, mid, 1.0 - 4.0, dz),
                    Local(axisPoint, tangent, radial, mid, 1.0 + 4.0, dz), 2.2));
            }

            var pad = plan.Add("清扫口合页垫座");
            pad.Color(MetalRed, MetalGreen, MetalBlue);
            pad.BestEffortCut = true;
            pad.Add.Add(BoxFrame(axisPoint, tangent, radial, mid, -5.0, 0.0,
                high - low, 10.0, length - 2.0));
            pad.Cut.Add(EngineeringShape.Cylinder(
                new EngineeringPoint(0.0, 0.0, axisPoint.Z - 500.0),
                new EngineeringPoint(0.0, 0.0, axisPoint.Z + 500.0), skinRadius));

            foreach (double dz in new[] { -length * 0.3, length * 0.3 })
            {
                pad.Cut.Add(EngineeringShape.Cylinder(
                    Local(axisPoint, tangent, radial, mid, -4.0 - 10.0, dz),
                    Local(axisPoint, tangent, radial, mid, -4.0 + 10.0, dz), 2.2));
            }
        }

        // ============================================================
        // 压紧锁：局部 Y=门板法向
        // ============================================================

        private static void AddLocks(
            EngineeringPlan plan, double ductRadius, double doorOuterRadius, double doorCenterZ)
        {
            double lx = ChimneyBaseConstants.CleanoutDoorWidth / 2.0 -
                ChimneyBaseConstants.CleanoutLockEdgeOffset;
            double ly = Math.Sqrt(doorOuterRadius * doorOuterRadius - lx * lx);
            EngineeringPoint radial = Unit(lx, ly);
            EngineeringPoint tangent = new EngineeringPoint(radial.Y, -radial.X, 0.0);

            foreach (int sign in new[] { -1, 1 })
            {
                var surface = new EngineeringPoint(
                    lx, ly, doorCenterZ + sign * ChimneyBaseConstants.CleanoutLockVerticalOffset);

                var body = plan.Add("清扫口压紧锁壳");
                body.Color(MetalRed, MetalGreen, MetalBlue);
                body.BestEffortCut = true;
                body.Add.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -9.0, radial.Y * -9.0, 0.0),
                    surface.Offset(radial.X * 5.0, radial.Y * 5.0, 0.0), 10.0));
                body.Cut.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -20.0, radial.Y * -20.0, 0.0),
                    surface.Offset(radial.X * 20.0, radial.Y * 20.0, 0.0), 6.0));

                var bezel = EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -2.0, radial.Y * -2.0, 0.0),
                    surface.Offset(radial.X * 6.0, radial.Y * 6.0, 0.0), 16.0);
                body.Add.Add(bezel);
                body.Cut.Add(EngineeringShape.Cylinder(
                    new EngineeringPoint(0.0, 0.0, surface.Z - 500.0),
                    new EngineeringPoint(0.0, 0.0, surface.Z + 500.0), doorOuterRadius));
                body.Cut.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -20.0, radial.Y * -20.0, 0.0),
                    surface.Offset(radial.X * 20.0, radial.Y * 20.0, 0.0), 6.0));

                var shaft = plan.Add("清扫口锁旋钮");
                shaft.Color(MetalRed, MetalGreen, MetalBlue);
                shaft.BestEffortCut = true;
                shaft.Add.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -15.0, radial.Y * -15.0, 0.0),
                    surface.Offset(radial.X * 9.0, radial.Y * 9.0, 0.0), 5.5));
                shaft.Add.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * 7.5, radial.Y * 7.5, 0.0),
                    surface.Offset(radial.X * 12.5, radial.Y * 12.5, 0.0), 11.0));
                shaft.Cut.Add(BoxFrame(surface, tangent, radial, 0.0, 12.3, 0.0,
                    16.0, 2.0, 3.0));

                var cam = AddCurvedPatch(plan, "清扫口锁舌", ductRadius - 3.0, ductRadius,
                    50.0, 18.0, surface.Z, lx, MetalRed, MetalGreen, MetalBlue);
                cam.Cut.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -20.0, radial.Y * -20.0, 0.0),
                    surface.Offset(radial.X * 20.0, radial.Y * 20.0, 0.0), 5.6));

                var collar = plan.Add("清扫口锁调整环");
                collar.Color(MetalRed, MetalGreen, MetalBlue);
                collar.BestEffortCut = true;
                collar.Add.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -15.0, radial.Y * -15.0, 0.0),
                    surface.Offset(radial.X * -11.0, radial.Y * -11.0, 0.0), 9.0));
                collar.Cut.Add(EngineeringShape.Cylinder(
                    surface.Offset(radial.X * -16.0, radial.Y * -16.0, 0.0),
                    surface.Offset(radial.X * -10.0, radial.Y * -10.0, 0.0), 5.6));
            }
        }

        private static EngineeringPoint Unit(double x, double y)
        {
            double length = Math.Sqrt(x * x + y * y);
            if (length <= 1e-9)
            {
                throw new InvalidOperationException("清扫口方向向量无效。");
            }

            return new EngineeringPoint(x / length, y / length, 0.0);
        }

        private static EngineeringPoint Local(
            EngineeringPoint origin, EngineeringPoint xAxis, EngineeringPoint yAxis,
            double a, double b, double dz)
        {
            return new EngineeringPoint(
                origin.X + xAxis.X * a + yAxis.X * b,
                origin.Y + xAxis.Y * a + yAxis.Y * b,
                origin.Z + dz);
        }

        private static EngineeringShape BoxFrame(
            EngineeringPoint origin, EngineeringPoint xAxis, EngineeringPoint yAxis,
            double a, double b, double dz, double sizeX, double sizeY, double sizeZ)
        {
            double zBottom = dz - sizeZ / 2.0;
            return EngineeringShape.Extrude(new[]
            {
                Local(origin, xAxis, yAxis, a - sizeX / 2.0, b - sizeY / 2.0, zBottom),
                Local(origin, xAxis, yAxis, a + sizeX / 2.0, b - sizeY / 2.0, zBottom),
                Local(origin, xAxis, yAxis, a + sizeX / 2.0, b + sizeY / 2.0, zBottom),
                Local(origin, xAxis, yAxis, a - sizeX / 2.0, b + sizeY / 2.0, zBottom)
            }, new EngineeringPoint(0.0, 0.0, sizeZ));
        }

        private static double Radians(double degrees)
        {
            return degrees * Math.PI / 180.0;
        }
    }
}
