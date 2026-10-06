using Bentley.ECObjects.Instance;
using System.Collections.Generic;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// OpenPlant 版本适配接口（开发指南 §20）。
    /// <para>
    /// 业务代码只调用本接口；版本相关的 API（<c>BMECObject</c> / <c>BMECApi</c> 等）
    /// 全部收在实现类里，这样 OPM 升级时只需要动实现。
    /// </para>
    /// <para>
    /// 与指南 §20 的 <c>IOpenPlantPipeAdapter</c> 对照：
    /// <c>GetPipeInfo</c> 的数据读取改为由 <c>Data/PipeElementReader</c> 承担（它需要
    /// 遵守"EC 实例不带出遍历"的铁律，放在读取层更安全）；
    /// <c>GetConnectedComponents</c> / <c>ValidateConnections</c> 由
    /// <see cref="IOpenPlantObjectProbe"/> 实现（连接关系必须在实例生存期内读）；
    /// 因此本接口聚焦"能不能改、怎么改"。
    /// </para>
    /// </summary>
    internal interface IOpenPlantPipeAdapter
    {
        /// <summary>适配器名（探测信息与日志用）。</summary>
        string Name { get; }

        /// <summary>该 EC 实例是不是管道（<c>PIPE</c> 或其有效派生类）。</summary>
        bool IsPipe(IECInstance instance);

        /// <summary>该管道现在能不能移动；不能时给出中文原因。</summary>
        bool CanMove(PipeInfo pipe, IUnitService units, out string reason);

        /// <summary>
        /// 按指定层级移动一根管道（开发指南 §18）。
        /// <para>返回的只是"接口调用结果"；**是否真的生效必须由调用方复核几何**。</para>
        /// </summary>
        PipeMoveAttempt MovePipe(PipeInfo pipe, double deltaZmm, PipeMoveLevel level, IUnitService units);
        bool DeferConnectionUpdates { get; set; }
        PipeMoveAttempt SetPipeAxis(PipeInfo pipe, PipeAxis target, IUnitService units);
        bool CanSetPipeAxis(PipeInfo pipe, PipeAxis target, IUnitService units, out string reason);
        void UpdateBatchConnections(IList<PipeInfo> pipes);
    }
}
