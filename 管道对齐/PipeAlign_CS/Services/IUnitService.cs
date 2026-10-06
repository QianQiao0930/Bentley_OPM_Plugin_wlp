namespace PipeAlign
{
    /// <summary>
    /// 单位服务（开发指南 §17）。
    /// <para>
    /// 业务计算**统一使用毫米**；DGN 存储单位（UOR）换算只发生在 Bentley 边界。
    /// 程序不得在各函数里重复写一套 UOR 换算。
    /// </para>
    /// </summary>
    internal interface IUnitService
    {
        /// <summary>UOR → 毫米。</summary>
        double UorToMillimeter(double value);

        /// <summary>毫米 → UOR。</summary>
        double MillimeterToUor(double value);

        /// <summary>当前模型每个毫米对应多少 UOR（自检与日志用）。</summary>
        double UorPerMillimeter { get; }

        /// <summary>该单位服务是否已成功绑定到一个 DGN 模型。</summary>
        bool IsAvailable { get; }
    }
}
