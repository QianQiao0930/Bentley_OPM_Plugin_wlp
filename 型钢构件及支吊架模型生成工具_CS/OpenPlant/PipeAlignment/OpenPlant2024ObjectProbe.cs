using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.Building.Mechanical.Components;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// OpenPlant Modeler 2024 的探针实现（开发指南 §20 的版本适配层）。
    /// <para>
    /// 两个职责：
    /// </para>
    /// <list type="number">
    /// <item><description>读连接关系：<c>BMECObject.Ports</c> + <c>Port.IsConnected</c> + <c>Port.ConnectedTo</c>。</description></item>
    /// <item><description>探测几何修改接口：<c>BMECObject.GetNthPoint</c> 与 <c>Transform3d</c> 的坐标单位，
    /// 用元素自己的几何去验证，验证通过才允许后续用它移动。</description></item>
    /// </list>
    /// <para>只读**类名**与**点坐标**，不去读对端的其它 EC 属性：拿一个可能不存在的属性名
    /// 去问 Bentley 会让 OPM 直接崩掉。</para>
    /// </summary>
    internal sealed class OpenPlant2024ObjectProbe : IOpenPlantObjectProbe
    {
        /// <summary>单位推断的允许相对误差（几何长度与 API 长度的比值）。</summary>
        private const double ScaleRelativeTolerance = 0.02;

        /// <summary>
        /// 坐标核对的允许误差（毫米）。把 API 端点换算成毫米后与几何端点逐分量比较，
        /// 超过该值就认为"这两个坐标描述的不是同一段管"。
        /// </summary>
        private const double CoordinateToleranceMm = 1.0;

        public PipeTopology ReadTopology(IECInstance instance, string selfInstanceId)
        {
            PipeTopology topology = new PipeTopology();
            if (instance == null)
            {
                topology.IsKnown = false;
                topology.ReadWarning = "EC 实例为空。";
                return topology;
            }

            try
            {
                using (OpenPlantObjectFactory.Acquired acquired =
                    OpenPlantObjectFactory.Acquire(selfInstanceId, instance))
                {
                    BMECObject component = acquired.Object;
                    if (component == null || !component.IsValid)
                    {
                        topology.IsKnown = false;
                        topology.ReadWarning = "OpenPlant 业务对象无效。";
                        return topology;
                    }

                    // ---- 来源 1：端口（Port.IsConnected / Port.ConnectedTo）----
                    // 只读，不调 DiscoverConnections* —— 那些名字听着像"读"，实际可能重建连接，
                    // 放在只读的读取阶段（PIPEALIGN DEBUG）会改数据。
                    int portCount = 0;
                    int connectedPortCount = 0;
                    try
                    {
                        List<Port> ports = component.Ports;
                        if (ports != null)
                        {
                            // SDK 的对端查询会刷新同一个 Ports 列表，不能直接遍历活集合。
                            ports = new List<Port>(ports);
                            portCount = ports.Count;
                            int ordinal = 0;
                            foreach (Port port in ports)
                            {
                                if (port == null) { ordinal++; continue; }

                                bool connected;
                                try { connected = port.IsConnected; }
                                catch
                                {
                                    topology.IsKnown = false;
                                    topology.ReadWarning = AppendWarning(topology.ReadWarning, "端口连接状态无法读取。");
                                    connected = false;
                                }
                                if (!connected) { ordinal++; continue; }
                                connectedPortCount++;

                                string otherInstanceId = null;
                                try { otherInstanceId = port.ConnectedTo; }
                                catch { }

                                int portIndex = ordinal;
                                int sdkPortId = ordinal;
                                try { if (port.ID >= 0) sdkPortId = port.ID; }
                                catch { }

                                // ConnectedTo 是对端 PORT 的 ID，不能把端口当成边界构件。
                                BMECObject neighbor = component.GetConnectedComponentAtPort(sdkPortId);
                                IECInstance neighborInstance = neighbor == null ? null : neighbor.Instance;
                                if (neighborInstance == null)
                                {
                                    IECInstance connectedInstance = OpenPlantObjectFactory.ResolveInstance(otherInstanceId);
                                    if (connectedInstance != null)
                                        neighborInstance = BMECApi.Instance.GetPortOwnerComponent(connectedInstance);
                                }
                                if (neighborInstance == null)
                                {
                                    topology.IsKnown = false;
                                    topology.ReadWarning = AppendWarning(topology.ReadWarning,
                                        "已连接端口的所属构件无法解析，不能确认移动范围。");
                                }
                                else if (!IsSelfOrEmpty(neighborInstance.InstanceId, selfInstanceId))
                                    AddConnection(topology, portIndex, neighborInstance.InstanceId,
                                        neighborInstance.ClassDefinition == null ? null : neighborInstance.ClassDefinition.Name);
                                ordinal++;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        topology.IsKnown = false;
                        topology.ReadWarning = "读取端口失败：" + ex.Message;
                    }

                    // ---- 来源 2：ConnectedComponents（API 直接给出的对端对象）----
                    // 纯 getter，没有副作用，所以即使来源 1 是空的也值得试一遍。
                    // 实测动机：Safe Mode 依赖连通性，而用户现场出现过"明显连着邻管却报无连接"，
                    // 多一个来源就多一分把握。
                    int componentCount = 0;
                    try
                    {
                        List<BMECObject> connected = component.ConnectedComponents;
                        if (connected != null)
                        {
                            connected = new List<BMECObject>(connected);
                            componentCount = connected.Count;
                            foreach (BMECObject other in connected)
                            {
                                if (other == null) continue;
                                string otherInstanceId = null;
                                try
                                {
                                    IECInstance otherInstance = other.Instance;
                                    if (otherInstance != null) otherInstanceId = otherInstance.InstanceId;
                                }
                                catch { }

                                if (IsSelfOrEmpty(otherInstanceId, selfInstanceId)) continue;
                                string className = null;
                                try { className = other.ClassName; }
                                catch { }

                                // 端口序号在这一路拿不到，用 -1 表示"未知端口"。
                                AddConnection(topology, -1, otherInstanceId, className);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        topology.IsKnown = false;
                        topology.ReadWarning = AppendWarning(topology.ReadWarning,
                            "读取 ConnectedComponents 失败：" + ex.Message);
                    }

                    topology.ReadSource = string.Format(
                        System.Globalization.CultureInfo.InvariantCulture,
                        "对象来源 {0}；端口 {1} 个（已连 {2}）；ConnectedComponents {3} 个；合并后连接 {4} 条",
                        acquired.Source, portCount, connectedPortCount, componentCount,
                        topology.ConnectionCount);
                }
            }
            catch (Exception ex)
            {
                topology.IsKnown = false;
                topology.ReadWarning = "读取连接关系失败：" + ex.Message;
            }

            return topology;
        }

        private static bool IsSelfOrEmpty(string otherInstanceId, string selfInstanceId)
        {
            if (string.IsNullOrEmpty(otherInstanceId)) return true;
            return !string.IsNullOrEmpty(selfInstanceId)
                && string.Equals(otherInstanceId, selfInstanceId, StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>按对端实例 ID 去重后加入连接（两个来源可能给出同一根管）。</summary>
        private static void AddConnection(PipeTopology topology, int portIndex, string otherInstanceId,
            string otherClassName)
        {
            if (string.IsNullOrEmpty(otherInstanceId)) return;
            foreach (PipeConnection existing in topology.Connections)
            {
                if (string.Equals(existing.OtherInstanceId, otherInstanceId, StringComparison.OrdinalIgnoreCase))
                {
                    // 端口来源比 ConnectedComponents 更具体：已经有的端口号不要被 -1 覆盖。
                    if (existing.PortIndex < 0 && portIndex >= 0) existing.PortIndex = portIndex;
                    if (string.IsNullOrEmpty(existing.OtherClassName) && !string.IsNullOrEmpty(otherClassName))
                        existing.OtherClassName = otherClassName;
                    return;
                }
            }
            topology.Connections.Add(new PipeConnection(portIndex, otherInstanceId, otherClassName, null));
        }

        private static string AppendWarning(string existing, string addition)
        {
            if (string.IsNullOrEmpty(addition)) return existing;
            if (string.IsNullOrEmpty(existing)) return addition;
            return existing + " " + addition;
        }

        /// <summary>
        /// 探测该实例的几何修改接口及其单位。
        /// <para>
        /// 判据（两步都要过）：
        /// </para>
        /// <list type="number">
        /// <item><description><b>长度比</b>：<c>|GetNthPoint(1)−GetNthPoint(0)| ÷ 几何长度</c>
        /// 必须等于已知候选之一（"每毫米多少 UOR" 或 1.0=毫米），否则说明单位不是我们认识的那两种，
        /// 直接拒绝。</description></item>
        /// <item><description><b>坐标比对</b>：把两个 API 端点按该比例换算成毫米，与**独立几何通道**
        /// 读出的管轴端点逐分量比较（两种端点顺序都试），误差必须小于
        /// <see cref="CoordinateToleranceMm"/>。</description></item>
        /// </list>
        /// <para>
        /// ⚠️ 第 2 步是必需的，不是画蛇添足。第 1 步只是**一个标量**，它可能因为"两根管的长度
        /// 恰好差 1000 倍"之类的巧合而成立；而且它无法发现"比例对了但坐标原点 / 轴向不一致"。
        /// 曾经这里把换算方向写反过一次（拿 UOR 去乘"每毫米多少 UOR"），结果在 Z≠0 的管上
        /// 全部误判为"接口不可用"——而 Z=0 的管又因为 0×1000=0 蒙对，正好说明单靠标量不够。
        /// </para>
        /// </summary>
        public PipeMoveProbe ProbeMoveCapability(IECInstance instance, PipeAxis axisMm, double uorPerMm)
        {
            PipeMoveProbe probe = new PipeMoveProbe();
            if (instance == null)
            {
                probe.Detail = "EC 实例为空。";
                return probe;
            }
            if (axisMm == null || axisMm.LengthMm <= 0.0)
            {
                probe.Detail = "没有可信的几何长度，无法标定接口单位。";
                return probe;
            }
            if (uorPerMm <= 0.0)
            {
                probe.Detail = "取不到模型单位换算，无法标定接口单位。";
                return probe;
            }

            BMECObject component = null;
            OpenPlantObjectFactory.Acquired acquired = null;
            try
            {
                acquired = OpenPlantObjectFactory.Acquire(instance.InstanceId, instance);
                component = acquired.Object;
                if (component == null || !component.IsValid)
                {
                    probe.Detail = "OpenPlant 业务对象无效。";
                    return probe;
                }

                DPoint3d p0, p1;
                if (!TryGetLinearPoints(component, out p0, out p1, probe))
                    return probe;

                double apiLength = Distance(p0, p1);
                if (apiLength <= 0.0)
                {
                    probe.Detail = "GetNthPoint 返回的两个端点重合，无法标定单位。";
                    return probe;
                }

                // ---- 第 1 步：长度比必须落在已知候选上 ----
                // inferred = "每毫米多少 API 单位"
                double inferred = apiLength / axisMm.LengthMm;
                bool uorCandidate = RelativeClose(inferred, uorPerMm);
                bool mmCandidate = RelativeClose(inferred, 1.0);
                if (!uorCandidate && !mmCandidate)
                {
                    probe.Detail = string.Format(CultureInfo.InvariantCulture,
                        "GetNthPoint 的长度比 {0:F6} 既不等于「每毫米 UOR」（{1:F6}）也不等于 1，"
                        + "无法确定接口单位，不使用该接口移动。",
                        inferred, uorPerMm);
                    return probe;
                }
                double scale = uorCandidate ? uorPerMm : 1.0;

                // ---- 第 2 步：端点坐标逐分量比对 ----
                double forwardError = PointErrorMm(p0, p1, axisMm, scale);
                double backwardError = PointErrorMm(p1, p0, axisMm, scale);
                double error = Math.Min(forwardError, backwardError);
                if (error > CoordinateToleranceMm)
                {
                    probe.Detail = string.Format(CultureInfo.InvariantCulture,
                        "GetNthPoint 的端点与几何端点对不上：按 {0:F3} 单位/毫米换算后最大分量误差 "
                        + "{1:F3} mm（容差 {2:F1} mm）。API 端点 ({3:F1},{4:F1},{5:F1})→({6:F1},{7:F1},{8:F1})，"
                        + "几何端点 ({9:F3},{10:F3},{11:F3})→({12:F3},{13:F3},{14:F3})，长度比 {15:F6}。"
                        + "因此不确认接口单位，不使用该接口移动。",
                        scale, error, CoordinateToleranceMm,
                        p0.X, p0.Y, p0.Z, p1.X, p1.Y, p1.Z,
                        axisMm.StartXmm, axisMm.StartYmm, axisMm.StartZmm,
                        axisMm.EndXmm, axisMm.EndYmm, axisMm.EndZmm, inferred);
                    return probe;
                }

                probe.ApiUnitsPerMillimeter = scale;
                probe.LinearPointsUsable = true;

                // ---- 顺带核对 Transform3d 的平移是否与几何同源 ----
                // 这一步用**乘**是正确的：把几何端点（毫米）换算成 API 单位再与平移分量比。
                try
                {
                    DTransform3d transform = component.Transform3d;
                    DPoint3d translation = transform.Translation;
                    DPoint3d startApi = ToApiUnits(axisMm.StartXmm, axisMm.StartYmm, axisMm.StartZmm, scale);
                    DPoint3d endApi = ToApiUnits(axisMm.EndXmm, axisMm.EndYmm, axisMm.EndZmm, scale);
                    double toStart = Distance(translation, startApi);
                    double toEnd = Distance(translation, endApi);
                    double nearest = Math.Min(toStart, toEnd);
                    double toleranceApi = CoordinateToleranceMm * scale;
                    probe.TransformUsable = nearest <= toleranceApi;
                    if (!probe.TransformUsable)
                    {
                        probe.Detail = string.Format(CultureInfo.InvariantCulture,
                            "Transform3d 平移 ({0:F1},{1:F1},{2:F1}) 与管轴端点最近距离 {3:F3}，"
                            + "超过容差 {4:F3}（API 单位），Level 2（变换）不可用；Level 1 仍可用。",
                            translation.X, translation.Y, translation.Z, nearest, toleranceApi);
                    }
                }
                catch (Exception ex)
                {
                    probe.TransformUsable = false;
                    probe.Detail = "读取 Transform3d 失败：" + ex.Message + "（Level 1 仍可用）";
                }

                return probe;
            }
            catch (Exception ex)
            {
                probe.Detail = "探测几何修改接口失败：" + ex.Message;
                return probe;
            }
            finally
            {
                if (acquired != null) acquired.Dispose();
            }
        }

        private static bool TryGetLinearPoints(BMECObject component, out DPoint3d start, out DPoint3d end,
            PipeMoveProbe probe)
        {
            start = new DPoint3d();
            end = new DPoint3d();
            try
            {
                start = component.GetNthPoint(0);
                end = component.GetNthPoint(1);
                return true;
            }
            catch (Exception ex)
            {
                probe.Detail = "GetNthPoint 调用失败：" + ex.Message;
                return false;
            }
        }

        /// <summary>
        /// 把 API 端点按 <paramref name="scale"/>（每毫米多少 API 单位）换算成毫米后，
        /// 与几何端点逐分量比较，返回最大分量误差（mm）。
        /// </summary>
        private static double PointErrorMm(DPoint3d apiStart, DPoint3d apiEnd, PipeAxis axisMm, double scale)
        {
            double startError = MaxAbs3(
                apiStart.X / scale - axisMm.StartXmm,
                apiStart.Y / scale - axisMm.StartYmm,
                apiStart.Z / scale - axisMm.StartZmm);
            double endError = MaxAbs3(
                apiEnd.X / scale - axisMm.EndXmm,
                apiEnd.Y / scale - axisMm.EndYmm,
                apiEnd.Z / scale - axisMm.EndZmm);
            return Math.Max(startError, endError);
        }

        private static double MaxAbs3(double a, double b, double c)
        {
            return Math.Max(Math.Abs(a), Math.Max(Math.Abs(b), Math.Abs(c)));
        }

        /// <summary>毫米 → API 单位（乘）。</summary>
        private static DPoint3d ToApiUnits(double xMm, double yMm, double zMm, double scale)
        {
            return new DPoint3d(xMm * scale, yMm * scale, zMm * scale);
        }

        private static double Distance(DPoint3d a, DPoint3d b)
        {
            double dx = a.X - b.X;
            double dy = a.Y - b.Y;
            double dz = a.Z - b.Z;
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        private static bool RelativeClose(double value, double reference)
        {
            if (reference <= 0.0) return false;
            return Math.Abs(value / reference - 1.0) <= ScaleRelativeTolerance;
        }

        private static string ResolveClassName(string instanceId)
        {
            if (string.IsNullOrEmpty(instanceId)) return null;
            try
            {
                IECInstance other = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities
                    .GetInstanceByInstanceId(instanceId);
                if (other == null || other.ClassDefinition == null) return null;
                return other.ClassDefinition.Name;
            }
            catch
            {
                return null;
            }
        }

        private static void Dispose(BMECObject component)
        {
            if (component == null) return;
            try { component.Dispose(); }
            catch { }
        }
    }
}
