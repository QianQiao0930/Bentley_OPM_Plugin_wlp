using System;
using System.Collections.Generic;
using System.Globalization;

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
            Equal(plan.Bodies.Count, 24 + 6 * parameters.BoltCount, "底座实体数 24+6N");
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
            Equal(customPlan.Bodies.Count, 24 + 6 * 6, "底座 6 螺栓实体数");
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
            Equal(new ChimneyCableParameters().WallThicknessMm, 10.0, 1e-9, "筒壁厚默认 10 mm");

            var parameters = new ChimneyCableParameters();
            ChimneyCableSpec spec = ChimneyCableCatalog.Resolve(parameters);
            Equal(spec.WallThicknessMm, 10.0, 1e-9, "筒壁厚取自输入参数");
            Equal(spec.CableCount, 3, "默认拉索根数");
            Equal(spec.AnchorCount, 3, "默认锚墩个数");

            EngineeringPlan plan = ChimneyCableCalculator.Calculate(parameters);
            CheckShapes(plan, "拉索默认");

            // 绳圈必须是放样（单一光滑管面），否则逐段扫掠会在每段接缝留下横向棱线。
            int loftCount = 0;
            foreach (EngineeringBody body in plan.Bodies)
            {
                foreach (EngineeringShape shape in body.Add)
                {
                    if (shape.Kind == EngineeringShapeKind.Loft)
                    {
                        loftCount++;
                        True(shape.Points.Length >= 10, "绳圈放样路径点足够");
                        True(shape.ArcMiddles != null && shape.ArcMiddles.Length >= shape.Points.Length - 1,
                            "绳圈放样圆弧中点齐全");
                        True(Math.Abs(shape.AxisX.X) + Math.Abs(shape.AxisX.Y) + Math.Abs(shape.AxisX.Z) > 0.5,
                            "绳圈放样平面法向为单位向量");
                    }
                }
            }

            Equal(loftCount, 6, "默认拉索 3 根 × 两端绳眼 = 6 个绳圈放样");

            // 并入底座：合并后的实体数 = 拉索部分 56 + 底座模块实体数 − 底座自带风管 1
            int baseBodies = ChimneyBaseCalculator.Calculate(
                ChimneyCableCatalog.ToBaseParameters(parameters)).PartCount;
            Equal(plan.PartCount, 56 + baseBodies - 1,
                "默认实体数 = 拉索 56 + 并入底座 " + baseBodies + "（不含底座自带风管）");
            CheckCollar(plan, spec, "拉索默认");
            CheckGroundFixing(plan, spec, "拉索默认", 3);
            CheckThimble(plan, "拉索默认");
            CheckMaterials(plan, spec, "拉索默认", 3);

            // 底座确实并进来了：基础、预埋板、加劲肋、地脚螺栓、检修门都在
            Equal(CountBodies(plan, "混凝土基础"), 1, "并入 1 块混凝土基础");
            Equal(CountBodies(plan, "环形预埋钢板"), 1, "并入 1 块环形预埋板");
            Equal(CountBodies(plan, "加劲肋"), parameters.BoltCount, "加劲肋与地脚螺栓同数");
            Equal(CountBodies(plan, "清扫口门板"), 1, "并入 +Y 面弧形检修门");
            Equal(CountBodies(plan, "排气筒风管"), 0, "不再画底座自带的风管（避免断管台阶）");

            Bounds bounds = Bounds.Of(plan);
            Equal(bounds.MaxZ, 30000.0, 1.0, "筒身顶高");
            True(bounds.MinZ <= -ChimneyCableCatalog.AnchorBuriedDepthMm,
                "锚墩埋深");
            // 说明：Bounds.Of 只按路径**控制点**加半径，不含圆弧中点，
            // 所以这里核对的是腿底外缘 −862.5；回钩弧顶的真最低点 −900 由 CheckGroundFixing 单独核对。
            Equal(bounds.MinZ, ChimneyCableCatalog.GroundRingLegBottomMm -
                ChimneyCableCatalog.GroundRingBarMm / 2.0, 1.0,
                "最低点：φ30 吊环腿底外缘");
            True(-bounds.MinY >= spec.OuterRadiusMm && -bounds.MinY <= spec.OuterRadiusMm + 300.0,
                "拉索外圆包络（outer=" + spec.OuterRadiusMm + "，minY=" + bounds.MinY + "）");

            var extra = new ChimneyCableParameters { HeightMeters = 60.0, DiameterMm = 500.0 };
            ChimneyCableSpec extraSpec = ChimneyCableCatalog.Resolve(extra);
            True(extraSpec.NeedsExtraCable, "60 m/φ500 需要中间层");
            Equal(extraSpec.CableCount, 6, "中间层拉索 6 根");
            EngineeringPlan extraPlan = ChimneyCableCalculator.Calculate(extra);
            CheckShapes(extraPlan, "拉索中间层");
            Equal(CountBodies(extraPlan, "环板"), 2, "中间层 2 圈连接环板");
            Equal(CountUpperRebars(extraPlan), 6, "中间层 6 根上端吊筋");
            Equal(CountBodies(extraPlan, "地面吊环"), 6, "中间层 6 个地面 φ30 吊环");
            Equal(CountBodies(extraPlan, "地面锚墩"), 6, "中间层 6 个锚墩（上下层各一）");
            Equal(extraPlan.PartCount, 111 + baseBodies - 1,
                "中间层实体数 = 拉索 111 + 并入底座 " + baseBodies + "（不含底座自带风管）");
            CheckGroundFixing(extraPlan, extraSpec, "拉索中间层", 6);
            CheckMaterials(extraPlan, extraSpec, "拉索中间层", 6);

            // 自立式：关掉拉索后不应再有任何拉索/环板/绳眼/地面吊环，只剩筒身与基础
            var selfStanding = new ChimneyCableParameters { GenerateCables = false };
            ChimneyCableSpec selfSpec = ChimneyCableCatalog.Resolve(selfStanding);
            Equal(selfSpec.CableCount, 0, "自立式拉索根数 0");
            Equal(selfSpec.AnchorCount, 0, "自立式锚墩 0");
            EngineeringPlan selfPlan = ChimneyCableCalculator.Calculate(selfStanding);
            CheckShapes(selfPlan, "自立式");
            Equal(CountBodies(selfPlan, "拉索 "), 0, "自立式没有拉索与绳眼");
            Equal(CountBodies(selfPlan, "地面吊环"), 0, "自立式没有地面吊环");
            Equal(CountBodies(selfPlan, "地面锚墩"), 0, "自立式没有锚墩");
            Equal(CountBodies(selfPlan, "环板"), 0, "自立式没有连接环板");
            Equal(CountBodies(selfPlan, "筒身"), 1, "自立式仍有筒身");
            Equal(CountBodies(selfPlan, "混凝土基础"), 1, "自立式仍有基础");
            Equal(CountBodies(selfPlan, "清扫口门板"), 1, "自立式仍有检修门");
            Equal(selfPlan.PartCount, 1 + baseBodies - 1, "自立式实体数 = 筒身 1 + 底座（不含风管）");
            CheckMaterials(selfPlan, selfSpec, "自立式", 0);

            // 自立式没有拉索，包络可以直接核对基础与总高
            Bounds selfBounds = Bounds.Of(selfPlan);
            Equal(selfBounds.MaxZ, 30000.0, 1.0, "自立式筒顶标高 = 总高");
            Equal(selfBounds.MaxX, selfSpec.FoundationSideMm / 2.0, 1.0, "自立式包络 = 基础边长的一半");
            Equal(selfBounds.MinZ, -selfSpec.FoundationThicknessMm, 1.0, "自立式最低点 = 基础底面");
            Equal(selfSpec.ShellBottomMm, ChimneyBaseConstants.BasePlateThickness, 1e-12,
                "生成基础时筒身从预埋板顶面起");

            // 关掉基础：没有混凝土/预埋板/加劲肋/地脚螺栓，筒身从 z = 0 起
            var noBase = new ChimneyCableParameters { GenerateBase = false };
            ChimneyCableSpec noBaseSpec = ChimneyCableCatalog.Resolve(noBase);
            Equal(noBaseSpec.ShellBottomMm, 0.0, 1e-12, "不生成基础时筒身从 0 起");
            EngineeringPlan noBasePlan = ChimneyCableCalculator.Calculate(noBase);
            CheckShapes(noBasePlan, "无基础");
            Equal(CountBodies(noBasePlan, "混凝土基础"), 0, "无基础时没有混凝土基础");
            Equal(CountBodies(noBasePlan, "环形预埋钢板"), 0, "无基础时没有预埋板");
            Equal(CountBodies(noBasePlan, "地面吊环"), 3, "无基础时拉索与地面吊环仍在");
            CheckMaterials(noBasePlan, noBaseSpec, "无基础", 3);

            // 壁厚可调：默认 10，自定义值必须贯穿几何与材料
            var thick = new ChimneyCableParameters { WallThicknessMm = 25.0 };
            ChimneyCableSpec thickSpec = ChimneyCableCatalog.Resolve(thick);
            Equal(thickSpec.WallThicknessMm, 25.0, 1e-9, "自定义壁厚 25 生效");
            EngineeringPlan thickPlan = ChimneyCableCalculator.Calculate(thick);
            CheckShapes(thickPlan, "拉索壁厚25");
            ChimneyCableMaterials thickMaterials = ChimneyCableTakeoff.Of(thickSpec, thickPlan);
            Equal(thickMaterials.StackThicknessMm, 25.0, 1e-9, "材料壁厚跟随参数");
            True(thickMaterials.StackMassKg > ChimneyCableTakeoff.Of(spec, plan).StackMassKg,
                "壁厚加大后钢管更重");

            string error;
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { HeightMeters = 0.5 }, out error), "拒绝拉索 H<1 m");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { DiameterMm = 5.0 }, out error), "拒绝拉索 D<10 mm");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { CableAngleDegrees = 90.0 }, out error), "拒绝拉索角度 90°");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { WallThicknessMm = 0.5 }, out error), "拒绝壁厚 <1 mm");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { WallThicknessMm = 1200.0 }, out error), "拒绝壁厚 >1000 mm");
            False(ChimneyCableCatalog.Validate(
                new ChimneyCableParameters { DiameterMm = 10.0, WallThicknessMm = 10.0 }, out error),
                "拒绝壁厚不小于筒身半径");
        }

        private static int CountBodies(EngineeringPlan plan, string fragment)
        {
            int count = 0;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf(fragment, StringComparison.Ordinal) >= 0)
                {
                    count++;
                }
            }

            return count;
        }

        /// <summary>
        /// 上端连接环板 + U 形吊筋：尺寸与“不得有明显干涉”的离线校核。
        /// 绳眼整体挂在环板下方，绳表面距板底 &gt; 6 mm；拉索本体距环板 &gt; 6 mm。
        /// </summary>
        private static void CheckCollar(EngineeringPlan plan, ChimneyCableSpec spec, string label)
        {
            double radius = spec.RadiusMm;
            double top = 2.0 * spec.HeightMm / 3.0;
            double bottom = top - ChimneyCableCatalog.CollarThicknessMm;
            double inner = radius - ChimneyCableCatalog.CollarEmbedMm;
            double outer = radius + ChimneyCableCatalog.CollarWidthMm;
            double holeRadius = ChimneyCableCatalog.CollarHoleRadiusMm(radius);

            Equal(outer - holeRadius, ChimneyCableCatalog.CollarHoleEdgeOffsetMm, 1e-9,
                label + " 孔心距环板外缘 50");

            EngineeringBody collar = null;
            EngineeringBody rope = null;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name == "上端连接环板")
                {
                    collar = body;
                }
                else if (body.Name == "拉索 1（上层）")
                {
                    rope = body;
                }
            }

            True(collar != null, label + " 有上端连接环板");
            Equal(collar.Add.Count, 1, label + " 环板为单个回转体");
            True(collar.Add[0].Kind == EngineeringShapeKind.Revolve, label + " 环板为回转环形板");
            Equal(collar.Cut.Count, 6, label + " 环板 6 个孔（3 个方向 × 2）");
            foreach (EngineeringShape hole in collar.Cut)
            {
                double r = Math.Sqrt(hole.Start.X * hole.Start.X + hole.Start.Y * hole.Start.Y);
                Equal(r, holeRadius, 1e-6, label + " 孔心半径 = R+50");
                Equal(hole.RadiusStart * 2.0, ChimneyCableCatalog.CollarHoleDiameterMm, 1e-9,
                    label + " 孔径 φ24");
                True(hole.RadiusStart * 2.0 < ChimneyCableCatalog.CollarNutAcrossFlatsMm,
                    label + " 孔径小于螺母对边，螺母能压住孔口");
                True(hole.Start.Z < bottom && hole.End.Z > top, label + " 孔为通孔");
            }

            Equal(CountBodies(plan, "上端吊筋"), 3, label + " 3 根上端吊筋");
            double lowestBend = double.MaxValue;
            EngineeringPoint bendPoint = default(EngineeringPoint);
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("上端吊筋", StringComparison.Ordinal) < 0)
                {
                    continue;
                }

                EngineeringShape rebar = body.Add[0];
                True(rebar.Kind == EngineeringShapeKind.Sweep, label + " 吊筋为扫掠");
                Equal(rebar.RadiusStart * 2.0, ChimneyCableCatalog.RebarDiameterMm, 1e-9,
                    label + " 吊筋 φ20");
                Equal(rebar.Points[0].Z, top + ChimneyCableCatalog.RebarAboveCollarMm, 1e-6,
                    label + " 吊筋高出板面 30");
                foreach (EngineeringPoint? middle in rebar.ArcMiddles)
                {
                    if (middle.HasValue && middle.Value.Z < lowestBend)
                    {
                        lowestBend = middle.Value.Z;
                        bendPoint = middle.Value;
                    }
                }

                // 两条腿各一个 M20 螺母，压在环板上表面。
                Equal(body.Add.Count, 3, label + " 吊筋 = 1 个 U 形螺栓 + 2 个螺母");
                double maxNutTop = 0.0;
                foreach (EngineeringShape nut in body.Add)
                {
                    if (nut.Kind != EngineeringShapeKind.HexPrism)
                    {
                        continue;
                    }

                    Equal(nut.RadiusStart * Math.Sqrt(3.0), ChimneyCableCatalog.CollarNutAcrossFlatsMm,
                        1e-6, label + " 螺母对边 30");
                    Equal(Math.Abs(nut.End.Z - nut.Start.Z), ChimneyCableCatalog.CollarNutHeightMm,
                        1e-9, label + " 螺母厚 16");
                    Equal(Math.Min(nut.Start.Z, nut.End.Z), top, 1e-9,
                        label + " 螺母压在环板上表面");
                    maxNutTop = Math.Max(maxNutTop, Math.Max(nut.Start.Z, nut.End.Z));
                }

                True(maxNutTop + 10.0 <= top + ChimneyCableCatalog.RebarAboveCollarMm,
                    label + " 螺母上方露出至少 10 mm 螺纹");
            }

            Equal(lowestBend, top - ChimneyCableCatalog.RebarBendDepthMm, 1e-6,
                label + " 吊筋弯钩最低点 = 板面下 60");

            True(rope != null, label + " 有上层拉索");
            double eyeClear = double.MaxValue;
            double strandClear = double.MaxValue;
            double nearest = double.MaxValue;
            foreach (EngineeringShape shape in rope.Add)
            {
                if (shape.Kind == EngineeringShapeKind.Loft)
                {
                    foreach (EngineeringPoint point in shape.Points)
                    {
                        double r = Math.Sqrt(point.X * point.X + point.Y * point.Y);
                        double clearance = SlabClearance(r, point.Z, 8.0, inner, outer, bottom, top);
                        eyeClear = Math.Min(eyeClear, clearance);
                        nearest = Math.Min(nearest, PointDistance(point, bendPoint));
                    }
                }
                else if (shape.Kind == EngineeringShapeKind.Cone)
                {
                    for (int index = 0; index <= 40; index++)
                    {
                        double t = index / 40.0;
                        double x = shape.Start.X + (shape.End.X - shape.Start.X) * t;
                        double y = shape.Start.Y + (shape.End.Y - shape.Start.Y) * t;
                        double z = shape.Start.Z + (shape.End.Z - shape.Start.Z) * t;
                        strandClear = Math.Min(strandClear,
                            SlabClearance(Math.Sqrt(x * x + y * y), z, 8.0, inner, outer, bottom, top));
                    }
                }
            }

            True(eyeClear > 6.0, label + " 绳眼与环板净距 > 6 mm（实测 " + Format(eyeClear) + "）");
            True(strandClear > 6.0, label + " 拉索本体与环板净距 > 6 mm（实测 " + Format(strandClear) + "）");
            True(nearest > 19.0 && nearest < 20.2,
                label + " 绳眼挂在吊筋上且不穿绳（轴距 " + Format(nearest) + "）");
        }

        /// <summary>点到轴对环形板实料的最短距离，已按绳半径扣除。</summary>
        private static double SlabClearance(
            double r, double z, double tubeRadius, double inner, double outer, double bottom, double top)
        {
            double dr = Math.Max(Math.Max(inner - r, 0.0), r - outer);
            double dz = Math.Max(Math.Max(bottom - z, 0.0), z - top);
            return Math.Sqrt(dr * dr + dz * dz) - tubeRadius;
        }

        private static double PointDistance(EngineeringPoint a, EngineeringPoint b)
        {
            double dx = a.X - b.X;
            double dy = a.Y - b.Y;
            double dz = a.Z - b.Z;
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }

        /// <summary>
        /// 鸡心环：CAD 的开口槽形截面沿泪滴路径扫掠（不是扁带），
        /// 槽底托住绳内缘、唇壁低于绳中心外偏，绳坐在槽里，不会像扁带那样挡住绳子。
        /// </summary>
        private static void CheckThimble(EngineeringPlan plan, string label)
        {
            EngineeringBody thimble = null;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("上端绳眼 鸡心环", StringComparison.Ordinal) >= 0)
                {
                    thimble = body;
                    break;
                }
            }

            True(thimble != null, label + " 有鸡心环");
            Equal(thimble.Add.Count, 1, label + " 鸡心环为单个实体");
            EngineeringShape band = thimble.Add[0];
            True(band.Kind == EngineeringShapeKind.Extrude, label + " 鸡心环为普通拉伸");
            True(band.Points.Length >= 20, label + " 环带轮廓点足够（内外两条圆弧链）");
            True(band.Points.Length % 2 == 0, label + " 环带轮廓内外点数相等");
            True(band.ArcMiddles != null && band.ArcMiddles.Length >= band.Points.Length - 1,
                label + " 环带轮廓圆弧中点齐全");

            double minX = double.MaxValue;
            double maxX = double.MinValue;
            double minY = double.MaxValue;
            double maxY = double.MinValue;
            double minZ = double.MaxValue;
            double maxZ = double.MinValue;
            foreach (EngineeringPoint point in band.Points)
            {
                True(Finite(point), label + " 环带点有限");
                minX = Math.Min(minX, point.X);
                maxX = Math.Max(maxX, point.X);
                minY = Math.Min(minY, point.Y);
                maxY = Math.Max(maxY, point.Y);
                minZ = Math.Min(minZ, point.Z);
                maxZ = Math.Max(maxZ, point.Z);
            }

            double diagonal = Math.Sqrt(
                (maxX - minX) * (maxX - minX) + (maxY - minY) * (maxY - minY) +
                (maxZ - minZ) * (maxZ - minZ));
            True(diagonal > 40.0 && diagonal < 130.0,
                label + " 环带包住泪滴、不是退化成一条线（对角 " + diagonal.ToString("0.0") + "）");
            Equal(ChimneyCableCatalog.ThimbleWidthMm, 17.0, 1e-9, label + " 鸡心环带宽 17");
            True(ChimneyCableCatalog.ThimbleWallMm < ChimneyCableCatalog.RopeEyeOffsetMm,
                label + " 环带厚度小于绳中心外偏");

            // 绳眼工作段与主体圆柱的搭接必须够长：改成短搭接时放样截面间距只有 0.8，
            // 放样体退化，宿主报“相并失败”。
            True(ChimneyCableCatalog.RopeEyeStubMm - ChimneyCableCatalog.RopeEyeJointMm >= 100.0,
                label + " 绳眼与主体搭接长度足够");

            // 环带必须与钢索中心（拉索轴线）对齐：轮廓画在 y=0 再沿 +B 拉伸会让环带
            // 整体偏出半个带宽，宿主里看着就是“鸡心环偏了”。
            EngineeringBody rope = null;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name == "拉索 1（上层）")
                {
                    rope = body;
                    break;
                }
            }

            True(rope != null, label + " 有拉索主体");
            EngineeringShape cone = null;
            foreach (EngineeringShape shape in rope.Add)
            {
                if (shape.Kind == EngineeringShapeKind.Cone)
                {
                    cone = shape;
                    break;
                }
            }

            True(cone != null, label + " 拉索主体为圆锥");
            EngineeringPoint normal = band.Direction;
            double normalLength = Math.Sqrt(
                normal.X * normal.X + normal.Y * normal.Y + normal.Z * normal.Z);
            True(normalLength > 1e-9, label + " 环带拉伸方向非零");
            Equal(normalLength, ChimneyCableCatalog.ThimbleWidthMm, 1e-6, label + " 环带拉伸长度 = 带宽 17");

            double cx = 0.0, cy = 0.0, cz = 0.0;
            foreach (EngineeringPoint point in band.Points)
            {
                cx += point.X;
                cy += point.Y;
                cz += point.Z;
            }

            int bandPointCount = band.Points.Length;
            cx /= bandPointCount;
            cy /= bandPointCount;
            cz /= bandPointCount;

            // 轮廓画在 −B/2，加上半个带宽才是环带的中心平面。
            double midX = cx + normal.X * 0.5;
            double midY = cy + normal.Y * 0.5;
            double midZ = cz + normal.Z * 0.5;

            double axisX = cone.End.X - cone.Start.X;
            double axisY = cone.End.Y - cone.Start.Y;
            double axisZ = cone.End.Z - cone.Start.Z;
            double axisLength = Math.Sqrt(axisX * axisX + axisY * axisY + axisZ * axisZ);
            double along = ((midX - cone.Start.X) * axisX + (midY - cone.Start.Y) * axisY +
                (midZ - cone.Start.Z) * axisZ) / (axisLength * axisLength);
            double gapX = midX - (cone.Start.X + axisX * along);
            double gapY = midY - (cone.Start.Y + axisY * along);
            double gapZ = midZ - (cone.Start.Z + axisZ * along);
            double planeOffset = Math.Abs((gapX * normal.X + gapY * normal.Y + gapZ * normal.Z) / normalLength);
            True(planeOffset < 0.5,
                label + " 鸡心环与钢索中心对齐（平面偏差 " + planeOffset.ToString("0.000") + " mm）");
        }

        /// <summary>
        /// 材料用量：排气筒钢管按环形截面、拉索按建模路径、附件按规格表。
        /// </summary>
        private static void CheckMaterials(
            EngineeringPlan plan, ChimneyCableSpec spec, string label, int expectedAnchors)
        {
            ChimneyCableMaterials materials = ChimneyCableTakeoff.Of(spec, plan);

            // 排气筒钢管：π(D−t)t 的环形截面；长度 = 总高 − 基础预埋板顶面
            double areaSquareMeters = Math.PI * (spec.DiameterMm - spec.WallThicknessMm) *
                spec.WallThicknessMm / 1e6;
            double shellMeters = (spec.HeightMm - spec.ShellBottomMm) / 1000.0;
            Equal(materials.StackThicknessMm, spec.WallThicknessMm, 1e-9, label + " 材料壁厚一致");
            Equal(materials.StackMassKgPerMeter, areaSquareMeters * 7850.0, 1e-6, label + " 钢管 kg/m");
            Equal(materials.StackMassKg, materials.StackMassKgPerMeter * shellMeters, 1e-6,
                label + " 钢管总重（长度扣除基础顶面）");
            Equal(materials.StackSurfaceSquareMeters,
                Math.PI * spec.DiameterMm / 1000.0 * shellMeters, 1e-6, label + " 筒身外表面积");

            // 拉索：单根必须比两挂点直线距离长（含两端绳眼），但不会多出太多
            double straight = 0.0;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name != "拉索 1（上层）")
                {
                    continue;
                }

                foreach (EngineeringShape shape in body.Add)
                {
                    if (shape.Kind == EngineeringShapeKind.Cone)
                    {
                        straight = PointDistance(shape.Start, shape.End);
                    }
                }
            }

            if (!spec.GenerateCables)
            {
                // 自立式：拉索与地面固定全部为 0，材料行里不应出现拉索分项
                Equal(materials.StrandCount, 0, label + " 无拉索");
                Equal(materials.StrandLengthM, 0.0, 1e-12, label + " 无单根长度");
                Equal(materials.RopeMassKg, 0.0, 1e-12, label + " 无钢丝绳重量");
                Equal(materials.CollarCount, 0, label + " 无连接环板");
                Equal(materials.ThimbleCount, 0, label + " 无鸡心环");
                Equal(materials.ClipCount, 0, label + " 无绳夹");
                Equal(materials.AnchorCount, 0, label + " 无锚墩");
                Equal(materials.GroundRebarCount, 0, label + " 无地面吊环");
                True(materials.Lines.Count >= 2, label + " 材料用量分项齐全");
                True(materials.Summary().Length > 20, label + " 材料摘要非空");
                CheckMaterialRows(materials, spec, label);
                return;
            }

            True(materials.StrandLengthM > 0.0, label + " 有单根拉索长度");
            True(materials.StrandLengthM * 1000.0 > straight, label + " 单根长度含绳眼、长于主体");
            True(materials.StrandLengthM * 1000.0 < straight + 3000.0, label + " 单根长度没有被重复累计");
            Equal(materials.StrandCount, spec.CableCount, label + " 拉索根数");
            Equal(materials.RopeTotalLengthM, materials.StrandLengthM * spec.CableCount, 1e-9,
                label + " 拉索总长");
            Equal(materials.RopeMassKg, materials.RopeTotalLengthM * 0.857, 1e-9, label + " 拉索总重");

            // 附件数量
            Equal(materials.CollarCount, spec.CableCount, label + " 环板每根一件");
            Equal(materials.CollarUboltCount, spec.CableCount, label + " U 形螺栓每根一套");
            Equal(materials.CollarNutCount, spec.CableCount * 2, label + " 螺母每根两个");
            Equal(materials.ThimbleCount, spec.CableCount * 2, label + " 鸡心环每根两个");
            Equal(materials.ClipCount, spec.CableCount * 6, label + " 绳夹每根六套");
            Equal(materials.AnchorCount, expectedAnchors, label + " 锚墩个数");
            Equal(materials.GroundRebarCount, expectedAnchors, label + " 地面吊环个数");
            True(materials.CollarMassKg > 1.0 && materials.CollarMassKg < 2000.0,
                label + " 单件环板重量合理（" + materials.CollarMassKg.ToString("0.#") + " kg）");
            True(materials.AnchorMassKg > 0.1 && materials.AnchorMassKg < 20.0,
                label + " 单件锚墩重量合理（" + materials.AnchorMassKg.ToString("0.##") + " kg）");
            True(materials.GroundRebarLengthM > 2.0 && materials.GroundRebarLengthM < 2.5,
                label + " φ30 吊环展开长度合理（" + materials.GroundRebarLengthM.ToString("0.###") + " m）");
            Equal(materials.GroundRebarMassKg, materials.GroundRebarLengthM * 5.55, 1e-6,
                label + " 吊环重量按 φ30 5.55 kg/m");
            True(materials.Lines.Count >= 6, label + " 材料用量分项齐全");
            True(materials.Summary().Length > 20, label + " 材料摘要非空");
            CheckMaterialRows(materials, spec, label);
        }

        /// <summary>
        /// 材料统计表（页面“材料统计”页签）：行数、钢材小计、合计与逐行自洽。
        /// 基础与拉索各自按开关出现，行数 = 1 行钢管 + 5 行基础 + 8 行拉索。
        /// </summary>
        private static void CheckMaterialRows(
            ChimneyCableMaterials materials, ChimneyCableSpec spec, string label)
        {
            Equal(materials.Rows.Count,
                1 + (spec.GenerateBase ? 5 : 0) + (spec.GenerateCables ? 8 : 0),
                label + " 材料统计表行数");
            Equal(materials.SteelMassKg,
                materials.StackMassKg + materials.PlateMassKg * materials.PlateCount +
                materials.RibMassKg * materials.RibCount +
                materials.CollarMassKg * materials.CollarCount +
                materials.AnchorMassKg * materials.AnchorCount +
                materials.GroundRebarMassKg * materials.GroundRebarCount,
                1e-6, label + " 钢材小计");
            Equal(materials.TotalMassKg,
                materials.SteelMassKg + materials.RopeMassKg + materials.FoundationMassKg, 1e-6,
                label + " 材料合计 = 钢材 + 钢丝绳 + 混凝土基础");
            if (spec.GenerateBase)
            {
                Equal(materials.FoundationMassKg,
                    materials.FoundationVolumeM3 * 2400.0, 1e-6, label + " 混凝土按 2400 kg/m³");
                Equal(materials.FoundationVolumeM3,
                    spec.FoundationSideMm * spec.FoundationSideMm * spec.FoundationThicknessMm / 1e9,
                    1e-9, label + " 基础方量");
                Equal(materials.RibCount, spec.BoltCount, label + " 加劲肋与地脚螺栓同数");
                True(materials.PlateMassKg > 1.0, label + " 预埋板重量为正");
                True(materials.RibMassKg > 0.1 && materials.RibMassKg < 100.0,
                    label + " 单块加劲肋重量合理（" + materials.RibMassKg.ToString("0.##") + " kg）");
            }
            else
            {
                Equal(materials.FoundationVolumeM3, 0.0, 1e-12, label + " 不生成基础时无混凝土");
                Equal(materials.RibCount, 0, label + " 不生成基础时无加劲肋");
            }

            foreach (ChimneyCableMaterialRow row in materials.Rows)
            {
                True(!string.IsNullOrEmpty(row.Item) && !string.IsNullOrEmpty(row.Unit),
                    label + " 材料行项目/单位齐全");
                True(row.Quantity > 0.0, label + " 材料行数量为正（" + row.Item + "）");
                if (row.Weighed)
                {
                    True(row.UnitMassKg > 0.0 && row.TotalMassKg > 0.0,
                        label + " 计重行重量为正（" + row.Item + "）");
                    Equal(row.TotalMassKg, row.UnitMassKg * row.Quantity, 1e-6,
                        label + " 行总重 = 单重×数量（" + row.Item + "）");
                }
                else
                {
                    Equal(row.UnitMassText, "—", label + " 不计重行显示短横线（" + row.Item + "）");
                }
            }
        }

        /// <summary>
        /// 地面端固定：φ30 吊环埋入锚墩，环顶作吊点，绳眼挂在其上；
        /// 两层吊索时同一方位的两个吊环沿拉索方向相距 300（四腿平行、互不干涉）。
        /// </summary>
        private static void CheckGroundFixing(
            EngineeringPlan plan, ChimneyCableSpec spec, string label, int expectedRebars)
        {
            Equal(CountBodies(plan, "地面吊环"), expectedRebars, label + " 地面 φ30 吊环数量");
            Equal(CountBodies(plan, "地面锚墩"), expectedRebars, label + " 锚墩数量与吊环一致");
            True(ChimneyCableCatalog.GroundRingHalfMm + ChimneyCableCatalog.GroundRingBarMm / 2.0 <
                 ChimneyCableCatalog.AnchorRadiusMm,
                label + " 吊环落在锚墩以内（埋入而非悬空）");
            True(ChimneyCableCatalog.GroundRingHalfMm - ChimneyCableCatalog.GroundRingBarMm / 2.0 >
                 ChimneyCableCatalog.RopeDiameterMm / 2.0,
                label + " 绳眼能从两腿之间通过");

            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("地面吊环", StringComparison.Ordinal) < 0)
                {
                    continue;
                }

                EngineeringShape rebar = body.Add[0];
                True(rebar.Kind == EngineeringShapeKind.Sweep, label + " 吊环为扫掠");
                Equal(rebar.RadiusStart * 2.0, ChimneyCableCatalog.GroundRingBarMm, 1e-9,
                    label + " 吊环 φ30");
                Equal(CrownZ(rebar), ChimneyCableCatalog.GroundRingCrownMm, 1e-6,
                    label + " 环顶中心线在地上 85（外露 100）");

                // 路径顺序：左钩尖 → 左钩切点 → 左腿底 → 左肩 → 右肩 → 右腿底 → 右钩切点 → 右钩尖
                Equal(PointDistance(rebar.Points[3], rebar.Points[4]),
                    ChimneyCableCatalog.GroundRingHalfMm * 2.0, 1e-6, label + " 两腿中心距 130（净距 100）");
                Equal(rebar.Points[3].Z, ChimneyCableCatalog.GroundRingCrownMm -
                    ChimneyCableCatalog.GroundRingHalfMm, 1e-6, label + " 环顶半圆肩部标高");
                Equal(rebar.Points[2].Z, ChimneyCableCatalog.GroundRingLegBottomMm, 1e-6,
                    label + " 左腿直段下端");
                Equal(rebar.Points[5].Z, ChimneyCableCatalog.GroundRingLegBottomMm, 1e-6,
                    label + " 右腿直段下端");
                Equal(rebar.Points[0].Z, ChimneyCableCatalog.GroundRingHookTipMm, 1e-6,
                    label + " 左回钩端头 −810");
                Equal(rebar.Points[7].Z, ChimneyCableCatalog.GroundRingHookTipMm, 1e-6,
                    label + " 右回钩端头 −810");
                Equal(PointDistance(rebar.Points[0], rebar.Points[1]),
                    ChimneyCableCatalog.GroundRingHookTipMm - ChimneyCableCatalog.GroundRingLegBottomMm,
                    1e-6, label + " 回钩直肢长 37.5");
                True(PointDistance(rebar.Points[0], rebar.Points[7]) >
                     ChimneyCableCatalog.GroundRingHalfMm * 2.0 + 1.0, label + " 两个回钩向外弯");
                Equal(Math.Abs(rebar.Points[0].X - CrownPoint(rebar).X),
                    Math.Abs(rebar.Points[7].X - CrownPoint(rebar).X), 1e-6, label + " 吊环左右对称");

                // 最低点（回钩外缘）必须正好落到埋深 900
                double lowest = double.MaxValue;
                foreach (EngineeringPoint point in rebar.Points)
                {
                    lowest = Math.Min(lowest, point.Z);
                }

                if (rebar.ArcMiddles != null)
                {
                    foreach (EngineeringPoint? middle in rebar.ArcMiddles)
                    {
                        if (middle.HasValue)
                        {
                            lowest = Math.Min(lowest, middle.Value.Z);
                        }
                    }
                }

                Equal(lowest - ChimneyCableCatalog.GroundRingBarMm / 2.0,
                    -ChimneyCableCatalog.GroundRingEmbeddedMm, 1e-6, label + " 埋深 900（最低外缘 −900）");
            }

            // 逐个方位核对“绳眼挂在弯拱顶点上”和“绳眼高于锚墩顶面”
            double padTop = ChimneyCableCatalog.AnchorHeightMm - ChimneyCableCatalog.AnchorBuriedDepthMm;
            double upperRadius = 0.0;
            double lowerRadius = 0.0;
            for (int index = 1; index <= ChimneyCableCatalog.CableAzimuthDegrees.Length; index++)
            {
                foreach (string layer in new[] { "（上层）", "（中间层）" })
                {
                    EngineeringBody rope = FindBody(plan, "拉索 " + index + layer);
                    if (rope == null)
                    {
                        continue;
                    }

                    EngineeringBody rebar = FindBody(plan, "拉索 " + index + " 地面吊环" +
                        (expectedRebars > 3 ? layer : ""));
                    True(rebar != null, label + " 拉索 " + index + layer + " 有地面 φ30 吊环");

                    EngineeringShape loft = null;
                    double loftLowest = double.MaxValue;
                    foreach (EngineeringShape shape in rope.Add)
                    {
                        if (shape.Kind != EngineeringShapeKind.Loft)
                        {
                            continue;
                        }

                        // 一根拉索两端各一个绳眼，取靠近地面的那个。
                        double lowestPoint = double.MaxValue;
                        foreach (EngineeringPoint point in shape.Points)
                        {
                            lowestPoint = Math.Min(lowestPoint, point.Z);
                        }

                        if (lowestPoint < loftLowest)
                        {
                            loftLowest = lowestPoint;
                            loft = shape;
                        }
                    }

                    True(loft != null, label + " 拉索 " + index + layer + " 有绳眼");
                    EngineeringShape ground = rebar.Add[0];
                    EngineeringPoint crownPoint = CrownPoint(ground);
                    double nearest = double.MaxValue;
                    double lowest = double.MaxValue;
                    foreach (EngineeringPoint point in loft.Points)
                    {
                        nearest = Math.Min(nearest, PointDistance(point, crownPoint));
                        lowest = Math.Min(lowest, point.Z);
                    }

                    True(nearest > ChimneyCableCatalog.GroundEyeOffsetMm - 0.6 &&
                         nearest < ChimneyCableCatalog.GroundEyeOffsetMm + 0.8,
                        label + " 拉索 " + index + layer + " 绳眼挂在环顶上（轴距 " + Format(nearest) + "）");
                    True(lowest - ChimneyCableCatalog.RopeRadiusMm > padTop + 3.0,
                        label + " 拉索 " + index + layer + " 绳眼高于锚墩顶面");

                    double radius = Math.Sqrt(
                        crownPoint.X * crownPoint.X + crownPoint.Y * crownPoint.Y);
                    if (layer == "（上层）")
                    {
                        upperRadius = radius;
                    }
                    else
                    {
                        lowerRadius = radius;
                    }

                    double expected = layer == "（上层）" && expectedRebars > 3
                        ? spec.OuterRadiusMm + ChimneyCableCatalog.GroundRingSpacingMm
                        : spec.OuterRadiusMm;
                    Equal(radius, expected, 1e-6, label + " 固定点半径");
                }
            }

            if (expectedRebars > 3)
            {
                Equal(upperRadius - lowerRadius, ChimneyCableCatalog.GroundRingSpacingMm, 1e-6,
                    label + " 两层两个吊环沿拉索方向相距 300");
            }
        }

        private static int CountUpperRebars(EngineeringPlan plan)
        {
            int count = 0;
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("吊筋", StringComparison.Ordinal) >= 0 &&
                    body.Name.IndexOf("地面吊环", StringComparison.Ordinal) < 0)
                {
                    count++;
                }
            }

            return count;
        }

        private static EngineeringBody FindBody(EngineeringPlan plan, string name)
        {
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name == name)
                {
                    return body;
                }
            }

            return null;
        }

        private static EngineeringPoint CrownPoint(EngineeringShape rebar)
        {
            EngineeringPoint best = default(EngineeringPoint);
            double bestZ = double.MinValue;
            foreach (EngineeringPoint? middle in rebar.ArcMiddles)
            {
                if (middle.HasValue && middle.Value.Z > bestZ)
                {
                    bestZ = middle.Value.Z;
                    best = middle.Value;
                }
            }

            return best;
        }

        private static double CrownZ(EngineeringShape rebar)
        {
            return CrownPoint(rebar).Z;
        }

        private static double LowestLegZ(EngineeringShape rebar)
        {
            double lowest = double.MaxValue;
            foreach (EngineeringPoint point in rebar.Points)
            {
                lowest = Math.Min(lowest, point.Z);
            }

            return lowest;
        }

        private static void CheckShapes(EngineeringPlan plan, string label)        {
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

            if (shape.Kind == EngineeringShapeKind.Loft)
            {
                True(shape.Points.Length >= 2, label + " 放样路径点足够");
                True(shape.RadiusStart > 0, label + " 放样半径正值");
                True(Math.Abs(shape.AxisX.X) + Math.Abs(shape.AxisX.Y) + Math.Abs(shape.AxisX.Z) > 1e-6,
                    label + " 放样平面法向非零");
            }

            if (shape.Kind == EngineeringShapeKind.SplineSweep)
            {
                True(shape.Points.Length >= 3, label + " 光滑路径拟合点足够");
                True(shape.RadiusStart > 0, label + " 光滑扫掠半径正值");
            }

            if (shape.Kind == EngineeringShapeKind.SplineBand)
            {
                True(shape.Points.Length >= 3, label + " 环带拟合点足够");
                True(shape.RadiusStart > 0 && shape.RadiusEnd > 0, label + " 环带宽度与厚度正值");
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
                    case EngineeringShapeKind.TorusArc:
                        bounds.Include(new EngineeringPoint(shape.Start.X - shape.MajorRadius - shape.MinorRadius,
                            shape.Start.Y - shape.MajorRadius - shape.MinorRadius, shape.Start.Z - shape.MinorRadius));
                        bounds.Include(new EngineeringPoint(shape.Start.X + shape.MajorRadius + shape.MinorRadius,
                            shape.Start.Y + shape.MajorRadius + shape.MinorRadius, shape.Start.Z + shape.MinorRadius));
                        break;
                    case EngineeringShapeKind.SplineBand:
                    {
                        double extent = Math.Max(shape.RadiusStart, shape.RadiusEnd) / 2.0;
                        foreach (EngineeringPoint point in shape.Points)
                        {
                            bounds.Include(point.Offset(-extent, -extent, -extent));
                            bounds.Include(point.Offset(extent, extent, extent));
                        }

                        break;
                    }
                    case EngineeringShapeKind.Sweep:
                    case EngineeringShapeKind.Loft:
                    case EngineeringShapeKind.SplineSweep:
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
