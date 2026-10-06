namespace PipeAlign
{
    /// <summary>
    /// 读取一根管道时的可选行为。
    /// <para>默认值就是"正式版"的行为，Debug 开关只影响是否多打印信息。</para>
    /// </summary>
    internal sealed class PipeReadOptions
    {
        /// <summary>是否读取连接关系（Safe Mode 的拓扑校验要用）。</summary>
        internal bool ReadTopology { get; set; }

        /// <summary>是否保留元素上**全部** EC 属性（只有 <c>PIPEALIGN DEBUG DUMP</c> 需要）。</summary>
        internal bool KeepAllProperties { get; set; }

        /// <summary>
        /// 手动指定的属性长度单位比例（1.0 = 毫米，1000.0 = 米）。
        /// <c>null</c> 表示自动标定（默认）。
        /// </summary>
        internal double? ManualPropertyLengthScale { get; set; }

        /// <summary>
        /// 跳过"移动能力探测"。复核（<c>PipeGeometryVerifier</c>）只需要几何读数与 EC 变换读数，
        /// 探测要构造 BMECObject 并做多轮比对，没必要在每次复核时重做。
        /// </summary>
        internal bool SkipMoveProbe { get; set; }

        internal PipeReadOptions()
        {
            ReadTopology = true;
        }

        internal static PipeReadOptions ForDebugDump()
        {
            return new PipeReadOptions { ReadTopology = false, KeepAllProperties = true };
        }

        /// <summary>移动之后的复核：只要几何与 EC 变换读数，不要拓扑、不要探测。</summary>
        internal static PipeReadOptions ForVerification()
        {
            return new PipeReadOptions { ReadTopology = false, SkipMoveProbe = true };
        }
    }
}
