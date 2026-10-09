using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 管道数据模型（开发指南 §7）。
    /// <para>
    /// 业务层**不得**反复回到元素上读 EC 属性：元素一旦被读取就转换成这个统一对象，
    /// 后续全部计算都跑在这份纯数据上（指南 §7、§37）。这也是本仓库
    /// <c>ComponentPropertyReader</c> 的既有做法 —— Bentley 的 EC 实例只在产生它的
    /// 那次遍历里有效，带出遍历再访问会让 OPM 访问违例。
    /// </para>
    /// <para>所有长度字段单位统一为**毫米**；<c>null</c> 表示该属性在元素上不存在。</para>
    /// </summary>
    internal sealed class PipeInfo
    {
        /// <summary>元素 ID（活动模型 ID 空间）。只用于 Debug 显示与重新取元素。</summary>
        internal bool IsReferenceLine { get; set; }
        internal ulong ElementId { get; set; }

        /// <summary>Element ID 的十六进制文本（日志用，避免 ulong 精度观感问题）。</summary>
        internal string ElementIdText
        {
            get { return "0x" + ElementId.ToString("X", CultureInfo.InvariantCulture); }
        }

        /// <summary>EC 实例 ID（字符串）。移动时用它重新取实例，避免保留已失效的实例对象。</summary>
        internal string InstanceId { get; set; }

        /// <summary>EC Schema 名（如 <c>OpenPlant_3D</c>）。</summary>
        internal string SchemaName { get; set; }

        /// <summary>EC 类名（如 <c>PIPE</c> / <c>PIPE_ELBOW</c>）。</summary>
        internal string ClassName { get; set; }

        /// <summary>中心线（mm）。取不到中心线时为 <c>null</c>，该管道不可用于对齐。</summary>
        internal PipeAxis Axis { get; set; }

        /// <summary>中心线来源说明（几何通道 / 显示几何 / 包围盒近似），用于 Debug 与提示。</summary>
        internal string AxisSource { get; set; }

        /// <summary>外径 Do（mm）。</summary>
        internal double? OutsideDiameterMm { get; set; }

        /// <summary>公称直径 DN（mm）。</summary>
        internal double? NominalDiameterMm { get; set; }

        /// <summary>壁厚（mm）。</summary>
        internal double? WallThicknessMm { get; set; }

        /// <summary>保温层厚度 Tinsulation（mm）。</summary>
        internal double? InsulationThicknessMm { get; set; }

        /// <summary>保温材料名（文本属性 <c>INSULATION</c>）。</summary>
        internal string InsulationMaterial { get; set; }

        /// <summary>管线号（<c>LINENUMBER</c>）。</summary>
        internal string PipeNumber { get; set; }

        /// <summary>管道等级（<c>SPECIFICATION</c>）。</summary>
        internal string Specification { get; set; }

        /// <summary>只读元素（参考文件 / 锁定文件）：不得修改。</summary>
        internal bool IsReadOnly { get; set; }

        /// <summary>元素被锁定（Lock）：不得修改。</summary>
        internal bool IsLocked { get; set; }

        /// <summary>是否来自参考文件（reference）。参考文件只能读、不能改。</summary>
        internal bool IsFromReference { get; set; }

        /// <summary>EC 长度类属性到 mm 的换算比例（1.0 = 毫米，1000.0 = 米）。</summary>
        internal double PropertyLengthScale { get; set; }
        internal double? EcLengthRaw { get; set; }

        /// <summary>
        /// EC 变换矩阵的 Z 平移分量原始值（<c>TRANSFORMATION_MATRIX.M11</c>）。
        /// <para>
        /// **只用于诊断**：移动之后重新读一遍，就能区分"改动没写进数据模型"与
        /// "数据模型更新了但图形没重建"—— 这两种失败的修法完全不同。
        /// 读法是从已经枚举出来的属性名里取（绝不拿可能不存在的名字去问 Bentley）。
        /// </para>
        /// </summary>
        internal double? EcTranslationZRaw { get; set; }

        /// <summary>该实例所在模型"每个子单位多少 UOR"（<c>GetUORPerSubForCurrentDgn</c>），EC 变换用它换算。</summary>
        internal double EcUorPerSub { get; set; }

        /// <summary>该比例的来源：calibrated / manual / heuristic / default。</summary>
        internal string PropertyLengthScaleSource { get; set; }

        /// <summary>需要展示给用户的读取提示（单位标定可疑等），没有则为 <c>null</c>。</summary>
        internal string ReadWarning { get; set; }

        /// <summary>
        /// 元素身份（含**所属模型引用**）。
        /// <para>
        /// 由 Data 层写入、由 App 层原样带回 <c>PipeElementReader.Read</c>，**Domain 不解释它的内容**
        /// （所以这里只能是 <c>object</c>，不能是 Bentley 类型 —— Domain 必须保持可离线编译）。
        /// </para>
        /// <para>
        /// 为什么必须带着它：ElementId 只在**它自己那个文件的 ID 空间**里有效。
        /// 参考文件里的管道与活动模型里的某个元素完全可能同号，重新读取时若丢掉模型引用，
        /// 就会读成**另一个构件**（表现为"标高突然全变了"），甚至把参考元素误判成可改。
        /// </para>
        /// </summary>
        internal object Source { get; set; }

        /// <summary>连接关系摘要（开发指南 §21）。</summary>
        internal PipeTopology Topology { get; set; }

        /// <summary>
        /// 该元素上探测出来的几何修改能力与单位（开发指南 §18 的分级移动依据）。
        /// 读取阶段探测一次，移动阶段直接用，不再重复探测。
        /// </summary>
        internal PipeMoveProbe MoveProbe { get; set; }

        /// <summary>全部 EC 属性（<c>Schema.Class.属性名</c> → 文本值），仅 Debug 模式使用。</summary>
        internal List<KeyValuePair<string, string>> AllProperties { get; private set; }

        internal PipeInfo()
        {
            PropertyLengthScale = 1.0;
            PropertyLengthScaleSource = "default";
            AllProperties = new List<KeyValuePair<string, string>>();
            Topology = new PipeTopology();
            MoveProbe = new PipeMoveProbe();
        }

        /// <summary>
        /// 用于计算顶部 / 底部标高的有效外径（开发指南 §10）：
        /// 裸管 Deff = Do；保温外表面 Deff = Do + 2 × Tinsulation。
        /// </summary>
        internal double EffectiveDiameterMm(SurfaceMode surfaceMode)
        {
            double outside = OutsideDiameterMm ?? 0.0;
            if (surfaceMode != SurfaceMode.Insulation) return outside;
            return outside + 2.0 * (InsulationThicknessMm ?? 0.0);
        }

        /// <summary>是否有可用的外径（没有外径就算不出管底 / 管顶）。</summary>
        internal bool HasOutsideDiameter
        {
            get { return OutsideDiameterMm.HasValue && OutsideDiameterMm.Value > 0.0; }
        }

        /// <summary>是否选择了保温外表面但该管没有保温厚度 —— 需要提示用户。</summary>
        internal bool LacksInsulationThickness
        {
            get { return !InsulationThicknessMm.HasValue || InsulationThicknessMm.Value <= 0.0; }
        }

        internal string DisplayName
        {
            get
            {
                if (!string.IsNullOrEmpty(PipeNumber)) return PipeNumber;
                if (!string.IsNullOrEmpty(ClassName)) return ClassName + " " + ElementIdText;
                return ElementIdText;
            }
        }

        public override string ToString()
        {
            return string.Format(CultureInfo.InvariantCulture,
                "{0} [{1}] Do={2} Tins={3} {4}",
                DisplayName, ClassName,
                OutsideDiameterMm.HasValue ? OutsideDiameterMm.Value.ToString("F1", CultureInfo.InvariantCulture) : "?",
                InsulationThicknessMm.HasValue ? InsulationThicknessMm.Value.ToString("F1", CultureInfo.InvariantCulture) : "?",
                Axis == null ? "无中心线" : Axis.ToString());
        }
    }
}
