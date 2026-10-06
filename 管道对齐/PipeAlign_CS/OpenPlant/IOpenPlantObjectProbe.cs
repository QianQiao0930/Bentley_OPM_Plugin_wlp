using Bentley.ECObjects.Instance;

namespace PipeAlign
{
    /// <summary>
    /// OpenPlant 业务对象访问探针。
    /// <para>
    /// ⚠️ 两个方法都**只能在产生 <paramref name="instance"/> 的那次 EC 遍历内调用**：
    /// 实例出了遍历就失效，再访问会让 OPM 访问违例、进程直接消失（catch 不到）。
    /// 实现必须把结果读成纯数据返回，不得把实例存起来。
    /// </para>
    /// <para>
    /// 抽出接口是为了让 <c>Data/PipeElementReader</c> 不直接依赖具体的 OpenPlant 版本
    /// （开发指南 §20 的版本适配层），同时让读取流程可以在没有 OPM 宿主的自检里被绕开。
    /// </para>
    /// </summary>
    internal interface IOpenPlantObjectProbe
    {
        /// <summary>读取一个管道实例的连接关系（开发指南 §21）。</summary>
        PipeTopology ReadTopology(IECInstance instance, string selfInstanceId);

        /// <summary>
        /// 探测该实例的几何修改接口及其单位（开发指南 §18、§40 Phase 1）。
        /// </summary>
        /// <param name="instance">正在遍历中的 EC 实例。</param>
        /// <param name="axisMm">该管由**独立几何通道**读出的中心线（毫米，永远可信）。</param>
        /// <param name="uorPerMm">当前模型每毫米多少 UOR。</param>
        PipeMoveProbe ProbeMoveCapability(IECInstance instance, PipeAxis axisMm, double uorPerMm);
    }
}
