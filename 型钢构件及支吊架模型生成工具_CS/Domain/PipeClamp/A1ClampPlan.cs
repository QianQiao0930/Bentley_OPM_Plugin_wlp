namespace SteelSectionProbe
{
    internal sealed class A1ClampPlan
    {
        internal A1ClampRow Row;
        internal double AngleDeg,NutHeightMm,NutAcrossFlatsMm,NutCenterMm,NutLow1Mm,NutLow2Mm;
        internal string PipeNumber,AssemblyTag,AssemblySpecification,BoltSpecification,NutSpecification;
        internal double BoltLengthMm;
        /// <summary>组合支架可按安装面缩短直腿；null 保留 A1 标准 D。</summary>
        internal double? StraightLegMm;
        /// <summary>导向管卡可覆盖腿中心距；null使用A1标准C。</summary>
        internal double? LegSpacingMm;
    }
}
