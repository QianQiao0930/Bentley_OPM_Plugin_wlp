namespace PipeAlign
{
    /// <summary>
    /// 移动之后的**数据一致性检查**（开发指南 §19、§29）。
    /// <para>
    /// OpenPlant 的修改接口返回成功，不等于模型真的变了：对象可能需要额外的提交 / 更新，
    /// 不同版本的行为也不一致。因此每次移动之后都必须用**独立通道**重新读一遍，
    /// 确认不了就回退并如实报告，绝不当成成功。
    /// </para>
    /// <para>
    /// 复核读两路，缺一不可：元素几何（用户看到的）与 EC 变换矩阵（数据模型里的）。
    /// 只有这样才能区分"没写进去"与"写了但图形没重建"。
    /// </para>
    /// </summary>
    internal interface IPipeGeometryVerifier
    {
        /// <summary>是否具备复核能力（例如存在活动模型）。</summary>
        bool IsAvailable { get; }

        /// <summary>重新读取一根管道的几何与 EC 变换读数。</summary>
        /// <param name="pipe">移动前的管道快照（提供元素身份与移动前的 EC 基线）。</param>
        PipeMoveVerification Verify(PipeInfo pipe);
    }
}
