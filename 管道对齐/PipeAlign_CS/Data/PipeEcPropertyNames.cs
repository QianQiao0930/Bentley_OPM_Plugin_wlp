namespace PipeAlign
{
    /// <summary>
    /// OpenPlant EC 属性的规范名（开发指南 §7、§31）。
    /// <para>
    /// 名字来自仓库已验证的 Python 读取库
    /// （<c>管道信息查询/模块/管道信息/管道信息_读取.py</c> 的 <c>TEXT_PROPERTIES</c> /
    /// <c>LENGTH_PROPERTIES</c>），不是猜的。
    /// </para>
    /// <para>
    /// ⚠️ 绝不能拿一个**可能不存在**的属性名去问 Bentley：<c>ECValue.GetValue()</c> 查
    /// 一个该实例没有的属性会让 OPM 直接崩掉（不是返回错误码，catch 不到）。
    /// 因此读取器一律先用 <c>ECValuesCollection</c> / <c>ClassDefinition.Properties</c>
    /// 枚举出实例上**实际存在**的属性名，只读其中存在的那些。
    /// </para>
    /// </summary>
    internal static class PipeEcPropertyNames
    {
        // ---- 文本类属性 ----
        internal const string PipeNumber = "LINENUMBER";
        internal const string Specification = "SPECIFICATION";
        internal const string Material = "MATERIAL";
        internal const string InsulationMaterial = "INSULATION";
        internal const string ComponentName = "NAME";
        internal const string NominalSize = "NOMINAL_SIZE";

        // ---- 长度类属性（裸 double，单位需标定，见 LengthUnitCalibrator）----
        internal const string Length = "LENGTH";
        internal const string OutsideDiameter = "OUTSIDE_DIAMETER";
        internal const string NominalDiameter = "NOMINAL_DIAMETER";
        internal const string NominalDiameterRunEnd = "NOMINAL_DIAMETER_RUN_END";
        internal const string WallThickness = "WALL_THICKNESS";
        internal const string InsulationThickness = "INSULATION_THICKNESS";
        internal const string Elevation = "ELEVATION";

        // ---- 变换矩阵（12 个分量，M03/M07/M11 是平移）----
        internal const string TransformationMatrixPrefix = "TRANSFORMATION_MATRIX.";

        /// <summary>管道元件类名里出现即认为"这是个管道 / 管道元件"的关键字。</summary>
        internal static readonly string[] PipingClassHints =
        {
            "PIPE", "ELBOW", "TEE", "REDUCER", "FLANGE", "VALVE", "GASKET",
            "COUPLING", "NIPPLE", "BEND", "CAP", "PLUG", "UNION", "CROSS",
            "ADAPTER", "HUB", "BUSHING", "FERRULE", "RETURN", "STUB"
        };
    }
}
