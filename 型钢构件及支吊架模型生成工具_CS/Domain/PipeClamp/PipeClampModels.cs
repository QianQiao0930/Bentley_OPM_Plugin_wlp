using System;

namespace SteelSectionProbe
{
    // ---------------------------------------------------------------------
    // A2 标准型 2 螺栓管夹
    // ---------------------------------------------------------------------

    /// <summary>A2 面板输入。长度单位 mm。</summary>
    internal sealed class A2ClampParameters
    {
        /// <summary>选中直线 / 读不到管道公称直径时使用的管径。</summary>
        internal int FallbackDn=A2ClampCatalog.FallbackDn;
        /// <summary>读不到管道保温厚度时使用的保温厚度。</summary>
        internal double FallbackInsulationMm;
    }

    /// <summary>A2 解析后的全部毫米尺寸与清单规格。</summary>
    internal sealed class A2ClampPlan
    {
        internal int Dn;
        internal double InsulationMm;
        /// <summary>实际采用的尺寸（若按保温放大内孔，A/B 已加大）。</summary>
        internal double InnerDiameterMm,BoltCenterMm,PlateWidthCm,EndOffsetDm;
        internal double PlateThicknessMm,WidthMm;
        internal string Nps,Bolt;
        internal double BoltDiameterMm;

        /// <summary>圆柱外径 = A + 2t。</summary>
        internal double CylinderDiameterMm;
        internal double CylinderRadiusMm;
        /// <summary>长方体沿管轴长度 = A + 2D + 2t。</summary>
        internal double BoxLengthMm;
        /// <summary>长方体垂直管轴宽度 = C + 2t。</summary>
        internal double BoxWidthMm;
        /// <summary>螺栓孔半径 = (F 数字 + 2) / 2。</summary>
        internal double HoleRadiusMm;

        internal int BoltCount;
        internal string AssemblyTag,AssemblySpecification;
        internal string BodySpecification,BoltSpecification;
        internal string CellName;
    }

    // ---------------------------------------------------------------------
    // K1 不保温管限位架
    // ---------------------------------------------------------------------

    /// <summary>K1 面板输入。长度单位 mm。</summary>
    internal sealed class K1LimitParameters
    {
        internal int Dn=K1LimitCatalog.FallbackDn;
        /// <summary>子项；null 表示按 DN 自动选。</summary>
        internal string SubitemKey;
        /// <summary>两限位块内侧面的间距（已有钢构宽）。</summary>
        internal double ExistingWidthMm=K1LimitCatalog.DefaultExistingWidthMm;
        internal string Material=K1LimitCatalog.DefaultMaterial;
    }

    /// <summary>K1 解析后的尺寸、接触高差与编号。</summary>
    internal sealed class K1LimitPlan
    {
        internal int Dn;
        internal string SubitemKey;
        internal double OutsideMm;
        internal string Nps;
        internal double ExistingWidthMm;
        internal double SizeMm;
        internal string SizeLabel;
        /// <summary>底板 (边长, 边长, 厚)；null 表示无底板。</summary>
        internal double[] Plate;

        /// <summary>管道骑在两翼缘端面上时，管轴 → 翼缘端面的高差。</summary>
        internal double ContactOffsetMm;
        /// <summary>钢板顶面与翼缘端面的间距。</summary>
        internal double PlateGapMm;

        internal string Number,Specification,Material;
        internal string SupportType,SupportCode,CellName;
    }

    // ---------------------------------------------------------------------
    // T4 高温隔热限位管托
    // ---------------------------------------------------------------------

    /// <summary>T4 面板输入。长度单位 mm。</summary>
    internal sealed class T4ShoeParameters
    {
        internal int Dn=T4ShoeCatalog.DefaultDn;
        /// <summary>隔热层厚度 B。</summary>
        internal double InsulationMm=T4ShoeCatalog.DefaultInsulationMm;
        /// <summary>管托沿管轴总长 L。</summary>
        internal double LengthMm=T4ShoeCatalog.DefaultLengthMm;
        /// <summary>编号名称段（默认 T4）。</summary>
        internal string Name="T4";
        internal string TemperatureCode="";
        internal string MaterialCode="";
        /// <summary>编号末段（图注 11）。</summary>
        internal string FCode="";
        internal bool BuildPipe,BuildInsulation;
    }

    /// <summary>T4 由 DN 与用户输入推导出的整套毫米尺寸（对应 Python build_layout）。</summary>
    internal sealed class T4ShoeLayout
    {
        internal int Dn;
        internal string Nps;
        internal double OutsideMm,PipeRadiusMm;
        internal double InsulationMm,InsulationRadiusMm,InsulationOdMm;
        /// <summary>底板厚 T1、腹板 / 上下板厚 T2、承重板厚 T3。</summary>
        internal double T1Mm,T2Mm,T3Mm;
        internal double ClampOuterRadiusMm,ClampWidthMm;
        internal double HeightMm,Height1Mm,ShoeLengthMm,ShoeBottomZMm;
        internal double BaseWidthMm,BaseTopZMm;
        internal int BoltCount;
        internal string Bolt;
        internal double BoltDiameterMm,BoltLengthMm;
        internal double EarWidthMm,EarHeightMm,EarThicknessMm;
        internal double BoltCenterCMm,WeldLegKMm,PlateGapJMm;
        internal double SplitAngleDeg;
        internal bool HasMiddleRib;
        internal double TopPlateTopZMm;
        internal string Number;
    }

    /// <summary>T4 布尔建模所需的全部尺寸（对应 Python build_boolean_layout）。</summary>
    internal sealed class T4ShoeBooleanLayout
    {
        internal double InnerRadiusMm,OuterRadiusMm,ClampLengthMm,CutAngleDeg,GapJMm;
        internal double[] EarCenterXmm;
        internal double[] SupportCenterXmm;
        internal double BaseBottomZMm,BaseTopZMm,SupportHalfSpanMm,SupportTopZMm,TrimRadiusMm;
        /// <summary>四块耳板的 (a0, a1, b0, b1)。</summary>
        internal double[][] EarBounds;
        /// <summary>各耳板的孔心 a 坐标（与 EarBounds 同序）。</summary>
        internal double[] EarHoleA;
        internal double HoleDiameterMm;
        internal double EarWidthMm,EarHeightMm,EarThicknessMm,EarSetbackMm;
    }
}
