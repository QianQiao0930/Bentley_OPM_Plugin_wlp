using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 一次会话的全部状态（开发指南 §5 的 Tool state object）。
    /// <para>
    /// 刻意**不用全局静态变量共享可变参数**：基准管、目标管、模式、计划都挂在这个对象上，
    /// 窗口关闭时整体丢弃，下一次打开是干净的一份。
    /// </para>
    /// <para>
    /// 依赖装配也在这里：数据读取器、OpenPlant 探针与移动适配器、几何复核器。
    /// 换 OPM 版本时只需要换这里的适配器实现（开发指南 §20）。
    /// </para>
    /// </summary>
    internal sealed class PipeAlignSession
    {
        private readonly List<PipeInfo> _targetPipes = new List<PipeInfo>();

        internal PipeAlignSession()
        {
            Log = new PipeAlignLog(false);
            Adapter = new OpenPlant2024PipeAdapter();
            ObjectProbe = new OpenPlant2024ObjectProbe();
            Verifier = new PipeGeometryVerifier(Log);
            Preview = new PipeAlignPreviewSession();

            string loadedFrom;
            IList<string> warnings;
            Options = PipeAlignOptionsStore.Load(out loadedFrom, out warnings);
            Scope = Options.DefaultMoveScope;
            Mode = Options.DefaultAlignmentMode;
            SurfaceMode = Options.DefaultSurfaceMode;
            OptionsPath = loadedFrom;

            foreach (string warning in warnings) Log.Warn(warning);
            if (!string.IsNullOrEmpty(loadedFrom))
                Log.Detail("运行参数来自：" + loadedFrom);
        }

        /// <summary>实际生效的运行参数。</summary>
        internal PipeAlignOptions Options { get; set; }

        /// <summary>运行参数文件路径（没有则为 <c>null</c>，表示用的是内置默认值）。</summary>
        internal string OptionsPath { get; private set; }

        internal PipeAlignLog Log { get; private set; }

        internal IOpenPlantPipeAdapter Adapter { get; private set; }

        internal IOpenPlantObjectProbe ObjectProbe { get; private set; }

        internal IPipeGeometryVerifier Verifier { get; private set; }

        internal PipeAlignPreviewSession Preview { get; private set; }

        /// <summary>基准管。**独立对象**，不从目标集合里推断（指南 §2.2）。</summary>
        internal PipeInfo ReferencePipe { get; set; }

        /// <summary>目标管集合。顺序与业务无关。</summary>
        internal IList<PipeInfo> TargetPipes { get { return _targetPipes; } }

        internal AlignmentMode Mode { get; set; }

        internal SurfaceMode SurfaceMode { get; set; }

        /// <summary>移动范围（指南 §22 Safe Mode / §23 Move Group）。</summary>
        internal MoveScope Scope { get; set; }
        internal double ZMoveDeltaMm { get; set; }

        /// <summary>最近一次 Move Group 展开的说明（行数变化时告诉用户为什么）。</summary>
        internal string LastGroupNote { get; private set; }

        /// <summary>当前的计划（预览与执行都用它）。</summary>
        internal AlignmentPlan Plan { get; set; }

        /// <summary>单位服务，随活动模型变化，取用前先刷新。</summary>
        internal IUnitService Units
        {
            get { return DgnUnitServiceFactory.ForModel(Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel()); }
        }

        /// <summary>按位置读取一根管道（**必须在工具回调返回之后调用**）。</summary>
        internal PipeInfo ReadPipe(LocatedElement located, bool keepAllProperties, bool readTopology)
        {
            if (located == null) throw new ArgumentNullException("located");
            PipeReadOptions readOptions = new PipeReadOptions
            {
                ReadTopology = readTopology,
                SkipMoveProbe = located.IsFromReference(),
                KeepAllProperties = keepAllProperties
            };
            return PipeElementReader.Read(located.ModelRef, located.ElementId, readOptions, ObjectProbe, Log);
        }

        internal void SetReferencePipe(PipeInfo pipe)
        {
            ReferencePipe = pipe;
            Plan = null;
        }

        /// <summary>把一个目标加进集合；同一根管只保留一次（判等见 <see cref="PipeIdentity"/>）。</summary>
        internal bool AddTargetPipe(PipeInfo pipe)
        {
            if (pipe == null) return false;
            string key = PipeIdentity.Key(pipe);
            foreach (PipeInfo existing in _targetPipes)
                if (string.Equals(PipeIdentity.Key(existing), key, StringComparison.Ordinal)) return false;
            if (_targetPipes.Count >= 15) throw new PipeAlignValidationException("最多选择 15 根起点/目标管。");
            _targetPipes.Add(pipe);
            Plan = null;
            return true;
        }

        /// <summary>按 <see cref="PipeIdentity.Key"/> 移除目标管。</summary>
        internal void RemoveTargetPipe(string identityKey)
        {
            if (string.IsNullOrEmpty(identityKey)) return;
            for (int index = _targetPipes.Count - 1; index >= 0; index--)
                if (string.Equals(PipeIdentity.Key(_targetPipes[index]), identityKey, StringComparison.Ordinal))
                    _targetPipes.RemoveAt(index);
            Plan = null;
        }

        internal void ClearTargets()
        {
            _targetPipes.Clear();
            Plan = null;
        }

        /// <summary>重新计算计划（指南 §16 / §27）。校验失败会抛出带中文消息的异常。</summary>
        internal AlignmentPlan BuildPlan()
        {
            if (Scope == MoveScope.ZStretch)
            {
                if (_targetPipes.Count < 1 || _targetPipes.Count > 15)
                    throw new PipeAlignValidationException("锁 Z 模式请选择 1～15 根水平管作为起点。");
                Plan = ZAxisRoutePlanner.BuildBatch(ReferencePipe, _targetPipes, Mode, SurfaceMode, ReadByInstanceId, Options);
                ZMoveDeltaMm = ElevationCalculator.ComputeDeltaZ(Plan.ReferenceElevationMm,
                    ElevationCalculator.GetAlignmentElevation(_targetPipes[0], Mode, SurfaceMode));
                int stretches = 0;
                foreach (AlignmentPlanItem item in Plan.Items) if (item.IsStretch) stretches++;
                LastGroupNote = string.Format(CultureInfo.InvariantCulture,
                    "多起点批量（各起点独立计算位移），随动 {1} 个，立管伸缩 {2} 根，固定侧 {3} 个",
                    ZMoveDeltaMm, Plan.Items.Count - stretches, stretches, Plan.FixedPipes.Count);
                return Plan;
            }
            IList<PipeInfo> targets = _targetPipes;
            IList<string> seedInstanceIds = null;
            LastGroupNote = null;

            if (Scope == MoveScope.ConnectedGroup)
            {
                // Move Group（指南 §23）：沿连接关系把整组展开，组内同一个 ΔZ。
                PipeGroupExpansion expansion = PipeGroupExpander.Expand(
                    _targetPipes, Options.BuildGroupPolicy(), Options.MoveGroupMaxMembers,
                    delegate (string instanceId) { return ReadByInstanceId(instanceId); },
                    delegate (string message) { Log.Detail(message); });

                if (!expansion.IsUsable)
                {
                    Log.Warn(expansion.RefusalReason);
                    Log.Flush();
                    throw new PipeAlignValidationException(expansion.RefusalReason);
                }

                targets = expansion.Members;
                seedInstanceIds = SeedInstanceIds();
                LastGroupNote = expansion.Describe();
                foreach (string trace in expansion.Traces) Log.Detail(trace);
            }

            AlignmentRequest request = new AlignmentRequest(ReferencePipe, targets, Mode, SurfaceMode,
                Options, seedInstanceIds);
            Plan = PipeAlignPlanner.BuildPlan(request);
            int modifiedPipes = 0;
            foreach (var item in Plan.Items)
                if (item.WillMove && PipeConnectionClassifier.Classify(item.Pipe.ClassName) == PipeConnectionKind.Pipe) modifiedPipes++;
            if (modifiedPipes > 15) { Plan = null; throw new PipeAlignValidationException("本批实际修改的直管超过 15 根，请减少目标或分批操作。"); }
            return Plan;
        }

        /// <summary>用户直接选中的目标管的实例 ID 集合。</summary>
        private IList<string> SeedInstanceIds()
        {
            List<string> ids = new List<string>();
            foreach (PipeInfo pipe in _targetPipes)
                if (pipe != null && !string.IsNullOrEmpty(pipe.InstanceId)) ids.Add(pipe.InstanceId);
            return ids;
        }

        /// <summary>按实例 ID 读一根连通对象（Move Group 展开成员时用）。</summary>
        private PipeInfo ReadByInstanceId(string instanceId)
        {
            Log.Detail("路由读取开始：" + instanceId); Log.Flush();
            PipeReadOptions readOptions = new PipeReadOptions { ReadTopology = true };
            var pipe = PipeElementReader.ReadByInstanceId(instanceId, readOptions, ObjectProbe, Log);
            Log.Detail("路由读取完成：" + instanceId); Log.Flush();
            return pipe;
        }

        /// <summary>
        /// 执行前重新读取全部管道（开发指南 §27 的第 1、2 步：再次读取所有 Pipe 对象、
        /// 检查 Element 是否仍然有效）。
        /// <para>
        /// 从选择到点【应用】之间用户可能删掉、撤消或改动了管道，**必须**重读一遍，
        /// 否则计划里的标高与拓扑可能已经过期。
        /// </para>
        /// </summary>
        /// <param name="notes">重读过程中的中文说明（元素已失效、读取失败等）。</param>
        /// <returns>是否至少还有一根基准管可继续。</returns>
        internal bool ReloadPipes(IList<string> notes)
        {
            if (notes == null) notes = new List<string>();

            if (ReferencePipe != null)
            {
                PipeInfo reloaded = TryReload(ReferencePipe, notes);
                if (reloaded == null)
                {
                    notes.Add("基准管已不存在或无法读取，请重新选择基准管。");
                    ReferencePipe = null;
                }
                else
                {
                    ReferencePipe = reloaded;
                }
            }

            for (int index = _targetPipes.Count - 1; index >= 0; index--)
            {
                PipeInfo reloaded = TryReload(_targetPipes[index], notes);
                if (reloaded == null)
                {
                    notes.Add(string.Format(CultureInfo.InvariantCulture,
                        "目标管 {0} 已不存在或无法读取，已从列表移除。", _targetPipes[index].DisplayName));
                    _targetPipes.RemoveAt(index);
                }
                else
                {
                    _targetPipes[index] = reloaded;
                }
            }

            Plan = null;
            return ReferencePipe != null;
        }

        private PipeInfo TryReload(PipeInfo pipe, IList<string> notes)
        {
            if (pipe == null) return null;
            try
            {
                PipeReadOptions readOptions = new PipeReadOptions { ReadTopology = true };
                // ⚠️ 必须带上原来的模型引用，不能只用 ElementId：参考文件与活动模型各自编号，
                // 丢掉模型引用会把参考元素读成活动模型里的同号元素（读到别的构件）。
                LocatedElement located = pipe.Source as LocatedElement;
                DgnModelRef modelRef = located == null ? null : located.ModelRef;
                return PipeElementReader.Read(modelRef, pipe.ElementId, readOptions, ObjectProbe, Log);
            }
            catch (Exception ex)
            {
                notes.Add("重新读取 " + pipe.DisplayName + " 失败：" + ex.Message);
                return null;
            }
        }

        /// <summary>执行对齐（指南 §27 / §28 / §29）。</summary>
        internal AlignmentResult Apply()
        {
            if (Plan == null) BuildPlan();
            PipeMoveService service = new PipeMoveService(Adapter, Verifier, Units, Options, Log);
            AlignmentResult result = service.Apply(Plan);
            Log.Block(result.BuildLog());
            Log.Flush();
            return result;
        }

        /// <summary>清空本次会话的选择与预览。</summary>
        internal void Reset()
        {
            Preview.Clear();
            _targetPipes.Clear();
            ReferencePipe = null;
            Plan = null;
        }

        /// <summary>窗口关闭时的收尾。可重复调用。</summary>
        internal void Close()
        {
            try { PipePickTool.End(); }
            catch { }
            try { Preview.Clear(); }
            catch { }
            try { Log.Flush(); }
            catch { }
        }

        /// <summary>把当前运行参数写回配置文件，返回写入路径。</summary>
        internal string SaveOptions()
        {
            string path = PipeAlignOptionsStore.Save(Options);
            OptionsPath = path;
            return path;
        }

        internal string DescribeTolerance()
        {
            return string.Format(CultureInfo.InvariantCulture,
                "水平容差 {0:G} mm；已对齐容差 {1:G} mm；连接校验 {2}",
                Options.HorizontalToleranceMm, Options.AlignmentToleranceMm,
                PipeTopologyCheckModes.Chinese(Options.TopologyCheckMode));
        }
    }
}
