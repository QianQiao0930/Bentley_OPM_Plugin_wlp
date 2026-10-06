using System;
using System.Globalization;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace PipeAlign
{
    /// <summary>
    /// OpenPlant Modeler 2024 的移动实现（开发指南 §18 / §20）。
    /// <para>三级策略：</para>
    /// <list type="number">
    /// <item><description><b>Level 1</b>：<c>BMECObject.SetLinearPoints</c> 按管轴两端点改位置。</description></item>
    /// <item><description><b>Level 2</b>：<c>BMECObject.Transform3d</c> 的平移分量 +ΔZ。</description></item>
    /// <item><description><b>Level 3</b>：DGN 图形变换（<c>Element.ApplyTransform</c>）。指南 §19 明确禁止
    /// 当作正式实现，**默认关闭**。</description></item>
    /// </list>
    /// <para>
    /// ⚠️ 两个真机实测换来的教训，改这个文件前务必先读：
    /// </para>
    /// <list type="number">
    /// <item><description>
    /// **对象必须通过 OpenPlant API 取，不能 <c>new</c>。** 第一版用
    /// <c>new BMECObject(instance)</c>，结果 <c>SetLinearPoints</c> / <c>Transform3d</c> 全都不报错、
    /// 读数却纹丝不动 —— 拿到的是没挂到文档上的副本。正确做法是先查
    /// <c>BMECApi.Instance.ObjectCache.FindByInstanceId</c>，没有就用
    /// <c>BMECApi.CreateBMECObjectForInstance</c> 创建并加入缓存（见 <see cref="AcquireComponent"/>）。
    /// </description></item>
    /// <item><description>
    /// **改完还要显式"写出去"。** 只设值不够，需要把对象标记为允许图形更新
    /// （<c>AllowGraphicsUpdate</c>）并走一遍 <c>Refresh</c> / <c>Resync</c> /
    /// <c>DiscoverConnectionsEx</c> / <c>UpdateConnections</c> / <c>BMECObjectWriter.Serialize</c>。
    /// 每一步都记进尝试记录，这样万一还不行，日志能直接指出卡在哪一步。
    /// </description></item>
    /// </list>
    /// <para>
    /// 另外：接口调用返回成功**不等于**模型真的变了。生效与否由
    /// <c>Services/PipeMoveService</c> 用独立读到的几何与 EC 变换复核 —— 这正是指南 §19 要求的
    /// "必须执行数据一致性检查"。
    /// </para>
    /// </summary>
    internal sealed class OpenPlant2024PipeAdapter : IOpenPlantPipeAdapter
    {
        public bool DeferConnectionUpdates { get; set; }

        public bool CanSetPipeAxis(PipeInfo pipe, PipeAxis target, IUnitService units, out string reason)
        {
            reason = null;
            try
            {
                if (!CanMove(pipe, units, out reason)) return false;
                if (target == null || pipe.Axis == null || pipe.MoveProbe == null || !pipe.MoveProbe.LinearPointsUsable
                    || PipeConnectionClassifier.Classify(pipe.ClassName) != PipeConnectionKind.Pipe)
                    throw new InvalidOperationException("立管没有可用的端点接口。");
                if (!pipe.EcLengthRaw.HasValue || pipe.PropertyLengthScale <= 0.0
                    || Math.Abs(pipe.EcLengthRaw.Value * pipe.PropertyLengthScale - pipe.Axis.LengthMm) > 1.0)
                    throw new InvalidOperationException("立管 LENGTH 单位未标定。");
                using (var acquired = OpenPlantObjectFactory.Acquire(pipe.InstanceId, ResolveInstance(pipe.InstanceId)))
                {
                    if (acquired.Object == null || !acquired.Object.IsValid || acquired.OwnsObject)
                        throw new InvalidOperationException("没有可写的 OpenPlant 立管对象。");
                    double minimum = BMECApi.GetMinimumPipeLengthInMM(acquired.Object);
                    if (double.IsNaN(minimum) || double.IsInfinity(minimum) || minimum < 0.0 || target.LengthMm < minimum)
                        throw new InvalidOperationException("立管新长度不满足 OpenPlant 最小安装管长。");
                }
                return true;
            }
            catch (Exception ex) { reason = ex.Message; return false; }
        }

        public PipeMoveAttempt SetPipeAxis(PipeInfo pipe, PipeAxis target, IUnitService units)
        {
            var attempt = new PipeMoveAttempt { Level = "OpenPlant 立管单端伸缩" };
            try
            {
                string reason;
                if (!CanMove(pipe, units, out reason)) throw new InvalidOperationException(reason);
                if (target == null || pipe.MoveProbe == null || !pipe.MoveProbe.LinearPointsUsable
                    || PipeConnectionClassifier.Classify(pipe.ClassName) != PipeConnectionKind.Pipe)
                    throw new InvalidOperationException("未证实该直管的端点接口，不能伸缩。");
                if (!pipe.EcLengthRaw.HasValue || pipe.PropertyLengthScale <= 0.0
                    || Math.Abs(pipe.EcLengthRaw.Value * pipe.PropertyLengthScale - pipe.Axis.LengthMm) > 1.0)
                    throw new InvalidOperationException("立管 LENGTH 单位未标定，不能验证伸缩后的数据长度。");
                using (var acquired = OpenPlantObjectFactory.Acquire(pipe.InstanceId, ResolveInstance(pipe.InstanceId)))
                {
                    BMECObject component = acquired.Object;
                    if (component == null || !component.IsValid || acquired.OwnsObject)
                        throw new InvalidOperationException("立管未取得挂到文档的业务对象。");
                    component.Refresh();
                    component.Resync();
                    double scale = pipe.MoveProbe.ApiUnitsPerMillimeter;
                    DPoint3d start = component.GetNthPoint(0);
                    DPoint3d end = component.GetNthPoint(1);
                    bool forward = PointMatches(start, pipe.Axis, true, scale) && PointMatches(end, pipe.Axis, false, scale);
                    bool backward = PointMatches(start, pipe.Axis, false, scale) && PointMatches(end, pipe.Axis, true, scale);
                    if (!forward && !backward) throw new InvalidOperationException("立管端点已改变，请重新预览。");
                    double minimum = BMECApi.GetMinimumPipeLengthInMM(component);
                    if (double.IsNaN(minimum) || double.IsInfinity(minimum) || minimum < 0.0)
                        throw new InvalidOperationException("OpenPlant 未返回可信的最小管长。");
                    if (target.LengthMm < minimum) throw new InvalidOperationException("立管新长度小于 OpenPlant 最小安装管长。");
                    component.AllowGraphicsUpdate = true;
                    component.SetLinearPoints(ApiPoint(target, forward, scale), ApiPoint(target, !forward, scale));
                    bool written = PersistImmediately(component, attempt);
                    attempt.Trace("SetLinearPoints + Serialize=" + written);
                    if (!written) throw new InvalidOperationException("OpenPlant 立管写回失败。");
                    component.Refresh();
                    component.Resync();
                    attempt.Succeeded = true;
                }
            }
            catch (Exception ex) { attempt.FailureReason = ex.Message; }
            return attempt;
        }

        private static DPoint3d ApiPoint(PipeAxis axis, bool start, double scale)
        {
            return start ? new DPoint3d(axis.StartXmm * scale, axis.StartYmm * scale, axis.StartZmm * scale)
                : new DPoint3d(axis.EndXmm * scale, axis.EndYmm * scale, axis.EndZmm * scale);
        }

        private static bool PointMatches(DPoint3d point, PipeAxis axis, bool start, double scale)
        {
            DPoint3d expected = ApiPoint(axis, start, scale);
            return Math.Abs(point.X - expected.X) <= scale && Math.Abs(point.Y - expected.Y) <= scale
                && Math.Abs(point.Z - expected.Z) <= scale;
        }

        public void UpdateBatchConnections(IList<PipeInfo> pipes)
        {
            var objects = new List<BMECObject>();
            foreach (PipeInfo pipe in pipes)
            {
                using (var acquired = OpenPlantObjectFactory.Acquire(pipe.InstanceId, ResolveInstance(pipe.InstanceId)))
                {
                    if (acquired.Object == null || !acquired.Object.IsValid || acquired.OwnsObject)
                        throw new InvalidOperationException("更新连接时无法取得业务对象：" + pipe.DisplayName);
                    acquired.Object.Refresh();
                    acquired.Object.Resync();
                    objects.Add(acquired.Object);
                }
            }
            // 所有成员位置写回之后才允许连接重建，避免组内中间状态断开关系。
            foreach (BMECObject component in objects) component.DiscoverConnectionsEx();
            foreach (BMECObject component in objects) component.UpdateConnections();
        }
        public string Name { get { return "OpenPlant Modeler 2024"; } }

        public bool IsPipe(IECInstance instance)
        {
            if (instance == null) return false;
            try
            {
                var schema = instance.ClassDefinition == null ? null : instance.ClassDefinition.Schema;
                string schemaName = schema == null ? null : schema.Name;
                // 与 Data/PipeElementReader 同一条规则：实例资格只由 schema 决定。
                if (string.IsNullOrEmpty(schemaName)
                    || !schemaName.StartsWith("OpenPlant", StringComparison.OrdinalIgnoreCase))
                    return false;
                try
                {
                    return SchemaUtilities.IsPipingComponent(instance);
                }
                catch
                {
                    string className = instance.ClassDefinition.Name;
                    return !string.IsNullOrEmpty(className)
                        && className.StartsWith("PIPE", StringComparison.OrdinalIgnoreCase);
                }
            }
            catch
            {
                return false;
            }
        }

        public bool CanMove(PipeInfo pipe, IUnitService units, out string reason)
        {
            reason = null;
            if (pipe == null) { reason = "管道数据为空。"; return false; }
            if (pipe.IsFromReference) { reason = "该管道位于参考文件中，参考文件不可修改。"; return false; }
            if (pipe.IsReadOnly) { reason = "该管道所在模型是只读的。"; return false; }
            if (pipe.IsLocked) { reason = "该管道已被锁定。"; return false; }
            if (string.IsNullOrEmpty(pipe.InstanceId))
            {
                reason = "取不到该管道的 OpenPlant 实例 ID，无法定位要修改的对象。";
                return false;
            }
            if (units == null || !units.IsAvailable)
            {
                reason = "取不到模型单位换算系数，无法换算位移。";
                return false;
            }
            return true;
        }

        public PipeMoveAttempt MovePipe(PipeInfo pipe, double deltaZmm, PipeMoveLevel level, IUnitService units)
        {
            PipeMoveAttempt attempt = new PipeMoveAttempt();
            attempt.Level = PipeMoveLevels.Chinese(level);

            string canMoveReason;
            if (!CanMove(pipe, units, out canMoveReason))
            {
                attempt.FailureReason = canMoveReason;
                return attempt;
            }

            if (deltaZmm == 0.0)
            {
                attempt.Succeeded = true;
                attempt.Trace("位移为 0，不需要修改。");
                return attempt;
            }

            if (level == PipeMoveLevel.GraphicsTransform)
                return MoveByGraphics(pipe, deltaZmm, units, attempt);

            OpenPlantObjectFactory.Acquired acquired = null;
            BMECObject component = null;
            try
            {
                IECInstance instance = ResolveInstance(pipe.InstanceId);
                acquired = OpenPlantObjectFactory.Acquire(pipe.InstanceId, instance);
                component = acquired.Object;
                if (instance == null && component != null && component.IsValid)
                    instance = component.Instance;
                if (instance == null)
                {
                    attempt.FailureReason = "按实例 ID 取不到 OpenPlant 实例（模型可能已被修改，请重新选择管道）。";
                    return attempt;
                }

                attempt.Trace("对象来源：" + acquired.Source);
                if (component == null || !component.IsValid || acquired.OwnsObject)
                {
                    attempt.FailureReason = "未取得挂到文档上的 OpenPlant 业务对象，未执行移动。";
                    return attempt;
                }

                // 上一级事务回退后，缓存对象也必须重新读取持久化基线。
                component.Refresh();
                component.Resync();

                // 允许图形更新：不允许时改了数据也看不见。
                try
                {
                    component.AllowGraphicsUpdate = true;
                }
                catch (Exception ex)
                {
                    attempt.Trace("设置 AllowGraphicsUpdate 失败（继续）：" + ex.Message);
                }

                attempt.Trace("修改前对象读数：" + DescribePoints(component));

                if (level == PipeMoveLevel.ObjectEcTransform)
                    MoveByEcTransform(component, pipe, instance, deltaZmm, attempt, !DeferConnectionUpdates);
                else if (level == PipeMoveLevel.ObjectLinearPoints)
                    MoveByLinearPoints(component, pipe, deltaZmm, attempt);
                else
                    MoveByTransform(component, pipe, deltaZmm, attempt);

                if (!attempt.Succeeded) return attempt;

                // 改完立刻看对象自己认不认这个改动 —— 这一步能把"接口是空操作"和
                // "改了内存没写回模型"分开。
                attempt.Trace("修改后对象读数：" + DescribePoints(component));

                if (level != PipeMoveLevel.ObjectEcTransform)
                    WriteOut(component, attempt, !DeferConnectionUpdates);

                return attempt;
            }
            catch (Exception ex)
            {
                attempt.Succeeded = false;
                attempt.FailureReason = ex.Message;
                attempt.Trace("异常：" + ex.GetType().Name + "：" + ex.Message);
                return attempt;
            }
            finally
            {
                // 只释放"我们自己 new 出来"的对象；来自 API 缓存 / 工厂的对象归 API 所有，
                // 释放它们会把缓存里的活对象销毁掉（由 Acquired 统一判断）。
                if (acquired != null) acquired.Dispose();
            }
        }

        /// <summary>
        /// 取"挂到文档上"的 OpenPlant 业务对象 —— 见 <see cref="OpenPlantObjectFactory"/>。
        /// </summary>
        private static BMECObject AcquireComponent(string instanceId, IECInstance instance,
            PipeMoveAttempt attempt, out bool ownsObject)
        {
            OpenPlantObjectFactory.Acquired acquired = OpenPlantObjectFactory.Acquire(instanceId, instance);
            ownsObject = acquired.OwnsObject;
            attempt.Trace("对象来源：" + acquired.Source);
            // 这里不能 Dispose：要把对象交给调用方继续用，所有权跟着 ownsObject 走。
            return acquired.Object;
        }

        /// <summary>
        /// Level 1：按管轴两端点改位置。
        /// <para>
        /// 端点坐标的单位来自读取阶段在该元素上探测出的
        /// <see cref="PipeMoveProbe.ApiUnitsPerMillimeter"/>（实测确认为 UOR）；
        /// 没有探测结论时**拒绝执行**，绝不用一个没被证实的单位去写模型。
        /// </para>
        /// </summary>
        private static void MoveByLinearPoints(BMECObject component, PipeInfo pipe,
            double deltaZmm, PipeMoveAttempt attempt)
        {
            if (pipe.MoveProbe == null || !pipe.MoveProbe.LinearPointsUsable)
            {
                attempt.Succeeded = false;
                attempt.FailureReason = "该元素上未证实 Level 1 接口的坐标单位，未执行。"
                    + (pipe.MoveProbe == null ? "" : "（" + pipe.MoveProbe.Detail + "）");
                return;
            }

            double scale = pipe.MoveProbe.ApiUnitsPerMillimeter;
            double deltaApi = deltaZmm * scale;

            DPoint3d start = component.GetNthPoint(0);
            DPoint3d end = component.GetNthPoint(1);
            attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                "GetNthPoint：({0:F3},{1:F3},{2:F3}) → ({3:F3},{4:F3},{5:F3})，单位/毫米 {6:F6}",
                start.X, start.Y, start.Z, end.X, end.Y, end.Z, scale));

            start.Z += deltaApi;
            end.Z += deltaApi;
            component.SetLinearPoints(start, end);

            attempt.Succeeded = true;
            attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                "SetLinearPoints 已调用，ΔZ = {0:F3} mm（{1:F3} API 单位）", deltaZmm, deltaApi));
        }

        /// <summary>Level 2：改对象变换的平移分量。</summary>
        private static void MoveByTransform(BMECObject component, PipeInfo pipe,
            double deltaZmm, PipeMoveAttempt attempt)
        {
            if (pipe.MoveProbe == null || !pipe.MoveProbe.TransformUsable)
            {
                attempt.Succeeded = false;
                attempt.FailureReason = "该元素上未证实 Level 2 变换接口与几何一致，未执行。"
                    + (pipe.MoveProbe == null ? "" : "（" + pipe.MoveProbe.Detail + "）");
                return;
            }

            double scale = pipe.MoveProbe.ApiUnitsPerMillimeter;
            double deltaApi = deltaZmm * scale;

            DTransform3d transform = component.Transform3d;
            DPoint3d translation = transform.Translation;
            attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                "Transform3d 平移：({0:F3},{1:F3},{2:F3})，单位/毫米 {3:F6}",
                translation.X, translation.Y, translation.Z, scale));

            transform.Translation = new DPoint3d(translation.X, translation.Y, translation.Z + deltaApi);
            component.Transform3d = transform;

            attempt.Succeeded = true;
            attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                "Transform3d 已写回，ΔZ = {0:F3} mm（{1:F3} API 单位）", deltaZmm, deltaApi));
        }

        /// <summary>
        /// 把**内存里已经改好的**位置推送到数据模型。
        /// <para>
        /// ⚠️ 顺序是实测逼出来的，不能凭直觉调整。第二版把
        /// <c>Refresh</c> / <c>Resync</c> 放在最前面，结果它们把改动**抹掉了**：
        /// 日志里"修改后对象读数"是 39700.000（改动已被接受），
        /// "Refresh/Resync 后对象读数"又回到 374028.935。
        /// 也就是说 <c>Refresh</c> 的语义是**从数据模型读回来**，不是写出去 ——
        /// 它适合放在写回**之后**用来刷新内存副本，放在之前就是自杀。
        /// </para>
        /// <para>注意这里**不做** EC 直写：那是独立的 Level 2b，中间隔着复核与回退，
        /// 结构上保证位移不会被叠加两次。</para>
        /// </summary>
        private static bool PersistImmediately(BMECObject component, PipeMoveAttempt attempt)
        {
            // SDK Serialize 调用 Create；Create 在 DeferCommits=true 时只排入待提交集合。
            // 不提交全局 DeferedChangeSet（可能含其他工具的改动），只使本次对象写回即时提交。
            BMECApi api = BMECApi.Instance;
            bool deferred = api.DeferCommits;
            attempt.Trace("写回前 DeferCommits=" + deferred);
            try
            {
                api.DeferCommits = false;
                return new BMECObjectWriter(component).Serialize();
            }
            finally
            {
                api.DeferCommits = deferred;
                attempt.Trace("已恢复 DeferCommits=" + deferred);
            }
        }

        private static void WriteOut(BMECObject component, PipeMoveAttempt attempt, bool updateConnections)
        {
            // ---- 第 1 步：OpenPlant 自己的序列化器（必须在 Refresh 之前）----
            try
            {
                bool serialized = PersistImmediately(component, attempt);
                attempt.Trace("BMECObjectWriter.Serialize = " + (serialized ? "true" : "false"));
                if (!serialized) throw new InvalidOperationException("OpenPlant 对象持久化返回失败。");
            }
            catch (Exception ex)
            {
                attempt.Trace("BMECObjectWriter.Serialize 失败：" + ex.Message);
                throw;
            }
            attempt.Trace("Serialize 后对象读数：" + DescribePoints(component));

            // ---- 第 2 步：到这里才刷新（Refresh 是"读回来"，只能放在写回之后）----
            Step(attempt, "Refresh", delegate { component.Refresh(); });
            Step(attempt, "Resync", delegate { component.Resync(); });
            attempt.Trace("Refresh/Resync 后对象读数：" + DescribePoints(component));

            if (updateConnections)
            {
                Step(attempt, "DiscoverConnectionsEx", delegate { component.DiscoverConnectionsEx(); });
                Step(attempt, "UpdateConnections", delegate { component.UpdateConnections(); });
            }
            attempt.Trace("连接更新后对象读数：" + DescribePoints(component));
        }

        /// <summary>
        /// Level 2b：直接写 EC 变换矩阵并提交，然后刷新对象 / 连接。
        /// <para>
        /// 它单独成一级（而不是挂在 Level 2 的写回链尾巴上）是**必须的**：
        /// 若 Level 2 其实已经写成功，多出来的直写会把位移**叠加两次**。
        /// 分成两级、中间隔着 <c>PipeMoveService</c> 的复核与回退，就不会叠加。
        /// </para>
        /// </summary>
        private static void MoveByEcTransform(BMECObject component, PipeInfo pipe, IECInstance instance,
            double deltaZmm, PipeMoveAttempt attempt, bool updateConnections)
        {
            if (!TryPersistEcTransform(pipe, instance, deltaZmm, attempt))
            {
                // TryPersistEcTransform 已把原因写进尝试记录。
                attempt.Succeeded = false;
                attempt.FailureReason = "EC 变换直写未执行（见逐级记录）。";
                return;
            }

            attempt.Succeeded = true;
            Step(attempt, "Refresh", delegate { component.Refresh(); });
            Step(attempt, "Resync", delegate { component.Resync(); });
            if (updateConnections)
            {
                Step(attempt, "DiscoverConnectionsEx", delegate { component.DiscoverConnectionsEx(); });
                Step(attempt, "UpdateConnections", delegate { component.UpdateConnections(); });
            }
            attempt.Trace("EC 直写后对象读数：" + DescribePoints(component));
        }

        /// <summary>EC 变换矩阵里 Z 平移分量的属性名（与 <c>PipeElementReader</c> 读诊断值时一致）。</summary>
        private const string EcTransformZProperty = "TRANSFORMATION_MATRIX.M11";

        /// <summary>
        /// 直接写 EC 变换并提交（<c>IDgnECInstance.WriteChanges</c>）。
        /// <para>
        /// 为什么需要这条兜底：OpenPlant 对象接口只在**内存副本**上改位置，本版本实测没有
        /// 把改动推回数据模型。而 "写 EC 值之后必须 <c>WriteChanges()</c>" 是本仓库另一侧
        /// （ItemType 写入）踩过的同一个坑。
        /// </para>
        /// <para>
        /// 三重门禁，缺一不做 —— 宁可拒绝也不要瞎写：
        /// </para>
        /// <list type="number">
        /// <item><description>该元素上**已证实**过 API 坐标单位（<see cref="PipeMoveProbe.ApiUnitsPerMillimeter"/>）；</description></item>
        /// <item><description>EC 的 Z 读数与"几何 Z × 单位"吻合 —— 即 EC 变换与 API 坐标同坐标系。
        /// 这一步用**实测数据自己证明**，不靠"文档上说是 UOR"；</description></item>
        /// <item><description>EC 里当前值仍等于移动前的基线（说明确实还没写进去），
        /// 否则跳过 —— 避免把位移叠加两次。</description></item>
        /// </list>
        /// </summary>
        private static bool TryPersistEcTransform(PipeInfo pipe, IECInstance instance,
            double deltaZmm, PipeMoveAttempt attempt)
        {
            double scale = pipe.MoveProbe == null ? 0.0 : pipe.MoveProbe.ApiUnitsPerMillimeter;
            if (scale <= 0.0)
            {
                attempt.Trace("未证实 API 坐标单位，跳过 EC 变换直写。");
                return false;
            }
            if (!pipe.EcTranslationZRaw.HasValue)
            {
                // 读诊断值时没拿到 → 该实例没有这个属性（或读不到）。**不能**再去试一个
                // 可能不存在的属性名：那会让 OPM 直接崩掉。
                attempt.Trace("读取阶段没拿到 TRANSFORMATION_MATRIX.M11，跳过 EC 变换直写。");
                return false;
            }
            if (pipe.Axis == null)
            {
                attempt.Trace("没有几何基线，无法核对 EC 单位，跳过 EC 变换直写。");
                return false;
            }

            // 门禁 2：EC 读数必须与"几何 Z × 单位"吻合，否则说明两者不同坐标系。
            double expectedRaw = pipe.Axis.CenterElevationMm * scale;
            double mismatch = Math.Abs(pipe.EcTranslationZRaw.Value - expectedRaw);
            double allowed = Math.Max(1.0 * scale, Math.Abs(pipe.EcTranslationZRaw.Value) * 0.02);
            if (mismatch > allowed)
            {
                attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                    "EC 变换与 API 坐标不同坐标系（EC M11 = {0:G}，几何 Zc × 单位 = {1:F3}，"
                    + "差 {2:F3}），跳过 EC 变换直写。",
                    pipe.EcTranslationZRaw.Value, expectedRaw, mismatch));
                return false;
            }

            try
            {
                IECPropertyValue value = instance[EcTransformZProperty];
                if (value == null || value.IsNull)
                {
                    attempt.Trace("EC 变换 Z 属性为空，跳过 EC 变换直写。");
                    return false;
                }

                // 门禁 3：仍等于移动前的基线才写，避免重复叠加。
                double current = value.DoubleValue;
                if (Math.Abs(current - pipe.EcTranslationZRaw.Value) > 1.0e-6)
                {
                    attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                        "EC 变换已是 {0:G}（基线 {1:G}），判定已写回，跳过直写。",
                        current, pipe.EcTranslationZRaw.Value));
                    return false;
                }

                var dgnInstance = instance as Bentley.DgnPlatformNET.DgnEC.IDgnECInstance;
                if (dgnInstance == null)
                {
                    attempt.Trace("实例不是 IDgnECInstance，无法 WriteChanges（改动只留在 EC 值上）。");
                    return false;
                }

                double deltaRaw = deltaZmm * scale;
                value.DoubleValue = current + deltaRaw;

                StatusInt status = dgnInstance.WriteChanges();
                attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                    "EC 变换直写：M11 {0:G} → {1:G}（ΔZ = {2:F3} mm = {3:F3}），WriteChanges = {4}",
                    current, current + deltaRaw, deltaZmm, deltaRaw, status));
                return status == StatusInt.Success;
            }
            catch (Exception ex)
            {
                attempt.Trace("EC 变换直写失败：" + ex.Message);
                return false;
            }
        }

        private static void Step(PipeMoveAttempt attempt, string name, Action action)
        {
            try
            {
                action();
                attempt.Trace(name + " 已调用");
            }
            catch (Exception ex)
            {
                attempt.Trace(name + " 失败：" + ex.Message);
            }
        }

        /// <summary>读对象自己的端点，用于判断"改动有没有被对象接受"。</summary>
        private static string DescribePoints(BMECObject component)
        {
            try
            {
                DPoint3d start = component.GetNthPoint(0);
                DPoint3d end = component.GetNthPoint(1);
                return string.Format(CultureInfo.InvariantCulture,
                    "({0:F3},{1:F3},{2:F3}) → ({3:F3},{4:F3},{5:F3})",
                    start.X, start.Y, start.Z, end.X, end.Y, end.Z);
            }
            catch (Exception ex)
            {
                return "读数失败：" + ex.Message;
            }
        }

        /// <summary>
        /// Level 3：DGN 图形变换。**会让 OpenPlant 数据与图形不一致**（指南 §19），
        /// 只在用户明确打开配置项时使用，并且会把 <see cref="PipeMoveAttempt.GraphicsOnly"/> 置位。
        /// </summary>
        private static PipeMoveAttempt MoveByGraphics(PipeInfo pipe, double deltaZmm, IUnitService units,
            PipeMoveAttempt attempt)
        {
            DgnModel model = Session.Instance.GetActiveDgnModel();
            if (model == null)
            {
                attempt.FailureReason = "没有活动模型。";
                return attempt;
            }

            var id = pipe.ElementId;
            Element element = model.FindElementById(new ElementId(ref id));
            if (element == null)
            {
                attempt.FailureReason = "在活动模型里找不到该元素。";
                return attempt;
            }

            double dzUor = units.MillimeterToUor(deltaZmm);
            DTransform3d transform = DTransform3d.Identity;
            transform.Translation = new DPoint3d(0.0, 0.0, dzUor);
            int status = element.ApplyTransform(new TransformInfo(transform));

            attempt.Succeeded = true;
            attempt.GraphicsOnly = true;
            attempt.Trace(string.Format(CultureInfo.InvariantCulture,
                "ApplyTransform 返回 {0}，ΔZ = {1:F3} mm（{2:F3} UOR）", status, deltaZmm, dzUor));
            attempt.Trace("⚠️ 只改了图形：OpenPlant 数据（EC 变换 / 轴测图）可能仍停在旧标高。");
            return attempt;
        }

        private static IECInstance ResolveInstance(string instanceId)
        {
            if (string.IsNullOrEmpty(instanceId)) return null;
            try
            {
                return OpenPlantObjectFactory.ResolveInstance(instanceId);
            }
            catch
            {
                return null;
            }
        }
    }
}
