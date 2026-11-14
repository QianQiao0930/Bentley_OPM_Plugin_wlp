using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>工程绘图三维模块的纯计算回归：不引用 Bentley，只检查尺寸、计划完整性与包络。</summary>
    internal static class Program
    {
        private static int checks;
        private static int failures;

        private static void Main()
        {
            CheckTurnbuckle();
            CheckConicalVentCap();
            CheckChimneyBase();
            CheckChimneyCable();
            Console.WriteLine("EngineeringCheck: " + checks + " 项检查，失败 " + failures + " 项。");
            Environment.Exit(failures == 0 ? 0 : 1);
        }

        private static void CheckTurnbuckle()
        {
            // 表值抽查：M20 与 M110。
            var m20 = new TurnbuckleParameters { Size = 20, EndGapMm = 10, StudProtrusionMm = 5 };
            TurnbuckleSpec s20 = TurnbuckleCatalog.Resolve(m20);
            Equal(s20.H, 150.0, "M20 开口长 H");
            Equal(s20.h, 75.0, "M20 净距 h");
            Equal(s20.L, 220.0, "M20 总长 L");
            Equal(s20.B, 52.0, "M20 宽 B");
            Equal(s20.PinDiameter, 24.0, "M20 销轴");
            True(s20.RoundedStyle, "M20 圆角样式");
            False(s20.ClevisFullShoulder, "M20 短肩");

            var m110 = new TurnbuckleParameters { Size = 110, EndGapMm = 10, StudProtrusionMm = 5 };
            TurnbuckleSpec s110 = TurnbuckleCatalog.Resolve(m110);
            Equal(s110.L, 460.0, "M110 总长 L");
            True(s110.ClevisFullShoulder, "M110 全高肩");

            foreach (int size in TurnbuckleCatalog.Sizes)
            {
                var parameters = new TurnbuckleParameters { Size = size, EndGapMm = 10, StudProtrusionMm = 5 };
                EngineeringPlan plan = TurnbuckleCalculator.Calculate(parameters);
                TurnbuckleSpec spec = TurnbuckleCatalog.Resolve(parameters);
                Equal(plan.Bodies.Count, 17, "M" + size + " 实体数");
                Equal(plan.RotateXDegrees, 90.0, "M" + size + " 立式旋转");
                CheckShapes(plan, "M" + size);

                Bounds local = Bounds.Of(plan);
                Bounds world = local.RotateX(90.0);
                double top = (spec.L / 2.0 + spec.EndGap) + (spec.ClevisH + spec.HeadHeight) + spec.Clevish;
                Equal(world.MinZ, -top, 1e-6, "M" + size + " 总长下端");
                Equal(world.MaxZ, top, 1e-6, "M" + size + " 总长上端");
                True(world.MaxY > 0 && world.MinY < 0, "M" + size + " 厚度包络");
            }

            var invalid = new TurnbuckleParameters { Size = 11 };
            string error;
            False(TurnbuckleCatalog.Validate(invalid, out error), "拒绝非表列规格");
            True(error.Contains("规格"), "非表列规格提示");

            var badGap = new TurnbuckleParameters { Size = 20, EndGapMm = -1 };
            False(TurnbuckleCatalog.Validate(badGap, out error), "拒绝负端部间隙");

            var badProtrusion = new TurnbuckleParameters { Size = 20, StudProtrusionMm = 100 };
            False(TurnbuckleCatalog.Validate(badProtrusion, out error), "拒绝碰销轴的伸入长度");
        }

        private static void CheckConicalVentCap()
        {
            ConicalVentCapDimensions d1250 = ConicalVentCapCatalog.Dimensions(1250.0);
            Equal(d1250.D1, 1270.0, "风帽 D1=D+20");
            Equal(d1250.D2, 2413.0, "风帽 D2=1.9·D1");
            Equal(d1250.D3, 1524.0, "风帽 D3=1.2·D1");
            Equal(d1250.H, 145.0, "风帽 1250 档 H");
            Equal(d1250.H2, 1143.0, "风帽 H2=0.9·D1");
            Equal(d1250.Top, 2177.0, "风帽总高");
            Equal(d1250.H3, 826.0, "风帽 1250 档 H3");
            Equal(d1250.H4, 1016.0, "风帽 1250 档 H4");
            Equal(d1250.H5, 260.0, "风帽 1250 档 H5");
            Equal(d1250.SupportA, 449.0, "风帽 1250 档 A");
            Equal(d1250.SupportF, 540.0, "风帽 1250 档 F");
            Equal(d1250.SupportPhi, 100.3, "风帽 1250 档 φ");
            Equal(ConicalVentCapCatalog.PartCount(4), 15, "风帽实体数 7+2N");

            ConicalVentCapDimensions d650 = ConicalVentCapCatalog.Dimensions(650.0);
            Equal(d650.H, 115.0, "风帽 650 档 H 取上邻档");
            Equal(d650.H5, 190.0, "风帽 650 档 H5 取上邻档");
            True(Math.Abs(d650.H3 - 435.857142857) < 0.01, "风帽 650 档 H3 线性插值");
            True(!d650.IsCatalog && !d650.IsExtended, "风帽 650 为非标插值");

            foreach (int supportCount in new[] { 3, 4, 8 })
            {
                var parameters = new ConicalVentCapParameters
                {
                    DiameterMm = 1250.0,
                    WallThicknessMm = 2.0,
                    SupportCount = supportCount
                };
                EngineeringPlan plan = ConicalVentCapCalculator.Calculate(parameters);
                Equal(plan.Bodies.Count, 7 + 2 * supportCount, "风帽 N=" + supportCount + " 实体数");
                Equal(plan.CellName, "CONICAL_VENT_CAP_D1250", "风帽单元名");
                CheckShapes(plan, "风帽 N=" + supportCount);

                Bounds bounds = Bounds.Of(plan);
                Equal(bounds.MaxX, d1250.D2 / 2.0, 1.0, "风帽外径包络");
                Equal(bounds.MaxZ, d1250.Top, 1.0, "风帽总高包络");
                Equal(bounds.MinZ, 0.0, 1.0, "风帽底面");
            }

            string error;
            False(ConicalVentCapCatalog.Validate(
                new ConicalVentCapParameters { DiameterMm = 199.0 }, out error), "拒绝风帽 D<200");
            False(ConicalVentCapCatalog.Validate(
                new ConicalVentCapParameters { WallThicknessMm = 3.5 }, out error), "拒绝风帽板厚 >3");
            False(ConicalVentCapCatalog.Validate(
                new ConicalVentCapParameters { SupportCount = 9 }, out error), "拒绝风帽支撑 9 组");
        }

        private static void CheckChimneyBase()
        {
            var parameters = new ChimneyBaseParameters();
            double d1, d2, d3;
            ChimneyBaseCatalog.ResolveDiameters(parameters, out d1, out d2, out d3);
            Equal(d2, 1350.0, "底座 D2 自动 D1+350");
            Equal(d3, 1700.0, "底座 D3 自动 D1+700");
            Equal(ChimneyBaseCatalog.FoundationSide(parameters, d3), 1900.0, "底座基础自动 D3+200");
            Equal(ChimneyBaseCatalog.BoltAngle(0, 12), 90.0, "底座首颗螺栓 90°");
            Equal(ChimneyBaseCatalog.RibAngle(0, 12), 105.0, "底座首块肋板半齿距");

            EngineeringPlan plan = ChimneyBaseCalculator.Calculate(parameters);
            Equal(plan.Bodies.Count, 8 + 5 * parameters.BoltCount, "底座实体数 8+5N");
            Equal(plan.CellName, "CHIMNEY_BASE_D1000", "底座单元名");
            CheckShapes(plan, "底座默认");
            Bounds bounds = Bounds.Of(plan);
            Equal(bounds.MinZ, -200.0, "底座基础深度");
            Equal(bounds.MaxZ, 1510.0, 1.0, "底座风管顶");
            Equal(bounds.MaxX, 950.0, 1.0, "底座基础半宽");

            var custom = new ChimneyBaseParameters
            {
                ExhaustDiameterMm = 600.0,
                BoltCount = 6,
                AbovePlateMm = 50.0,
                FoundationThicknessMm = 300.0,
                FoundationWidthMm = 2000.0
            };
            EngineeringPlan customPlan = ChimneyBaseCalculator.Calculate(custom);
            Equal(customPlan.Bodies.Count, 8 + 5 * 6, "底座 6 螺栓实体数");
            CheckShapes(customPlan, "底座 6 螺栓");

            string error;
            False(ChimneyBaseCatalog.Validate(
                new ChimneyBaseParameters { ExhaustDiameterMm = 99.0 }, out error), "拒绝底座 D1<100");
            False(ChimneyBaseCatalog.Validate(
                new ChimneyBaseParameters { BoltCount = 1 }, out error), "拒绝底座 1 颗螺栓");
            False(ChimneyBaseCatalog.Validate(
                new ChimneyBaseParameters { AbovePlateMm = 10.0 }, out error), "拒绝底座露出长度过小");
            False(ChimneyBaseCatalog.Validate(
                new ChimneyBaseParameters { FoundationThicknessMm = 100.0 }, out error), "拒绝底座基础过薄");
        }

        private static void CheckChimneyCable()
        {
            Equal(ChimneyCableCatalog.OuterRadius(30000.0, 500.0, 30.0), 12047.005383, 0.001,
                "拉索外圆半径公式");
            False(ChimneyCableCatalog.NeedsExtraCable(30000.0, 500.0), "H/(2R)=30 不加中间层");
            True(ChimneyCableCatalog.NeedsExtraCable(60000.0, 500.0), "H/(2R)=60 加中间层");
            Equal(ChimneyCableCatalog.WallThickness(500.0), 20.0, "筒壁厚 max(5, 4%R)");

            var parameters = new ChimneyCableParameters();
            ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
            Equal(spec.CableCount, 3, "默认拉索根数");
            Equal(spec.AnchorCount, 3, "默认锚墩个数");

            EngineeringPlan plan = ChimneyCableCalculator.Calculate(parameters);
            CheckShapes(plan, "拉索默认");
            Bounds bounds = Bounds.Of(plan);
            Equal(bounds.MaxZ, 30000.0, 1.0, "筒身顶高");
            True(bounds.MinZ <= -ChimneyCableCatalog.AnchorBuriedDepthMm && bounds.MinZ > -200.0,
                "锚墩埋深");
            True(-bounds.MinY >= spec.OuterRadiusMm && -bounds.MinY <= spec.OuterRadiusMm + 300.0,
                "拉索外圆包络（outer=" + spec.OuterRadiusMm + "，minY=" + bounds.MinY + "）");

            var extra = new ChimneyCableParameters { HeightMeters = 60.0, DiameterMm = 500.0 };
            ChimneyCableSpec extraSpec = ChimneyCableCatalog.Resolve(extra);
            True(extraSpec.NeedsExtraCable, "60 m/φ500 需要中间层");
            Equal(extraSpec.CableCount, 6, "中间层拉索 6 根");
            EngineeringPlan extraPlan = ChimneyCableCalculator.Calculate(extra);
            CheckShapes(extraPlan, "拉索中间层");

            string error;
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { HeightMeters = 0.5 }, out error), "拒绝拉索 H<1 m");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { DiameterMm = 5.0 }, out error), "拒绝拉索 D<10 mm");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { CableAngleDegrees = 90.0 }, out error), "拒绝拉索角度 90°");
        }

        private static void CheckShapes(EngineeringPlan plan, string label)
        {
            foreach (EngineeringBody body in plan.Bodies)
            {
                True(body.Add.Count > 0, label + " " + body.Name + " 有基体");
                foreach (EngineeringShape shape in body.Add)
                {
                    CheckShape(shape, label + " " + body.Name);
                }

                foreach (EngineeringShape shape in body.Cut)
                {
                    CheckShape(shape, label + " " + body.Name + " 刀体");
                }
            }
        }

        private static void CheckShape(EngineeringShape shape, string label)
        {
            if (shape.Kind == EngineeringShapeKind.Cone || shape.Kind == EngineeringShapeKind.HexPrism)
            {
                True(Finite(shape.Start) && Finite(shape.End), label + " 端点有限");
                True(shape.RadiusStart > 0, label + " 起半径正值");
                True(shape.Kind != EngineeringShapeKind.Cone || shape.RadiusEnd > 0, label + " 终半径正值");
            }

            if (shape.Kind == EngineeringShapeKind.Torus)
            {
                True(Finite(shape.Start), label + " 圆心有限");
                True(shape.MajorRadius > 0 && shape.MinorRadius > 0 &&
                     shape.MinorRadius < shape.MajorRadius, label + " 圆环半径合理");
            }

            if (shape.Kind == EngineeringShapeKind.Revolve)
            {
                True(shape.Points.Length >= 3, label + " 回转点足够");
                foreach (EngineeringPoint point in shape.Points)
                {
                    True(Finite(point) && point.X >= 0, label + " 回转半径非负");
                }
            }

            if (shape.Kind == EngineeringShapeKind.Extrude)
            {
                True(shape.Points.Length >= 3, label + " 拉伸点足够");
                True(Math.Abs(shape.Direction.X) + Math.Abs(shape.Direction.Y) +
                     Math.Abs(shape.Direction.Z) > 1e-9, label + " 拉伸方向非零");
                foreach (EngineeringPoint point in shape.Points)
                {
                    True(Finite(point), label + " 拉伸点有限");
                }
            }

            if (shape.Kind == EngineeringShapeKind.Sweep)
            {
                True(shape.Points.Length >= 2, label + " 扫掠路径点足够");
                True(shape.RadiusStart > 0, label + " 扫掠半径正值");
            }
        }

        private static bool Finite(EngineeringPoint point)
        {
            return !double.IsNaN(point.X) && !double.IsInfinity(point.X) &&
                   !double.IsNaN(point.Y) && !double.IsInfinity(point.Y) &&
                   !double.IsNaN(point.Z) && !double.IsInfinity(point.Z);
        }

        private static void True(bool value, string label)
        {
            checks++;
            if (!value)
            {
                failures++;
                Console.WriteLine("失败：" + label);
            }
        }

        private static void False(bool value, string label)
        {
            True(!value, label);
        }

        private static void Equal(double actual, double expected, string label)
        {
            Equal(actual, expected, 1e-9, label);
        }

        private static void Equal(double actual, double expected, double tolerance, string label)
        {
            True(Math.Abs(actual - expected) <= tolerance,
                label + "（期望 " + expected + "，实际 " + actual + "）");
        }

        private static void Equal(int actual, int expected, string label)
        {
            True(actual == expected, label + "（期望 " + expected + "，实际 " + actual + "）");
        }

        private static void Equal(string actual, string expected, string label)
        {
            True(actual == expected, label + "（期望 " + expected + "，实际 " + actual + "）");
        }

        private struct Bounds
        {
            internal double MinX, MaxX, MinY, MaxY, MinZ, MaxZ;

            internal static Bounds Empty()
            {
                return new Bounds
                {
                    MinX = double.MaxValue,
                    MaxX = double.MinValue,
                    MinY = double.MaxValue,
                    MaxY = double.MinValue,
                    MinZ = double.MaxValue,
                    MaxZ = double.MinValue
                };
            }

            internal static Bounds Of(EngineeringPlan plan)
            {
                Bounds bounds = Empty();
                foreach (EngineeringBody body in plan.Bodies)
                {
                    foreach (EngineeringShape shape in body.Add)
                    {
                        bounds.Include(ShapeBounds(shape));
                    }
                }

                return bounds;
            }

            private void Include(EngineeringPoint point)
            {
                MinX = Math.Min(MinX, point.X);
                MaxX = Math.Max(MaxX, point.X);
                MinY = Math.Min(MinY, point.Y);
                MaxY = Math.Max(MaxY, point.Y);
                MinZ = Math.Min(MinZ, point.Z);
                MaxZ = Math.Max(MaxZ, point.Z);
            }

            private void Include(Bounds other)
            {
                MinX = Math.Min(MinX, other.MinX);
                MaxX = Math.Max(MaxX, other.MaxX);
                MinY = Math.Min(MinY, other.MinY);
                MaxY = Math.Max(MaxY, other.MaxY);
                MinZ = Math.Min(MinZ, other.MinZ);
                MaxZ = Math.Max(MaxZ, other.MaxZ);
            }

            internal Bounds RotateX(double degrees)
            {
                if (Math.Abs(degrees - 90.0) > 1e-9)
                {
                    return this;
                }

                return new Bounds
                {
                    MinX = MinX,
                    MaxX = MaxX,
                    MinY = -MaxZ,
                    MaxY = -MinZ,
                    MinZ = MinY,
                    MaxZ = MaxY
                };
            }

            private static Bounds ShapeBounds(EngineeringShape shape)
            {
                Bounds bounds = Empty();
                switch (shape.Kind)
                {
                    case EngineeringShapeKind.Cone:
                    case EngineeringShapeKind.HexPrism:
                    {
                        double radius = Math.Max(shape.RadiusStart, shape.RadiusEnd);
                        bounds.Include(shape.Start);
                        bounds.Include(shape.End);
                        bounds.Include(new EngineeringPoint(shape.Start.X - radius,
                            shape.Start.Y - radius, shape.Start.Z - radius));
                        bounds.Include(new EngineeringPoint(shape.Start.X + radius,
                            shape.Start.Y + radius, shape.Start.Z + radius));
                        bounds.Include(new EngineeringPoint(shape.End.X - radius,
                            shape.End.Y - radius, shape.End.Z - radius));
                        bounds.Include(new EngineeringPoint(shape.End.X + radius,
                            shape.End.Y + radius, shape.End.Z + radius));
                        break;
                    }

                    case EngineeringShapeKind.Revolve:
                        foreach (EngineeringPoint point in shape.Points)
                        {
                            bounds.Include(new EngineeringPoint(-point.X, -point.X, point.Z));
                            bounds.Include(new EngineeringPoint(point.X, point.X, point.Z));
                        }

                        break;
                    case EngineeringShapeKind.Extrude:
                        foreach (EngineeringPoint point in shape.Points)
                        {
                            bounds.Include(point);
                            bounds.Include(point.Offset(shape.Direction.X, shape.Direction.Y, shape.Direction.Z));
                        }

                        break;
                    case EngineeringShapeKind.Torus:
                        bounds.Include(new EngineeringPoint(shape.Start.X - shape.MajorRadius - shape.MinorRadius,
                            shape.Start.Y - shape.MajorRadius - shape.MinorRadius, shape.Start.Z - shape.MinorRadius));
                        bounds.Include(new EngineeringPoint(shape.Start.X + shape.MajorRadius + shape.MinorRadius,
                            shape.Start.Y + shape.MajorRadius + shape.MinorRadius, shape.Start.Z + shape.MinorRadius));
                        break;
                    case EngineeringShapeKind.Sweep:
                        foreach (EngineeringPoint point in shape.Points)
                        {
                            bounds.Include(point.Offset(-shape.RadiusStart, -shape.RadiusStart, -shape.RadiusStart));
                            bounds.Include(point.Offset(shape.RadiusStart, shape.RadiusStart, shape.RadiusStart));
                        }

                        break;
                }

                return bounds;
            }
        }
    }
}
