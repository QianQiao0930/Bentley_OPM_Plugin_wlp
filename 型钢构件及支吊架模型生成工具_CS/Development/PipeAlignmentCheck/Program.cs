using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using SteelSectionProbe.PipeAlignment;

namespace SteelSectionProbe.PipeAlignmentCheck
{
    /// <summary>
    /// 管道标高对齐插件 · 纯计算层离线自检。
    /// <para>
    /// 用例分两组：
    /// <list type="bullet">
    /// <item>T01～T16：对应《管道标高对齐插件开发指南》§38 测试表的 T01～T16；
    /// 表里的 T17～T20（Undo / 保存重开模型 / Connectivity Check / Isometric）依赖
    /// OpenPlant Modeler 运行时，**本离线工程无法验证**，必须在 OPM 里实测。</item>
    /// <item>S01～S08：超出指南测试表的补充断言（单位服务、ShiftedByZ、退化几何、
    /// 连接分类器、配置解析容错、ReadyInstanceIds 等）。</item>
    /// <item>§34 算例：指南 §34 的端到端算例，ΔZ = 4890.5 − 5146 = −255.5 mm。</item>
    /// </list>
    /// </para>
    /// <para>
    /// 全部用例只调用纯计算层（Domain\*.cs + 7 个 Services 文件），不触碰任何 Bentley 类型。
    /// 编译语言版本为 C# 7.3（与链接进来的源码一致）。
    /// </para>
    /// </summary>
    internal static partial class Program
    {
        /// <summary>浮点比较容差（长度量，单位 mm）。</summary>
        private const double Len = 1.0e-9;

        /// <summary>浮点比较容差（比例等无量纲量）。</summary>
        private const double Tiny = 1.0e-12;

        private static int Main()
        {
            // 输出含中文用例名：固定 UTF-8，避免控制台代码页/重定向导致乱码。
            try
            {
                Console.OutputEncoding = new UTF8Encoding(false);
            }
            catch (Exception)
            {
                // 某些宿主不允许改编码：忽略，不影响断言结果。
            }

            List<TestCase> cases = BuildCases();
            AddBatchCases(cases); AddReferenceLineCases(cases); AddOffsetCases(cases);

            int passed = 0;
            foreach (TestCase testCase in cases)
            {
                try
                {
                    testCase.Body();
                    passed++;
                    Console.WriteLine("PASS " + testCase.Name);
                }
                catch (Exception error)
                {
                    Console.WriteLine("FAIL " + testCase.Name + " —— " + error.Message);
                }
            }

            Console.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "共 {0} 条，通过 {1} 条", cases.Count, passed));
            return passed == cases.Count ? 0 : 1;
        }

        private sealed class TestCase
        {
            internal TestCase(string name, Action body)
            {
                Name = name;
                Body = body;
            }

            internal string Name { get; private set; }

            internal Action Body { get; private set; }
        }

        // ==================================================================
        // 构造辅助：全部按源码里的**真实**成员名设置
        // ==================================================================

        /// <summary>给一根管接上一个连接端点（Move Group 展开用例用）。</summary>
        private static void Connect(PipeInfo pipe, string otherInstanceId, string otherClassName, int portIndex)
        {
            if (pipe.Topology == null) pipe.Topology = new PipeTopology();
            pipe.Topology.IsKnown = true;
            pipe.Topology.Connections.Add(new PipeConnection(portIndex, otherInstanceId, otherClassName, null));
        }

        /// <summary>构造一根水平直管（中心线沿 +X，两端同标高）。</summary>
        private static PipeInfo Pipe(ulong elementId, double zcMm, double outsideDiameterMm,
            string className)
        {
            PipeInfo pipe = new PipeInfo();
            pipe.ElementId = elementId;
            pipe.InstanceId = "idx-" + elementId.ToString(CultureInfo.InvariantCulture);
            pipe.ClassName = className;
            pipe.OutsideDiameterMm = outsideDiameterMm;
            pipe.Axis = new PipeAxis(0.0, 0.0, zcMm, 1000.0, 0.0, zcMm);
            return pipe;
        }

        private static PipeInfo Pipe(ulong elementId, double zcMm, double outsideDiameterMm)
        {
            return Pipe(elementId, zcMm, outsideDiameterMm, "PIPE");
        }

        private static PipeAlignOptions Options()
        {
            return new PipeAlignOptions();
        }

        /// <summary>把目标管集合包成一个请求（基准管不再重复传给目标管）。</summary>
        private static AlignmentRequest Request(PipeInfo reference, params PipeInfo[] targets)
        {
            return new AlignmentRequest(reference, new List<PipeInfo>(targets),
                AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
        }

        private static AlignmentPlan BuildPlan(PipeInfo reference, params PipeInfo[] targets)
        {
            return PipeAlignPlanner.BuildPlan(Request(reference, targets));
        }

        // ==================================================================
        // 断言辅助：失败时给出「实际值 / 期望值」
        // ==================================================================

        private static void True(bool condition, string message)
        {
            if (!condition) throw new Exception("断言不成立：" + message);
        }

        private static void False(bool condition, string message)
        {
            True(!condition, message);
        }

        private static void Near(double actual, double expected, double tolerance, string what)
        {
            double difference = Math.Abs(actual - expected);
            if (double.IsNaN(difference) || difference > tolerance)
            {
                throw new Exception(string.Format(CultureInfo.InvariantCulture,
                    "{0}：实际 {1:G17}，期望 {2:G17}，差 {3:G17} > 容差 {4:G17}",
                    what, actual, expected, difference, tolerance));
            }
        }

        private static void Eq(object actual, object expected, string what)
        {
            bool same = actual == null ? expected == null : actual.Equals(expected);
            if (!same)
            {
                throw new Exception(string.Format(CultureInfo.InvariantCulture,
                    "{0}：实际 {1}，期望 {2}", what,
                    actual == null ? "<null>" : actual.ToString(),
                    expected == null ? "<null>" : expected.ToString()));
            }
        }

        private static void NotEmpty(string text, string what)
        {
            if (string.IsNullOrEmpty(text))
                throw new Exception(what + "：实际为空或 null，期望非空文本");
        }

        // ==================================================================
        // 用例清单
        // ==================================================================

        private static List<TestCase> BuildCases()
        {
            List<TestCase> cases = new List<TestCase>();

            // ------------------------------------------------------------------
            // T01 指南 §16 / §34：两根**相同外径**水平管，Bottom 模式下管底完全对齐。
            // ΔZ 应等于基准管底 − 目标管底；外径相同 ⇒ ΔZ 等于中心标高之差。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T01 相同外径水平管管底对齐", delegate
            {
                PipeInfo reference = Pipe(901, 5000.0, 219.0);
                PipeInfo target = Pipe(101, 5200.0, 219.0);

                double referenceBottom = ElevationCalculator.GetAlignmentElevation(
                    reference, AlignmentMode.Bottom, SurfaceMode.Pipe);
                double targetBottom = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Bottom, SurfaceMode.Pipe);
                Near(referenceBottom, 4890.5, Len, "基准管管底标高");
                Near(targetBottom, 5090.5, Len, "目标管管底标高");

                AlignmentPlan plan = BuildPlan(reference, target);
                Near(plan.ReferenceElevationMm, 4890.5, Len, "计划里的基准标高");
                AlignmentPlanItem item = plan.Items[0];
                Eq(item.Status, PlanItemStatus.Ready, "计划状态");
                Near(item.DeltaZmm, -200.0, Len, "ΔZ");

                // 移动后两根管的管底必须重合（这才是「对齐」的定义）。
                double movedBottom = ElevationCalculator.GetAlignmentElevation(
                    item.Pipe, AlignmentMode.Bottom, SurfaceMode.Pipe) + item.DeltaZmm;
                Near(movedBottom, referenceBottom, Len, "移动后目标管管底标高");
            }));

            // ------------------------------------------------------------------
            // T02 指南 §10 / §16：两根**不同外径**水平管，Bottom 模式对齐的是**外表面底部**，
            // 不是中心线 —— ΔZ ≠ 中心标高之差（该差值正是有效外径之差的一半）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T02 不同外径水平管对齐外表面底部而非中心线", delegate
            {
                PipeInfo reference = Pipe(902, 5000.0, 219.0);
                PipeInfo target = Pipe(102, 5200.0, 108.0);

                double referenceBottom = ElevationCalculator.GetAlignmentElevation(
                    reference, AlignmentMode.Bottom, SurfaceMode.Pipe);
                double targetBottom = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Bottom, SurfaceMode.Pipe);
                Near(referenceBottom, 4890.5, Len, "基准管管底标高 (5000 − 219/2)");
                Near(targetBottom, 5146.0, Len, "目标管管底标高 (5200 − 108/2)");

                AlignmentPlan plan = BuildPlan(reference, target);
                AlignmentPlanItem item = plan.Items[0];
                Near(item.DeltaZmm, -255.5, Len, "ΔZ（管底对齐）");

                // 中心线差值 ≠ ΔZ，且差正好是两根管半径之差（55.5 mm）。
                double centerLineDelta = ElevationCalculator.ComputeDeltaZ(
                    reference.Axis.CenterElevationMm, target.Axis.CenterElevationMm);
                Near(centerLineDelta, -200.0, Len, "中心线标高差");
                Near(centerLineDelta - item.DeltaZmm, 55.5, Len, "中心线差与管底差之差");

                // 中心线绝不重合：证明插件没有偷懒按中心线对齐。
                double movedCenter = target.Axis.CenterElevationMm + item.DeltaZmm;
                Near(movedCenter, 4944.5, Len, "移动后目标管中心标高");
                True(Math.Abs(movedCenter - reference.Axis.CenterElevationMm) > 1.0,
                    "Bottom 模式下移动后的中心线不应与基准管中心线重合");
            }));

            // ------------------------------------------------------------------
            // T03 指南 §3.1 / §16：Center 模式 —— 中心线标高相同，ΔZ = 基准 Zc − 目标 Zc。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T03 Center 模式中心线标高相同", delegate
            {
                PipeInfo reference = Pipe(903, 5000.0, 219.0);
                PipeInfo target = Pipe(103, 5200.0, 108.0);

                AlignmentRequest request = new AlignmentRequest(reference,
                    new List<PipeInfo> { target }, AlignmentMode.Center, SurfaceMode.Pipe, Options());
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(request);
                AlignmentPlanItem item = plan.Items[0];

                Near(plan.ReferenceElevationMm, 5000.0, Len, "Center 模式的基准标高（应为 Zc）");
                Near(item.CurrentElevationMm, 5200.0, Len, "Center 模式的目标标高（应为 Zc）");
                Near(item.DeltaZmm, -200.0, Len, "ΔZ（中心线对齐）");

                AlignmentPlanItem moved = new AlignmentPlanItem(target, AlignmentMode.Center, SurfaceMode.Pipe);
                moved.DeltaZmm = item.DeltaZmm;
                Near(moved.TargetAxis.CenterElevationMm, reference.Axis.CenterElevationMm, Len,
                    "移动后目标管中心线标高");
            }));

            // ------------------------------------------------------------------
            // T04 指南 §16：Top 模式 —— 管顶标高相同（Zc + Deff/2）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T04 Top 模式管顶标高相同", delegate
            {
                PipeInfo reference = Pipe(904, 5000.0, 219.0);
                PipeInfo target = Pipe(104, 5200.0, 108.0);

                double referenceTop = ElevationCalculator.GetAlignmentElevation(
                    reference, AlignmentMode.Top, SurfaceMode.Pipe);
                double targetTop = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Top, SurfaceMode.Pipe);
                Near(referenceTop, 5109.5, Len, "基准管管顶标高 (5000 + 219/2)");
                Near(targetTop, 5254.0, Len, "目标管管顶标高 (5200 + 108/2)");

                AlignmentRequest request = new AlignmentRequest(reference,
                    new List<PipeInfo> { target }, AlignmentMode.Top, SurfaceMode.Pipe, Options());
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(request);
                AlignmentPlanItem item = plan.Items[0];
                Near(item.DeltaZmm, -144.5, Len, "ΔZ（管顶对齐）");

                double movedTop = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Top, SurfaceMode.Pipe) + item.DeltaZmm;
                Near(movedTop, referenceTop, Len, "移动后目标管管顶标高");
            }));

            // ------------------------------------------------------------------
            // T05 指南 T05 / PipeAlignOptions.AlignmentToleranceMm：
            // |ΔZ| ≤ AlignmentToleranceMm 时状态必须是 AlreadyAligned（而不是去「移动 0」）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T05 已对齐时状态为 AlreadyAligned", delegate
            {
                PipeInfo reference = Pipe(905, 5000.0, 219.0);
                // 管底只差 0.0005 mm（< 默认容差 0.001 mm），方向向上（ΔZ > 0 的边界）。
                PipeInfo target = Pipe(105, 4999.9995, 219.0);

                AlignmentPlan plan = BuildPlan(reference, target);
                AlignmentPlanItem item = plan.Items[0];
                Near(item.DeltaZmm, 0.0005, Len, "ΔZ（小于对齐容差）");
                True(Math.Abs(item.DeltaZmm) <= Options().AlignmentToleranceMm,
                    "ΔZ 的绝对值应不大于 AlignmentToleranceMm");
                Eq(item.Status, PlanItemStatus.AlreadyAligned, "计划状态（|ΔZ| ≤ 容差）");
                Eq(plan.AlreadyAlignedCount, 1, "AlreadyAlignedCount");
                Eq(plan.ReadyCount, 0, "ReadyCount（已对齐的不应算作待移动）");
                Eq(item.WillMove, false, "WillMove（已对齐时不得移动）");
                NotEmpty(item.Describe(), "计划条目中文摘要");
            }));

            // ------------------------------------------------------------------
            // T06 指南 §9：目标管高于基准管 ⇒ ΔZ 为负（必须向下移动）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T06 目标管高于基准管时 ΔZ 为负", delegate
            {
                PipeInfo reference = Pipe(906, 5000.0, 219.0);
                PipeInfo target = Pipe(106, 5400.0, 219.0);

                AlignmentPlan plan = BuildPlan(reference, target);
                AlignmentPlanItem item = plan.Items[0];
                Eq(item.Status, PlanItemStatus.Ready, "计划状态");
                True(item.DeltaZmm < 0.0, string.Format(CultureInfo.InvariantCulture,
                    "ΔZ 应为负：实际 {0:G17}", item.DeltaZmm));
                Near(item.DeltaZmm, -400.0, Len, "ΔZ");

                double movedCenter = target.Axis.CenterElevationMm + item.DeltaZmm;
                True(movedCenter < target.Axis.CenterElevationMm,
                    "移动后中心标高应下降：移动后 " + movedCenter.ToString("G17", CultureInfo.InvariantCulture));
            }));

            // ------------------------------------------------------------------
            // T07 指南 §9：目标管低于基准管 ⇒ ΔZ 为正（必须向上移动）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T07 目标管低于基准管时 ΔZ 为正", delegate
            {
                PipeInfo reference = Pipe(907, 5000.0, 219.0);
                PipeInfo target = Pipe(107, 4600.0, 219.0);

                AlignmentPlan plan = BuildPlan(reference, target);
                AlignmentPlanItem item = plan.Items[0];
                Eq(item.Status, PlanItemStatus.Ready, "计划状态");
                True(item.DeltaZmm > 0.0, string.Format(CultureInfo.InvariantCulture,
                    "ΔZ 应为正：实际 {0:G17}", item.DeltaZmm));
                Near(item.DeltaZmm, 400.0, Len, "ΔZ");

                double movedCenter = target.Axis.CenterElevationMm + item.DeltaZmm;
                True(movedCenter > target.Axis.CenterElevationMm,
                    "移动后中心标高应上升：移动后 " + movedCenter.ToString("G17", CultureInfo.InvariantCulture));
            }));

            // ------------------------------------------------------------------
            // T08 指南 §27：多根目标管**各自独立**计算 ΔZ（不同外径 + 不同标高混合）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T08 多根目标管独立计算 ΔZ", delegate
            {
                PipeInfo reference = Pipe(908, 5000.0, 219.0);
                PipeInfo a = Pipe(108, 5200.0, 108.0);
                PipeInfo b = Pipe(109, 4800.0, 325.0);
                PipeInfo c = Pipe(110, 5300.0, 159.0);

                AlignmentPlan plan = BuildPlan(reference, a, b, c);
                Eq(plan.Items.Count, 3, "计划条目数");
                Eq(plan.ReadyCount, 3, "ReadyCount");
                Eq(plan.SkippedCount, 0, "SkippedCount");
                Eq(plan.AlreadyAlignedCount, 0, "AlreadyAlignedCount");

                // 基准管底 = 5000 − 109 = 4890.5
                Near(plan.Items[0].DeltaZmm, 4890.5 - 5146.0, Len, "A 管 ΔZ（Do=108, Zc=5200）");
                Near(plan.Items[1].DeltaZmm, 4890.5 - 4637.5, Len, "B 管 ΔZ（Do=325, Zc=4800）");
                Near(plan.Items[2].DeltaZmm, 4890.5 - 5220.5, Len, "C 管 ΔZ（Do=159, Zc=5300）");
            }));

            // ------------------------------------------------------------------
            // T09 指南 §11 / §12：斜管 —— IsHorizontal 判否，ValidateTargetPipe 不通过，
            // 且原因文本非空（必须是面向用户的说明，不能静默跳过）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T09 斜管判否且校验不通过", delegate
            {
                PipeAxis sloped = new PipeAxis(0.0, 0.0, 5000.0, 1000.0, 0.0, 5200.0);
                PipeInfo target = new PipeInfo();
                target.ElementId = 111;
                target.InstanceId = "idx-111";
                target.ClassName = "PIPE";
                target.OutsideDiameterMm = 219.0;
                target.Axis = sloped;

                False(sloped.IsHorizontal(Options().HorizontalToleranceMm),
                    "ΔZ=200mm 的管不应被判为水平管");
                True(sloped.IsHorizontal(500.0), "容差放大到 500mm 后应判为水平（容差来自配置，不得写死）");
                Near(sloped.DeltaZmm, 200.0, Len, "斜管 DeltaZmm");

                ValidationOutcome outcome = PipeValidationService.ValidateTargetPipe(
                    target, AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
                False(outcome.IsValid, "斜管必须校验不通过");
                NotEmpty(outcome.Reason, "斜管不通过原因");
                True(outcome.Reason.IndexOf("水平", StringComparison.Ordinal) >= 0,
                    "斜管原因里应说明「水平管」判据：实际「" + outcome.Reason + "」");

                // 经过 BuildPlan 也必须落到 Skipped，且带原因。
                AlignmentPlan plan = BuildPlan(Pipe(909, 5000.0, 219.0), target);
                Eq(plan.Items[0].Status, PlanItemStatus.Skipped, "计划状态");
                NotEmpty(plan.Items[0].SkipReason, "计划里的跳过原因");
            }));

            // ------------------------------------------------------------------
            // T10 指南 §2.1：非 PIPE 对象（EC 类名不符合）必须校验不通过。
            // 注意：PipeValidationService 用 PipeConnectionClassifier 认类，措辞可能是
            // 「不是管道」或「不是直管」，断言只认语义（必须说明 EC 类名、必须列 VALVE）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T10 非 PIPE 类对象校验不通过", delegate
            {
                PipeInfo valve = Pipe(112, 5000.0, 219.0, "VALVE");
                ValidationOutcome outcome = PipeValidationService.ValidateTargetPipe(
                    valve, AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
                False(outcome.IsValid, "VALVE 类对象必须校验不通过");
                NotEmpty(outcome.Reason, "非管道对象的不通过原因");
                True(outcome.Reason.IndexOf("不是管道", StringComparison.Ordinal) >= 0
                    || outcome.Reason.IndexOf("不是直管", StringComparison.Ordinal) >= 0,
                    "原因应说明对象不是管道/直管：实际「" + outcome.Reason + "」");
                True(outcome.Reason.IndexOf("VALVE", StringComparison.Ordinal) >= 0,
                    "原因里应带上实际的 EC 类名：实际「" + outcome.Reason + "」");

                // PIPE 类的兄弟类（PIPE_ELBOW 等）类名里同样含 PIPE，必须单独拒绝。
                PipeInfo elbow = Pipe(130, 5000.0, 219.0, "PIPE_ELBOW");
                False(PipeValidationService.ValidateTargetPipe(
                    elbow, AlignmentMode.Bottom, SurfaceMode.Pipe, Options()).IsValid,
                    "PIPE_ELBOW（类名含 PIPE 但属管件）必须校验不通过");

                // 空类名同样不通过。
                PipeInfo blank = Pipe(131, 5000.0, 219.0, null);
                False(PipeValidationService.ValidateTargetPipe(
                    blank, AlignmentMode.Bottom, SurfaceMode.Pipe, Options()).IsValid,
                    "类名为空的对象必须校验不通过");
            }));

            // ------------------------------------------------------------------
            // T11 指南 §15 / §27：锁定对象（IsLocked）必须校验不通过，且进计划后被跳过。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T11 锁定对象校验不通过", delegate
            {
                PipeInfo locked = Pipe(132, 5200.0, 108.0);
                locked.IsLocked = true;

                ValidationOutcome outcome = PipeValidationService.ValidateTargetPipe(
                    locked, AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
                False(outcome.IsValid, "IsLocked=true 必须校验不通过");
                NotEmpty(outcome.Reason, "锁定对象的不通过原因");
                True(outcome.Reason.IndexOf("锁定", StringComparison.Ordinal) >= 0,
                    "原因应说明已锁定：实际「" + outcome.Reason + "」");

                AlignmentPlan plan = BuildPlan(Pipe(910, 5000.0, 219.0), locked);
                Eq(plan.Items[0].Status, PlanItemStatus.Skipped, "计划状态");
                NotEmpty(plan.Items[0].SkipReason, "计划里的跳过原因");
            }));

            // ------------------------------------------------------------------
            // T12 指南 §14 / §15：参考文件里的对象（IsFromReference）不可修改，必须不通过。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T12 参考文件对象校验不通过", delegate
            {
                PipeInfo fromReference = Pipe(115, 5200.0, 108.0);
                fromReference.IsFromReference = true;

                ValidationOutcome outcome = PipeValidationService.ValidateTargetPipe(
                    fromReference, AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
                False(outcome.IsValid, "IsFromReference=true 必须校验不通过");
                NotEmpty(outcome.Reason, "参考文件对象的不通过原因");
                True(outcome.Reason.IndexOf("参考文件", StringComparison.Ordinal) >= 0,
                    "原因应说明位于参考文件：实际「" + outcome.Reason + "」");

                // 只读元素是另一条独立判据，同样必须拒绝。
                PipeInfo readOnlyPipe = Pipe(116, 5200.0, 108.0);
                readOnlyPipe.IsReadOnly = true;
                False(PipeValidationService.ValidateTargetPipe(
                    readOnlyPipe, AlignmentMode.Bottom, SurfaceMode.Pipe, Options()).IsValid,
                    "IsReadOnly=true 必须校验不通过");
            }));

            // ------------------------------------------------------------------
            // T13 指南 §21 / §22 Safe Mode：目标管存在连到「不在移动集合里」的对象的连接时
            // 必须被跳过，原因非空；且跳过后与之相连的另一根目标管要跟着被跳过（迭代到不动点）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T13 两端固定连接在 Safe Mode 下被跳过", delegate
            {
                PipeInfo reference = Pipe(911, 5000.0, 219.0);

                PipeInfo a = Pipe(117, 5200.0, 219.0);
                a.InstanceId = "A";
                PipeInfo b = Pipe(118, 5300.0, 219.0);
                b.InstanceId = "B";

                List<PipeConnection> aConnections = new List<PipeConnection>();
                // 口 1 → B（本批会一起移动，不阻断）
                aConnections.Add(new PipeConnection(0, "B", "PIPE", null));
                // 口 2 → 固定设备（不在移动集合里，必须阻断）
                aConnections.Add(new PipeConnection(1, "FIXED-EQUIP", "NOZZLE", null));
                a.Topology = new PipeTopology(aConnections);

                List<PipeConnection> bConnections = new List<PipeConnection>();
                bConnections.Add(new PipeConnection(0, "A", "PIPE", null));
                bConnections.Add(new PipeConnection(1, "FIXED-VALVE", "VALVE", null));
                b.Topology = new PipeTopology(bConnections);

                // 单看 A：对端在移动集合里的连接不阻断，直连固定对象的那条阻断。
                PipeConnection blocking = a.Topology.FindBlockingConnection(new List<string> { "A", "B" });
                True(blocking != null, "A 应存在阻断连接");
                Eq(blocking.OtherInstanceId, "FIXED-EQUIP", "阻断连接的实例 ID");

                AlignmentPlan plan = BuildPlan(reference, a, b);
                Eq(plan.SkippedCount, 2, "SkippedCount（A 与 B 都应被跳过）");
                Eq(plan.ReadyCount, 0, "ReadyCount");
                foreach (AlignmentPlanItem item in plan.Items)
                {
                    Eq(item.Status, PlanItemStatus.Skipped, "计划状态");
                    NotEmpty(item.SkipReason, "跳过原因");
                }
                NotEmpty(plan.Items[0].SkipReason, "A 的跳过原因");
                NotEmpty(plan.Items[1].SkipReason, "B 的跳过原因");
            }));

            // ------------------------------------------------------------------
            // T14 指南 §17：单位为 mm —— PropertyLengthScale = 1 时长度**不放大**。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T14 PropertyLengthScale=1 时长度不放大", delegate
            {
                PipeInfo pipe = Pipe(119, 5000.0, 219.0);
                pipe.PropertyLengthScale = 1.0;
                pipe.PropertyLengthScaleSource = "calibrated";

                Eq(pipe.PropertyLengthScale, 1.0, "PropertyLengthScale");

                double? raw = 1000.0;
                double? millimeters = LengthUnitCalibrator.ToMillimeter(raw, pipe.PropertyLengthScale);
                Eq(millimeters.HasValue, true, "换算结果是否有值");
                Near(millimeters.Value, 1000.0, Len, "1000（mm 存储）× 1.0");

                // 标定路径也必须给出 1.0（属性值就存毫米）。
                LengthScale scale = LengthUnitCalibrator.Detect(1500.0, 1500.0);
                True(scale != null, "属性长度与几何长度一致时应标定成功");
                Eq(scale.Scale, LengthUnitCalibrator.ScaleMillimeter, "标定出的比例");
                Eq(scale.Source, LengthScaleSource.Calibrated, "标定来源");
                Near(scale.Scale, 1.0, Tiny, "标定比例数值");

                // Resolve 在"属性存毫米 + 几何长度一致"时不放大，且来源为自动标定。
                LengthScale resolved = LengthUnitCalibrator.Resolve(1500.0, 1500.0, null);
                Near(resolved.Scale, 1.0, Tiny, "Resolve 自动标定比例（mm 存储）");
                Eq(resolved.Source, LengthScaleSource.Calibrated, "Resolve 来源");
                True(resolved.UnitText == "毫米", "单位文本应为毫米：实际「" + resolved.UnitText + "」");

                // 换算后再走一遍标高计算：Do 已经是 mm，不能被 PropertyLengthScale 二次放大。
                PipeInfo reference = Pipe(919, 5000.0, 219.0);
                PipeInfo target = Pipe(122, 5200.0, 219.0);
                target.PropertyLengthScale = 1.0;
                AlignmentPlan plan = BuildPlan(reference, target);
                Near(plan.Items[0].DeltaZmm, -200.0, Len, "ΔZ（Do 已为 mm，不得被比例二次放大）");
            }));

            // ------------------------------------------------------------------
            // T15 指南 §17 结尾：Imperial / 米制存储 —— 长度属性按米存储时 Detect 返回 1000；
            // Resolve 的 Manual 分支直接采用手动值（不做任何猜测）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T15 米存储时 Detect 返回 1000 且 Manual 直采", delegate
            {
                // 6 米几何长度，属性存 6.0 ⇒ 只有 ×1000 对得上。
                LengthScale meters = LengthUnitCalibrator.Detect(6.0, 6000.0);
                True(meters != null, "米存储必须能标定成功");
                Eq(meters.Scale, LengthUnitCalibrator.ScaleMeter, "标定出的比例");
                Near(meters.Scale, 1000.0, Tiny, "比例数值");
                Eq(meters.Source, LengthScaleSource.Calibrated, "标定来源");
                Eq(meters.UnitText, "米", "单位文本");

                // 手动指定 1000（米）时直接采用，不看原始数值与几何长度。
                LengthScale manualMeter = LengthUnitCalibrator.Resolve(12345.0, 12345.0, 1000.0);
                Eq(manualMeter.Scale, 1000.0, "Manual 分支比例（米）");
                Eq(manualMeter.Source, LengthScaleSource.Manual, "Manual 分支来源");
                True(manualMeter.Warning == null, "手动指定不应产生警告");

                // 手动指定 1（毫米）时同样直接采用 —— 即使数值看起来像米。
                LengthScale manualMillimeter = LengthUnitCalibrator.Resolve(6.0, 6000.0, 1.0);
                Eq(manualMillimeter.Scale, 1.0, "Manual 分支比例（毫米）");
                Eq(manualMillimeter.Source, LengthScaleSource.Manual, "Manual 分支来源");

                // 换算闭环：2.5 米存储的属性值 → 2500 mm。
                double? converted = LengthUnitCalibrator.ToMillimeter(2.5, meters.Scale);
                True(converted.HasValue, "米存储的换算结果应有值");
                Near(converted.Value, 2500.0, Len, "2.5（米存储）× 1000");
            }));

            // ------------------------------------------------------------------
            // T16 指南 §10：带保温管道 —— SurfaceMode.Insulation 时
            // Deffective = Do + 2 × Tinsulation，Bottom 模式结果随之改变。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("T16 保温模式下 Deff=Do+2×Tins", delegate
            {
                PipeInfo reference = Pipe(916, 5000.0, 219.0);
                // 基准管本身也要有保温厚度：Insulation 模式下它的对齐标高同样按保温外表面算。
                reference.InsulationThicknessMm = 30.0;
                PipeInfo target = Pipe(120, 5200.0, 108.0);
                target.InsulationThicknessMm = 50.0;

                Near(reference.EffectiveDiameterMm(SurfaceMode.Insulation), 279.0, Len,
                    "基准管保温有效外径");
                Near(target.EffectiveDiameterMm(SurfaceMode.Pipe), 108.0, Len, "裸管有效外径");
                Near(target.EffectiveDiameterMm(SurfaceMode.Insulation), 208.0, Len, "保温有效外径");
                False(target.LacksInsulationThickness, "已给保温厚度，不应报缺失");
                True(reference.LacksInsulationThickness == false, "基准管已给保温厚度");

                double bareBottom = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Bottom, SurfaceMode.Pipe);
                double insulatedBottom = ElevationCalculator.GetAlignmentElevation(
                    target, AlignmentMode.Bottom, SurfaceMode.Insulation);
                Near(bareBottom, 5146.0, Len, "裸管管底标高");
                Near(insulatedBottom, 5096.0, Len, "保温外表面管底标高");
                Near(insulatedBottom, bareBottom - 50.0, Len, "保温使管底再降 Tinsulation");

                // 端到端：保温模式下 ΔZ 必须按保温外径算（基准管 Deff=279，无保温时为 219）。
                AlignmentRequest request = new AlignmentRequest(reference,
                    new List<PipeInfo> { target }, AlignmentMode.Bottom, SurfaceMode.Insulation, Options());
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(request);
                AlignmentPlanItem item = plan.Items[0];
                Near(plan.ReferenceElevationMm, 5000.0 - 279.0 / 2.0, Len, "保温模式的基准标高");
                Near(item.EffectiveDiameterMm, 208.0, Len, "计划里的有效外径");
                Near(item.DeltaZmm, (5000.0 - 279.0 / 2.0) - 5096.0, Len, "ΔZ（保温外表面）");

                // 对比：同一根管在裸管模式下（基准 Deff=219）的 ΔZ 不同 —— 证明表面模式真的生效。
                AlignmentPlan barePlan = BuildPlan(reference, Pipe(121, 5200.0, 108.0));
                Near(barePlan.ReferenceElevationMm, 4890.5, Len, "裸管模式的基准标高");
                True(Math.Abs(barePlan.Items[0].DeltaZmm - item.DeltaZmm) > 1.0,
                    "保温模式与裸管模式的 ΔZ 应有明显差异");
            }));

            // ------------------------------------------------------------------
            // S01 指南 §17：单位服务 —— UnitService(1000) 时毫米↔UOR 互为逆运算；
            // Unavailable() 的 IsAvailable 为 false，调用换算必须抛异常。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S01 单位服务换算互逆且不可用时抛异常", delegate
            {
                UnitService service = new UnitService(1000.0);
                Eq(service.IsAvailable, true, "IsAvailable");
                Near(service.UorPerMillimeter, 1000.0, Tiny, "UorPerMillimeter");

                const double millimeters = 1234.5;
                double uor = service.MillimeterToUor(millimeters);
                Near(uor, 1234500.0, 1.0e-6, "毫米 → UOR");
                Near(service.UorToMillimeter(uor), millimeters, Len, "UOR → 毫米（应为逆运算）");

                double randomUor = 250.0;
                Near(service.MillimeterToUor(service.UorToMillimeter(randomUor)), randomUor, Tiny,
                    "两次换算应回到原值");

                UnitService unavailable = UnitService.Unavailable();
                Eq(unavailable.IsAvailable, false, "Unavailable().IsAvailable");

                bool threwOnUor = false;
                try { unavailable.UorToMillimeter(1.0); }
                catch (InvalidOperationException) { threwOnUor = true; }
                Eq(threwOnUor, true, "不可用时 UorToMillimeter 应抛 InvalidOperationException");

                bool threwOnMillimeter = false;
                try { unavailable.MillimeterToUor(1.0); }
                catch (InvalidOperationException) { threwOnMillimeter = true; }
                Eq(threwOnMillimeter, true, "不可用时 MillimeterToUor 应抛 InvalidOperationException");
            }));

            // ------------------------------------------------------------------
            // S02 指南 §9：PipeAxis.ShiftedByZ 只改 Z，绝不改 X / Y。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S02 ShiftedByZ 只改 Z 不改 X/Y", delegate
            {
                PipeAxis axis = new PipeAxis(100.5, 200.25, 5000.0, 900.5, 1200.75, 5000.0);
                PipeAxis shifted = axis.ShiftedByZ(-255.5);

                Near(shifted.StartXmm, axis.StartXmm, Tiny, "起点 X");
                Near(shifted.StartYmm, axis.StartYmm, Tiny, "起点 Y");
                Near(shifted.EndXmm, axis.EndXmm, Tiny, "终点 X");
                Near(shifted.EndYmm, axis.EndYmm, Tiny, "终点 Y");
                Near(shifted.StartZmm, 4744.5, Len, "起点 Z");
                Near(shifted.EndZmm, 4744.5, Len, "终点 Z");
                Near(axis.StartZmm, 5000.0, Len, "原对象起点 Z（不得被就地修改）");
                Near(shifted.CenterElevationMm, axis.CenterElevationMm - 255.5, Len, "中心标高");
                Near(shifted.LengthMm, axis.LengthMm, Len, "平移不改变管长");
            }));

            // ------------------------------------------------------------------
            // S03 指南 §15：零长度管 IsDegenerate 为 true，且校验必须拒绝。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S03 零长度管判为退化几何", delegate
            {
                PipeAxis degenerate = new PipeAxis(100.0, 200.0, 5000.0, 100.0, 200.0, 5000.0);
                Eq(degenerate.IsDegenerate, true, "IsDegenerate");
                Near(degenerate.LengthMm, 0.0, Tiny, "三维长度");
                Near(degenerate.HorizontalRunMm, 0.0, Tiny, "水平投影长度");
                Eq(degenerate.SlopePercent.HasValue, false, "竖直/退化时坡度应为 null");

                // 正常管不应被误判。
                PipeAxis normal = new PipeAxis(0.0, 0.0, 5000.0, 1000.0, 0.0, 5000.0);
                Eq(normal.IsDegenerate, false, "正常管 IsDegenerate");

                PipeInfo degeneratePipe = Pipe(122, 5000.0, 219.0);
                degeneratePipe.Axis = degenerate;
                ValidationOutcome outcome = PipeValidationService.ValidateTargetPipe(
                    degeneratePipe, AlignmentMode.Bottom, SurfaceMode.Pipe, Options());
                False(outcome.IsValid, "零长度管必须校验不通过");
                NotEmpty(outcome.Reason, "零长度管的不通过原因");
            }));

            // ------------------------------------------------------------------
            // S04 指南 §21 / §22：PipeTopology.FindBlockingConnection ——
            // 「对端在移动集合里」必须返回 null（不阻断）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S04 FindBlockingConnection 对移动集合返回 null", delegate
            {
                List<PipeConnection> connections = new List<PipeConnection>();
                connections.Add(new PipeConnection(0, "P-2", "PIPE", null));
                connections.Add(new PipeConnection(1, "P-3", "PIPE", null));
                PipeTopology topology = new PipeTopology(connections);

                Eq(topology.IsKnown, true, "IsKnown（有连接数据的构造函数）");
                Eq(topology.ConnectionCount, 2, "ConnectionCount");
                Eq(topology.HasConnection, true, "HasConnection");
                Eq(topology.IsTwoEndConnected, true, "IsTwoEndConnected");
                NotEmpty(topology.Summary(), "连接摘要");

                PipeConnection blockingAllMoving = topology.FindBlockingConnection(
                    new List<string> { "P-2", "P-3" });
                Eq(blockingAllMoving, null, "对端全在移动集合里时应返回 null");

                PipeConnection blockingPartial = topology.FindBlockingConnection(
                    new List<string> { "P-2" });
                True(blockingPartial != null, "有对端不在移动集合里时必须返回该连接");
                Eq(blockingPartial.OtherInstanceId, "P-3", "阻断连接的实例 ID");

                // 未知连接关系在 Strict 模式下必须拒绝（指南 §22：不允许悄悄放宽）。
                PipeInfo unknown = Pipe(123, 5200.0, 219.0);
                PipeTopology unknownTopology = new PipeTopology();
                unknownTopology.IsKnown = false;
                unknownTopology.ReadWarning = "读取连接关系失败";
                unknown.Topology = unknownTopology;
                ValidationOutcome strict = PipeValidationService.ValidateTopology(
                    unknown, new List<string>(), PipeTopologyCheckMode.Strict);
                False(strict.IsValid, "Strict 模式下连接关系未知必须不通过");
                NotEmpty(strict.Reason, "连接关系未知的不通过原因");
                Eq(PipeValidationService.ValidateTopology(
                    unknown, new List<string>(), PipeTopologyCheckMode.BestEffort).IsValid, true,
                    "BestEffort 模式下连接关系未知应放行");
                Eq(PipeValidationService.ValidateTopology(
                    unknown, new List<string>(), PipeTopologyCheckMode.Off).IsValid, true,
                    "Off 模式下不做任何连接校验");
            }));

            // ------------------------------------------------------------------
            // S05 指南 §21：纯计算层的连接分类器按 EC 类名分类正确
            // （源码里的类型名是 PipeConnectionClassifier；判定顺序敏感）。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S05 连接分类器按类名分类正确", delegate
            {
                Eq(PipeConnectionClassifier.Classify("NOZZLE"),
                    PipeConnectionKind.EquipmentNozzle, "NOZZLE 分类");
                Eq(PipeConnectionClassifier.Classify("ELBOW"), PipeConnectionKind.Fitting, "ELBOW 分类");
                Eq(PipeConnectionClassifier.Classify("PIPE"), PipeConnectionKind.Pipe, "PIPE 分类");
                Eq(PipeConnectionClassifier.Classify("PIPE_NOZZLE"),
                    PipeConnectionKind.EquipmentNozzle, "PIPE_NOZZLE 必须先认管口");
                Eq(PipeConnectionClassifier.Classify("VALVE"), PipeConnectionKind.Valve, "VALVE 分类");
                Eq(PipeConnectionClassifier.Classify("FLANGE"), PipeConnectionKind.Flange, "FLANGE 分类");
                Eq(PipeConnectionClassifier.Classify("PIPE_SUPPORT"),
                    PipeConnectionKind.Support, "PIPE_SUPPORT 必须先认支吊架");
                Eq(PipeConnectionClassifier.Classify(null),
                    PipeConnectionKind.Unknown, "空类名分类");
                Eq(PipeConnectionClassifier.Classify("SOMETHING_ELSE"),
                    PipeConnectionKind.Unknown, "无法归类时为 Unknown");
                Eq(PipeConnectionClassifier.Chinese(PipeConnectionKind.EquipmentNozzle), "设备管口",
                    "设备管口中文名");
                Eq(PipeConnectionClassifier.Chinese(PipeConnectionKind.Unknown), null,
                    "未知类别中文名应为 null");
            }));

            // ------------------------------------------------------------------
            // S06 指南 §3.1 / §11：AlignmentModes.TryParse 认得英文代号与中文名。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S06 AlignmentModes.TryParse 中英文均可解析", delegate
            {
                AlignmentMode mode;

                Eq(AlignmentModes.TryParse("bottom", out mode), true, "\"bottom\" 解析结果");
                Eq(mode, AlignmentMode.Bottom, "\"bottom\" 解析出的模式");

                Eq(AlignmentModes.TryParse("管顶", out mode), true, "\"管顶\" 解析结果");
                Eq(mode, AlignmentMode.Top, "\"管顶\" 解析出的模式");

                Eq(AlignmentModes.TryParse("  CENTRE  ", out mode), true, "\"  CENTRE  \" 解析结果");
                Eq(mode, AlignmentMode.Center, "\"CENTRE\" 解析出的模式");

                Eq(AlignmentModes.TryParse("", out mode), false, "空文本应解析失败");
                Eq(AlignmentModes.TryParse("中部", out mode), false, "无法识别时应返回 false");

                Eq(AlignmentModes.Code(AlignmentMode.Bottom), "BOTTOM", "模式代号");
                Eq(AlignmentModes.Chinese(AlignmentMode.Top), "管顶", "模式中文名");

                SurfaceMode surface;
                Eq(SurfaceModes.TryParse("保温", out surface), true, "\"保温\" 解析结果");
                Eq(surface, SurfaceMode.Insulation, "\"保温\" 解析出的表面模式");
            }));

            // ------------------------------------------------------------------
            // S07 指南 §11 / 仓库规范 §7：PipeAlignOptions.Parse 能读合法键；
            // 对未知键与非法值**不抛异常**，只是忽略并写入 warnings。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S07 配置解析容错且记录警告", delegate
            {
                string text = string.Join("\n", new[]
                {
                    "# 注释行",
                    "; 另一种注释",
                    "HorizontalToleranceMm=2.5",
                    "AlignmentToleranceMm=0.01",
                    "DefaultAlignmentMode=TOP",
                    "DefaultSurfaceMode=INSULATION",
                    "MaxTargetPipes=50",
                    "AllowGraphicsTransformFallback=yes",
                    "DumpEcProperties=off",
                    "TopologyCheckMode=BestEffort",
                    "UnknownKey=1",
                    "HorizontalToleranceMm=-5",
                    "MaxTargetPipes=abc",
                    "ThisLineHasNoEquals"
                });

                List<string> warnings = new List<string>();
                PipeAlignOptions options = PipeAlignOptions.Parse(text, warnings);

                Near(options.HorizontalToleranceMm, 2.5, Tiny, "HorizontalToleranceMm（合法值）");
                Near(options.AlignmentToleranceMm, 0.01, Tiny, "AlignmentToleranceMm（合法值）");
                Eq(options.DefaultAlignmentMode, AlignmentMode.Top, "DefaultAlignmentMode");
                Eq(options.DefaultSurfaceMode, SurfaceMode.Insulation, "DefaultSurfaceMode");
                Eq(options.MaxTargetPipes, 50, "MaxTargetPipes");
                Eq(options.AllowGraphicsTransformFallback, true, "AllowGraphicsTransformFallback");
                Eq(options.DumpEcProperties, false, "DumpEcProperties");
                Eq(options.TopologyCheckMode, PipeTopologyCheckMode.BestEffort, "TopologyCheckMode");

                // 未知键 / 非法值 / 缺等号：每一行都要有警告，且不抛异常。
                Eq(warnings.Count, 4, "warnings 数量（未知键、负容差、非整数、缺等号）");
                True(warnings.Count > 0, "warnings 必须非空");

                // 空文本、null、null warnings 都不能抛异常。
                Eq(PipeAlignOptions.Parse("", new List<string>()).HorizontalToleranceMm, 1.0,
                    "空文本应回落默认值 1.0");
                Eq(PipeAlignOptions.Parse(null, null).MaxTargetPipes, 200,
                    "null 文本应回落默认值 200");
            }));

            // ------------------------------------------------------------------
            // S08 指南 §25 / §22：AlignmentPlan.ReadyInstanceIds 只包含 Ready 项。
            // ------------------------------------------------------------------
            cases.Add(new TestCase("S08 ReadyInstanceIds 只包含 Ready 项", delegate
            {
                PipeInfo reference = Pipe(924, 5000.0, 219.0);

                PipeInfo ready = Pipe(124, 5200.0, 219.0);
                ready.InstanceId = "READY-1";

                PipeInfo already = Pipe(125, 5000.0, 219.0);
                already.InstanceId = "ALREADY-1";

                PipeInfo locked = Pipe(126, 5300.0, 219.0);
                locked.InstanceId = "LOCKED-1";
                locked.IsLocked = true;

                AlignmentPlan plan = BuildPlan(reference, ready, already, locked);
                Eq(plan.ReadyCount, 1, "ReadyCount");
                Eq(plan.AlreadyAlignedCount, 1, "AlreadyAlignedCount");
                Eq(plan.SkippedCount, 1, "SkippedCount");

                List<string> ids = plan.ReadyInstanceIds();
                Eq(ids.Count, 1, "ReadyInstanceIds 数量");
                Eq(ids[0], "READY-1", "ReadyInstanceIds 内容");
                False(ids.Contains("ALREADY-1"), "AlreadyAligned 项不得进入移动集合");
                False(ids.Contains("LOCKED-1"), "Skipped 项不得进入移动集合");
                False(ids.Contains(reference.InstanceId), "基准管不得进入移动集合");
            }));

            // ------------------------------------------------------------------
            // §34 指南算例（端到端）：基准管中心标高 5000、外径 219；
            // 目标管中心标高 5200、外径 108；Bottom 模式：
            //   Zbottom(基准) = 5000 − 219/2 = 4890.5
            //   Zbottom(目标) = 5200 − 108/2 = 5146
            //   ΔZ = 4890.5 − 5146 = −255.5 mm
            // ------------------------------------------------------------------
            cases.Add(new TestCase("§34 算例 基准Zc5000/Do219 → 目标Zc5200/Do108 Bottom ΔZ=−255.5", delegate
            {
                PipeInfo reference = Pipe(934, 5000.0, 219.0);
                PipeInfo target = Pipe(134, 5200.0, 108.0);

                // 先用公开的 BottomElevation 工具复核两个标高（指南 §34 的算式）。
                Near(ElevationCalculator.BottomElevation(5000.0, 219.0), 4890.5, Len,
                    "BottomElevation(5000, 219)");
                Near(ElevationCalculator.BottomElevation(5200.0, 108.0), 5146.0, Len,
                    "BottomElevation(5200, 108)");
                Near(ElevationCalculator.TopElevation(5200.0, 108.0), 5254.0, Len,
                    "TopElevation(5200, 108)");

                // 端到端走一遍 BuildPlan。
                AlignmentPlan plan = BuildPlan(reference, target);
                Near(plan.ReferenceElevationMm, 4890.5, Len, "计划的基准标高");
                AlignmentPlanItem item = plan.Items[0];
                Near(item.CurrentElevationMm, 5146.0, Len, "目标管当前对齐标高");
                Near(item.ReferenceElevationMm, 4890.5, Len, "目标管要对齐到的标高");
                Near(item.DeltaZmm, -255.5, Len, "ΔZ");
                Near(item.DeltaZmm, 4890.5 - 5146.0, 1.0e-9, "ΔZ（按指南算式逐项复核）");

                // 移动后管底必须严格等于基准管管底。
                Near(ElevationCalculator.BottomElevation(
                        item.TargetAxis.CenterElevationMm, item.EffectiveDiameterMm),
                    plan.ReferenceElevationMm, Len, "移动后目标管管底标高");
            }));

            // ==================================================================
            // Move Group（开发指南 §23 / §24）—— 整组展开与边界拒绝
            // ==================================================================
            cases.Add(new TestCase("G01 MoveGroupPolicy 默认分类：管/管件/法兰/阀门可动，管口/支吊架/仪表/未知为边界", delegate
            {
                MoveGroupPolicy policy = MoveGroupPolicy.Default();
                True(policy.IsMovableClass("PIPE"), "PIPE 应可一起移动");
                True(policy.IsMovableClass("PIPE_ELBOW"), "弯头应可一起移动");
                True(policy.IsMovableClass("PIPE_FLANGE"), "法兰应可一起移动");
                True(policy.IsMovableClass("PIPE_VALVE"), "阀门应可一起移动");
                True(!policy.IsMovableClass("NOZZLE"), "设备管口不应可一起移动");
                True(!policy.IsMovableClass("PIPE_SUPPORT"), "支吊架默认不应可一起移动");
                True(!policy.IsMovableClass("INSTRUMENT"), "仪表不应可一起移动");
                True(!policy.IsMovableClass("SOME_UNKNOWN_CLASS"), "未知类不应可一起移动");
                NotEmpty(policy.Describe(), "策略说明");
            }));

            cases.Add(new TestCase("G02 Move Group 沿连接关系展开整条链（PIPE 串联）", delegate
            {
                Dictionary<string, PipeInfo> graph = new Dictionary<string, PipeInfo>();
                PipeInfo a = Pipe(1, 100.0, 219.0);
                PipeInfo b = Pipe(2, 100.0, 219.0);
                PipeInfo c = Pipe(3, 100.0, 219.0);
                Connect(a, b.InstanceId, "PIPE", 1);
                Connect(b, a.InstanceId, "PIPE", 0);
                Connect(b, c.InstanceId, "PIPE", 1);
                Connect(c, b.InstanceId, "PIPE", 0);
                graph[a.InstanceId] = a;
                graph[b.InstanceId] = b;
                graph[c.InstanceId] = c;

                PipeGroupExpansion expansion = PipeGroupExpander.Expand(
                    new List<PipeInfo> { a }, MoveGroupPolicy.Default(), 50,
                    delegate (string id) { PipeInfo found; return graph.TryGetValue(id, out found) ? found : null; },
                    null);

                True(expansion.IsUsable, "纯 PIPE 链应可整组移动，实际：" + expansion.RefusalReason);
                Eq(expansion.Members.Count, 3, "整组成员数");
                Eq(expansion.BoundaryDescriptions.Count, 0, "边界数");
            }));

            cases.Add(new TestCase("G03 Move Group 遇到设备管口时拒绝整组并说明边界", delegate
            {
                Dictionary<string, PipeInfo> graph = new Dictionary<string, PipeInfo>();
                PipeInfo a = Pipe(1, 100.0, 219.0);
                PipeInfo b = Pipe(2, 100.0, 219.0);
                Connect(a, b.InstanceId, "PIPE", 1);
                Connect(b, a.InstanceId, "PIPE", 0);
                // 第二根管另一端接设备管口 —— 等量平移会在这里产生断口。
                Connect(b, "nozzle-instance", "NOZZLE", 1);
                graph[a.InstanceId] = a;
                graph[b.InstanceId] = b;

                PipeGroupExpansion expansion = PipeGroupExpander.Expand(
                    new List<PipeInfo> { a }, MoveGroupPolicy.Default(), 50,
                    delegate (string id) { PipeInfo found; return graph.TryGetValue(id, out found) ? found : null; },
                    null);

                True(!expansion.IsUsable, "存在管口边界时必须拒绝整组");
                NotEmpty(expansion.RefusalReason, "拒绝原因");
                True(expansion.RefusalReason.Contains("管口"), "拒绝原因里应点明是设备管口");
                Eq(expansion.BoundaryDescriptions.Count, 1, "边界条目数");
            }));

            cases.Add(new TestCase("G04 Move Group 连接关系未知时拒绝整组", delegate
            {
                PipeInfo a = Pipe(1, 100.0, 219.0);
                a.Topology.IsKnown = false;
                a.Topology.ReadWarning = "测试用：读取失败";

                PipeGroupExpansion expansion = PipeGroupExpander.Expand(
                    new List<PipeInfo> { a }, MoveGroupPolicy.Default(), 50,
                    delegate (string id) { return null; }, null);

                True(!expansion.IsUsable, "连通性未知时必须拒绝整组（否则就是猜移动范围）");
                NotEmpty(expansion.RefusalReason, "拒绝原因");
            }));

            cases.Add(new TestCase("G05 Move Group 超过成员上限时拒绝", delegate
            {
                Dictionary<string, PipeInfo> graph = new Dictionary<string, PipeInfo>();
                // 造一条 6 根管的链，上限设 3。
                PipeInfo[] chain = new PipeInfo[6];
                for (int index = 0; index < chain.Length; index++)
                {
                    chain[index] = Pipe((ulong)(index + 1), 100.0, 219.0);
                    graph[chain[index].InstanceId] = chain[index];
                }
                for (int index = 0; index < chain.Length - 1; index++)
                {
                    Connect(chain[index], chain[index + 1].InstanceId, "PIPE", 1);
                    Connect(chain[index + 1], chain[index].InstanceId, "PIPE", 0);
                }

                PipeGroupExpansion expansion = PipeGroupExpander.Expand(
                    new List<PipeInfo> { chain[0] }, MoveGroupPolicy.Default(), 3,
                    delegate (string id) { PipeInfo found; return graph.TryGetValue(id, out found) ? found : null; },
                    null);

                True(!expansion.IsUsable, "超过上限必须拒绝，而不是拖走半张图");
                NotEmpty(expansion.RefusalReason, "拒绝原因");
            }));

            cases.Add(new TestCase("G06 MoveScopes.TryParse 中英文均可解析", delegate
            {
                MoveScope scope;
                True(MoveScopes.TryParse("GROUP", out scope) && scope == MoveScope.ConnectedGroup, "GROUP");
                True(MoveScopes.TryParse("整组", out scope) && scope == MoveScope.ConnectedGroup, "整组");
                True(MoveScopes.TryParse("SINGLE", out scope) && scope == MoveScope.SelectedOnly, "SINGLE");
                True(!MoveScopes.TryParse("这不是模式", out scope), "非法值应返回 false");
            }));

            cases.Add(new TestCase("G07 Move Group 成员计入计划并标记为自动带入", delegate
            {
                PipeInfo reference = Pipe(900, 5000.0, 219.0);
                PipeInfo seed = Pipe(1, 5200.0, 219.0);
                PipeInfo neighbour = Pipe(2, 5200.0, 219.0);
                // 组内两根管都在移动集合里，所以 Safe Mode 的拓扑校验不应把它们判为"固定连接"。
                Connect(seed, neighbour.InstanceId, "PIPE", 1);
                Connect(neighbour, seed.InstanceId, "PIPE", 0);

                AlignmentRequest request = new AlignmentRequest(reference,
                    new List<PipeInfo> { seed, neighbour }, AlignmentMode.Bottom, SurfaceMode.Pipe,
                    new PipeAlignOptions(), new List<string> { seed.InstanceId });
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(request);

                Eq(plan.Items.Count, 2, "计划条目数");
                False(plan.Items[0].AddedByGroup, "用户选中的那根不应标为自动带入");
                True(plan.Items[1].AddedByGroup, "连通带进来的那根应标为自动带入");
                Eq(plan.ReadyCount, 2, "两根都应可移动（互为移动集合）");
            }));

            cases.Add(new TestCase("G08 管件和竖管按种子同一位移平移", delegate
            {
                PipeInfo reference = Pipe(900, 5000.0, 219.0);
                PipeInfo seed = Pipe(1, 5200.0, 219.0);
                PipeInfo elbow = Pipe(2, 5200.0, 108.0);
                elbow.ClassName = "LONG_RADIUS_90_DEGREE_PIPE_ELBOW";
                PipeInfo vertical = Pipe(3, 5200.0, 108.0);
                vertical.Axis = new PipeAxis(0.0, 0.0, 5200.0, 0.0, 0.0, 6200.0);
                Connect(seed, elbow.InstanceId, elbow.ClassName, 1);
                Connect(elbow, vertical.InstanceId, "PIPE", 1);
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(new AlignmentRequest(reference,
                    new List<PipeInfo> { seed, elbow, vertical }, AlignmentMode.Bottom, SurfaceMode.Pipe,
                    Options(), new List<string> { seed.InstanceId }));
                Eq(plan.ReadyCount, 3, "全部组员应可移动");
                foreach (AlignmentPlanItem item in plan.Items) Near(item.DeltaZmm, -200.0, Len, "同一 ΔZ");
            }));
            cases.Add(new TestCase("G09 同一连通组的种子位移冲突时拒绝", delegate
            {
                PipeInfo a = Pipe(1, 5200.0, 219.0);
                PipeInfo b = Pipe(2, 5300.0, 219.0);
                Connect(a, b.InstanceId, "PIPE", 1);
                bool refused = false;
                try
                {
                    PipeAlignPlanner.BuildPlan(new AlignmentRequest(Pipe(900, 5000.0, 219.0),
                        new List<PipeInfo> { a, b }, AlignmentMode.Bottom, SurfaceMode.Pipe,
                        Options(), new List<string> { a.InstanceId, b.InstanceId }));
                }
                catch (PipeAlignValidationException) { refused = true; }
                True(refused, "必须拒绝不同位移");
            }));
            cases.Add(new TestCase("G10 组内锁定成员或基准管必须拒绝整组", delegate
            {
                PipeInfo seed = Pipe(1, 5200.0, 219.0);
                PipeInfo locked = Pipe(2, 5200.0, 219.0);
                locked.IsLocked = true;
                Connect(seed, locked.InstanceId, "PIPE", 1);
                bool refused = false;
                try
                {
                    PipeAlignPlanner.BuildPlan(new AlignmentRequest(Pipe(900, 5000.0, 219.0),
                        new List<PipeInfo> { seed, locked }, AlignmentMode.Center, SurfaceMode.Pipe,
                        Options(), new List<string> { seed.InstanceId }));
                }
                catch (PipeAlignValidationException) { refused = true; }
                True(refused, "锁定组员应拒绝整组");
                locked.IsLocked = false;
                refused = false;
                try
                {
                    PipeAlignPlanner.BuildPlan(new AlignmentRequest(locked,
                        new List<PipeInfo> { seed, locked }, AlignmentMode.Center, SurfaceMode.Pipe,
                        Options(), new List<string> { seed.InstanceId }));
                }
                catch (PipeAlignValidationException) { refused = true; }
                True(refused, "不能移动基准管");
            }));
            cases.Add(new TestCase("V01 几何变化但 EC 未同步不得算移动成功", delegate
            {
                PipeInfo pipe = Pipe(1, 5200.0, 219.0);
                pipe.MoveProbe = new PipeMoveProbe { ApiUnitsPerMillimeter = 1000.0 };
                pipe.EcTranslationZRaw = 5200000.0;
                var verification = new PipeMoveVerification
                {
                    GeometryCenterElevationMm = 5000.0, EcTranslationZRaw = 5200000.0
                };
                False(verification.MatchesPosition(pipe, -200.0, 0.1), "不同步应失败");
                verification.EcTranslationZRaw = 5000000.0;
                True(verification.MatchesPosition(pipe, -200.0, 0.1), "同步才成功");
                verification.EcTranslationZRaw = null;
                False(verification.MatchesPosition(pipe, -200.0, 0.1), "EC 无读数应失败");
            }));
            cases.Add(new TestCase("V02 移动后丢失或新增连接必须拒绝", delegate
            {
                PipeInfo pipe = Pipe(1, 5200.0, 219.0);
                Connect(pipe, "neighbor", "PIPE", 0);
                var verification = new PipeMoveVerification { Topology = new PipeTopology() };
                False(verification.MatchesConnections(pipe), "丢连接");
                verification.Topology.Connections.Add(new PipeConnection(0, "neighbor", "PIPE", null));
                True(verification.MatchesConnections(pipe), "连接保留");
                verification.Topology.Connections.Add(new PipeConnection(1, "new", "PIPE", null));
                False(verification.MatchesConnections(pipe), "新增连接");
            }));
            cases.Add(new TestCase("S09 相连目标管独立计算出不同位移时必须跳过", delegate
            {
                PipeInfo a = Pipe(1, 5200.0, 219.0);
                PipeInfo b = Pipe(2, 5200.0, 108.0);
                Connect(a, b.InstanceId, "PIPE", 1);
                Connect(b, a.InstanceId, "PIPE", 0);
                AlignmentPlan plan = PipeAlignPlanner.BuildPlan(Request(Pipe(900, 5000.0, 219.0), a, b));
                Eq(plan.ReadyCount, 0, "不能按不同 ΔZ 移动相连对象");
            }));
            cases.Add(new TestCase("Z01 锁 Z 上移：水平管弯头随动，立管伸长，固定侧不进入移动组", delegate
            {
                var route = RouteFixture(false);
                AlignmentPlan plan = RoutePlan(route, 200.0);
                Eq(plan.Items.Count, 3, "水平管、弯头、立管");
                Eq(plan.FixedPipes.Count, 1, "固定侧快照");
                AlignmentPlanItem stretch = StretchItem(plan);
                Near(stretch.TargetAxis.StartZmm, 1100.0, Len, "随动端");
                Near(stretch.TargetAxis.EndZmm, 0.0, Len, "固定端");
                Near(stretch.TargetAxis.LengthMm, 1100.0, Len, "新管长");
                foreach (AlignmentPlanItem item in plan.Items)
                    if (!item.IsStretch) Near(item.TargetAxis.StartZmm - item.Pipe.Axis.StartZmm, 200.0, Len, "随动位移");
            }));
            cases.Add(new TestCase("Z02 锁 Z 下移：立管缩短，固定端不变", delegate
            {
                AlignmentPlanItem stretch = StretchItem(RoutePlan(RouteFixture(false), -200.0));
                Near(stretch.TargetAxis.LengthMm, 700.0, Len, "缩短后的管长");
                Near(stretch.TargetAxis.EndZmm, 0.0, Len, "固定端");
            }));
            cases.Add(new TestCase("Z03 立管端点顺序反向仍固定正确端", delegate
            {
                AlignmentPlanItem stretch = StretchItem(RoutePlan(RouteFixture(true), 200.0));
                Near(stretch.TargetAxis.StartZmm, 0.0, Len, "反向起点固定");
                Near(stretch.TargetAxis.EndZmm, 1100.0, Len, "反向终点随动");
            }));
            cases.Add(new TestCase("Z04 立管过短或越过固定端必须拒绝", delegate
            {
                RouteRefused(RouteFixture(false), -899.0, Options());
                RouteRefused(RouteFixture(false), -1000.0, Options());
                var options = Options();
                options.MinimumStretchLengthMm = 800.0;
                RouteRefused(RouteFixture(false), -200.0, options);
            }));
            cases.Add(new TestCase("Z05 斜管、只读和未知连接不能绕过路由保护", delegate
            {
                var route = RouteFixture(false);
                route["vertical"].Axis = new PipeAxis(1100.0, 0.0, 900.0, 1200.0, 0.0, 0.0);
                RouteRefused(route, 200.0, Options());
                route = RouteFixture(false);
                route["vertical"].IsReadOnly = true;
                RouteRefused(route, 200.0, Options());
                route = RouteFixture(false);
                route["elbow"].Topology.IsKnown = false;
                RouteRefused(route, 200.0, Options());
            }));
            cases.Add(new TestCase("Z06 固定侧只读可保持固定，移动侧遇设备边界拒绝", delegate
            {
                var route = RouteFixture(false);
                route["fixed"].IsReadOnly = true;
                Eq(RoutePlan(route, 200.0).Items.Count, 3, "不修改只读固定侧");
                route["elbow"].ClassName = "EQUIPMENT_NOZZLE";
                RouteRefused(route, 200.0, Options());
            }));
            cases.Add(new TestCase("Z07 端点不吻合与立管分支歧义均拒绝", delegate
            {
                var route = RouteFixture(false);
                route["elbow"].Axis = new PipeAxis(1000.0, 0.0, 1000.0, 1100.0, 0.0, 800.0);
                RouteRefused(route, 200.0, Options());
                route = RouteFixture(false);
                Connect(route["vertical"], "third", "PIPE", 2);
                RouteRefused(route, 200.0, Options());
            }));
            cases.Add(new TestCase("Z08 伸缩必须同时验证两个端点、EC 长度与 EC 原点", delegate
            {
                foreach (bool reversed in new[] { false, true })
                {
                    AlignmentPlanItem item = StretchItem(RoutePlan(RouteFixture(reversed), 200.0));
                    var verification = new PipeMoveVerification
                    {
                        GeometryAxis = item.TargetAxis,
                        EcLengthRaw = item.TargetAxis.LengthMm,
                        EcTranslationZRaw = item.TargetAxis.StartZmm * 1000.0
                    };
                    True(verification.MatchesTarget(item, 0.1), "两种顺序都应验证通过");
                    verification.EcLengthRaw = item.Pipe.Axis.LengthMm;
                    False(verification.MatchesTarget(item, 0.1), "几何变了但 LENGTH 未写回");
                    verification.EcLengthRaw = item.TargetAxis.LengthMm;
                    verification.GeometryAxis = item.TargetAxis.ShiftedByZ(10.0);
                    False(verification.MatchesTarget(item, 0.1), "固定端被带走");
                }
            }));
            cases.Add(new TestCase("Z09 配置容错和 ZSTRETCH 模式序列化往返", delegate
            {
                var warnings = new List<string>();
                PipeAlignOptions options = PipeAlignOptions.Parse("MoveScope=ZSTRETCH\nRouteEndpointToleranceMm=0.5\nMinimumStretchLengthMm=50", warnings);
                Eq(warnings.Count, 0, "合法配置");
                True(options.DefaultMoveScope == MoveScope.ZStretch, "锁 Z 模式");
                PipeAlignOptions reread = PipeAlignOptions.Parse(options.Serialize(), warnings);
                Near(reread.MinimumStretchLengthMm, 50.0, Len, "最小管长往返");
                Near(reread.RouteEndpointToleranceMm, 0.5, Len, "端点容差往返");
                options = PipeAlignOptions.Parse("MinimumStretchLengthMm=-1\nRouteEndpointToleranceMm=NaN", warnings);
                Near(options.MinimumStretchLengthMm, 10.0, Len, "非法数值默认");
                True(warnings.Count == 2, "逐行警告");
            }));
            cases.Add(new TestCase("Z10 成员上限与非有限位移必须拒绝", delegate
            {
                var options = Options();
                options.MoveGroupMaxMembers = 2;
                RouteRefused(RouteFixture(false), 200.0, options);
                RouteRefused(RouteFixture(false), double.NaN, Options());
                RouteRefused(RouteFixture(false), double.PositiveInfinity, Options());
            }));
            cases.Add(new TestCase("Z11 基准管底中心管顶驱动路由伸缩", delegate
            {
                foreach (AlignmentMode mode in new[] { AlignmentMode.Bottom, AlignmentMode.Center, AlignmentMode.Top })
                {
                    var route = RouteFixture(false);
                    PipeInfo reference = Pipe(99, 1200, 168.3);
                    reference.InstanceId = "reference";
                    AlignmentPlan plan = ZAxisRoutePlanner.BuildAligned(reference, route["seed"], mode,
                        SurfaceMode.Pipe, delegate(string id) { return route[id]; }, Options());
                    double expected = ElevationCalculator.GetAlignmentElevation(reference, mode, SurfaceMode.Pipe)
                        - ElevationCalculator.GetAlignmentElevation(route["seed"], mode, SurfaceMode.Pipe);
                    Near(plan.Items[0].DeltaZmm, expected, Len, "按真实管径计算位移");
                    Near(StretchItem(plan).TargetAxis.EndZmm, 0, Len, "远端固定");
                    Near(StretchItem(plan).TargetAxis.LengthMm, 900 + expected, Len, "立管跟随伸缩");
                    True(plan.ReferencePipe == reference && plan.Mode == mode, "计划保留真实基准与对齐方式");
                }
            }));
            cases.Add(new TestCase("Z12 基准处于移动范围必须拒绝", delegate
            {
                var route = RouteFixture(false);
                bool refused = false;
                try { ZAxisRoutePlanner.BuildAligned(route["seed"], route["seed"], AlignmentMode.Center,
                    SurfaceMode.Pipe, delegate(string id) { return route[id]; }, Options()); }
                catch (PipeAlignValidationException) { refused = true; }
                True(refused, "禁止移动基准");
            }));
            return cases;
        }

        private static Dictionary<string, PipeInfo> RouteFixture(bool reverseVertical)
        {
            var route = new Dictionary<string, PipeInfo>();
            route["seed"] = RouteMember(1, "seed", "PIPE", new PipeAxis(0, 0, 1000, 1000, 0, 1000));
            route["elbow"] = RouteMember(2, "elbow", "LONG_RADIUS_90_DEGREE_PIPE_ELBOW", new PipeAxis(1000, 0, 1000, 1100, 0, 900));
            route["vertical"] = RouteMember(3, "vertical", "PIPE", reverseVertical
                ? new PipeAxis(1100, 0, 0, 1100, 0, 900) : new PipeAxis(1100, 0, 900, 1100, 0, 0));
            route["fixed"] = RouteMember(4, "fixed", "PIPE", new PipeAxis(1100, 0, 0, 1100, 1000, 0));
            Connect(route["seed"], "elbow", route["elbow"].ClassName, 1);
            Connect(route["elbow"], "seed", "PIPE", 0);
            Connect(route["elbow"], "vertical", "PIPE", 1);
            Connect(route["vertical"], "elbow", route["elbow"].ClassName, reverseVertical ? 1 : 0);
            Connect(route["vertical"], "fixed", "PIPE", reverseVertical ? 0 : 1);
            Connect(route["fixed"], "vertical", "PIPE", 0);
            return route;
        }

        private static PipeInfo RouteMember(ulong id, string instance, string className, PipeAxis axis)
        {
            PipeInfo pipe = Pipe(id, axis.CenterElevationMm, 88.9);
            pipe.InstanceId = instance;
            pipe.ClassName = className;
            pipe.Axis = axis;
            pipe.EcTranslationZRaw = axis.StartZmm * 1000.0;
            pipe.EcLengthRaw = axis.LengthMm;
            pipe.PropertyLengthScale = 1.0;
            pipe.MoveProbe = new PipeMoveProbe { ApiUnitsPerMillimeter = 1000.0, LinearPointsUsable = true, TransformUsable = true };
            return pipe;
        }

        private static AlignmentPlan RoutePlan(Dictionary<string, PipeInfo> route, double delta)
        {
            return ZAxisRoutePlanner.Build(route["seed"], delta, delegate(string id) { return route[id]; }, Options());
        }

        private static AlignmentPlanItem StretchItem(AlignmentPlan plan)
        {
            foreach (AlignmentPlanItem item in plan.Items) if (item.IsStretch) return item;
            throw new InvalidOperationException("没有立管伸缩计划");
        }

        private static void RouteRefused(Dictionary<string, PipeInfo> route, double delta, PipeAlignOptions options)
        {
            bool refused = false;
            try { ZAxisRoutePlanner.Build(route["seed"], delta, delegate(string id) { return route[id]; }, options); }
            catch (PipeAlignValidationException) { refused = true; }
            True(refused, "必须拒绝危险路由调整");
        }
    }
}
