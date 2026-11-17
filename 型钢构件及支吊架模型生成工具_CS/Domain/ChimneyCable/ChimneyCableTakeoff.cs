using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 材料统计表的一行：项目、规格、数量、单位与重量。
    /// 属性必须为 public，WPF DataGrid 绑定才可用（类本身仍是 internal）。
    /// 附件只计数量、不计重量，<see cref="Weighed"/> 为 false 时重量列显示短横线。
    /// </summary>
    internal sealed class ChimneyCableMaterialRow
    {
        /// <summary>项目名称。</summary>
        public string Item { get; set; }

        /// <summary>规格描述。</summary>
        public string Specification { get; set; }

        /// <summary>数量数值（导出用）。</summary>
        public double Quantity { get; set; }

        /// <summary>单位。</summary>
        public string Unit { get; set; }

        /// <summary>单重（kg），不计重时为 0。</summary>
        public double UnitMassKg { get; set; }

        /// <summary>总重（kg），不计重时为 0。</summary>
        public double TotalMassKg { get; set; }

        /// <summary>是否计重；false 表示只计数量。</summary>
        public bool Weighed { get; set; }

        /// <summary>备注。</summary>
        public string Note { get; set; }

        /// <summary>
        /// 数量显示文本（表格列）：数量与单位合并成“30 m”，
        /// 页面在 400 宽下才能同时看到“总重”列而不用横向滚动。
        /// </summary>
        public string QuantityText
        {
            get
            {
                return Quantity.ToString("0.###", CultureInfo.CurrentCulture) + " " + Unit;
            }
        }

        /// <summary>单重显示文本（表格列）；不计重显示短横线。</summary>
        public string UnitMassText
        {
            get { return Weighed ? UnitMassKg.ToString("0.###", CultureInfo.CurrentCulture) : "—"; }
        }

        /// <summary>总重显示文本（表格列）；不计重显示短横线。</summary>
        public string TotalMassText
        {
            get { return Weighed ? TotalMassKg.ToString("0.###", CultureInfo.CurrentCulture) : "—"; }
        }
    }

    /// <summary>
    /// 烟囱拉索的材料用量（排气筒钢管、拉索、附件），全部由几何与规格表算出，
    /// 只读、不改计划。拉索长度按**建模出来的实际路径**累加（含两端绳眼），
    /// 不是按挂点直线距离估算。
    /// </summary>
    internal sealed class ChimneyCableMaterials
    {
        /// <summary>排气筒壁厚（mm）。</summary>
        internal double StackThicknessMm;

        /// <summary>排气筒每米钢管重量（kg/m）。</summary>
        internal double StackMassKgPerMeter;

        /// <summary>排气筒钢管总重（kg）。</summary>
        internal double StackMassKg;

        /// <summary>排气筒外表面面积（m²）。</summary>
        internal double StackSurfaceSquareMeters;

        /// <summary>筒身长度（m）：总高减去基础预埋板顶面标高。</summary>
        internal double StackLengthM;

        /// <summary>单根拉索长度（m，含两端绳眼）。</summary>
        internal double StrandLengthM;

        /// <summary>拉索根数。</summary>
        internal int StrandCount;

        /// <summary>拉索总长（m）。</summary>
        internal double RopeTotalLengthM;

        /// <summary>拉索总重（kg）。</summary>
        internal double RopeMassKg;

        /// <summary>混凝土基础体积（m³）。</summary>
        internal double FoundationVolumeM3;

        /// <summary>混凝土基础重量（kg），按 2400 kg/m³。</summary>
        internal double FoundationMassKg;

        /// <summary>环形预埋钢板单件重量（kg）。</summary>
        internal double PlateMassKg;

        /// <summary>环形预埋钢板件数（0 或 1）。</summary>
        internal int PlateCount;

        /// <summary>加劲肋单件重量（kg）。</summary>
        internal double RibMassKg;

        /// <summary>加劲肋块数。</summary>
        internal int RibCount;

        /// <summary>地脚螺栓套数（每套含 1 个螺母 + 1 个垫圈）。</summary>
        internal int AnchorBoltCount;

        /// <summary>弧形检修门套数（0 或 1）。</summary>
        internal int CleanoutCount;

        /// <summary>连接环板件数。</summary>
        internal int CollarCount;

        /// <summary>单件连接环板重量（kg）。</summary>
        internal double CollarMassKg;

        /// <summary>M20 U 形螺栓套数。</summary>
        internal int CollarUboltCount;

        /// <summary>M20 螺母个数。</summary>
        internal int CollarNutCount;

        /// <summary>鸡心环件数。</summary>
        internal int ThimbleCount;

        /// <summary>绳夹套数（每套含 U 形螺栓 1、螺母 2）。</summary>
        internal int ClipCount;

        /// <summary>锚墩个数。</summary>
        internal int AnchorCount;

        /// <summary>单件锚墩重量（kg）。</summary>
        internal double AnchorMassKg;

        /// <summary>地面 φ30 吊环个数。</summary>
        internal int GroundRebarCount;

        /// <summary>单个地面 φ30 吊环展开长度（m）。</summary>
        internal double GroundRebarLengthM;

        /// <summary>单个地面 φ30 吊环重量（kg）。</summary>
        internal double GroundRebarMassKg;

        /// <summary>展示用文本行（中文摘要用）。</summary>
        internal List<string> Lines = new List<string>();

        /// <summary>材料统计表行（页面“材料统计”页签的表格与导出共用）。</summary>
        internal List<ChimneyCableMaterialRow> Rows = new List<ChimneyCableMaterialRow>();

        /// <summary>钢材小计（kg）：排气筒钢管 + 预埋板 + 加劲肋 + 连接环板 + 锚墩 + 地面 φ30 吊环。</summary>
        internal double SteelMassKg;

        /// <summary>材料合计（kg）：钢材小计 + 钢丝绳 + 混凝土基础。</summary>
        internal double TotalMassKg;

        /// <summary>单行摘要（写进 Describe 与日志）。</summary>
        internal string Summary()
        {
            return string.Format(CultureInfo.CurrentCulture,
                "材料：排气筒钢管 {0:0.###} kg（{1:0.#} kg/m）、混凝土 {2:0.##} m³ / {3:0.#} kg、" +
                "预埋板 {4} 件共 {5:0.#} kg、加劲肋 {6} 块共 {7:0.#} kg、地脚螺栓 {8} 套；" +
                "拉索 {9} 根共 {10:0.##} m / {11:0.##} kg、环板 {12} 件、M20 U 形螺栓 {13} 套、" +
                "鸡心环 {14} 件、绳夹 {15} 套、锚墩 {16} 个、φ30 吊环 {17} 个",
                StackMassKg, StackMassKgPerMeter, FoundationVolumeM3, FoundationMassKg,
                PlateCount, PlateMassKg * PlateCount, RibCount, RibMassKg * RibCount, AnchorBoltCount,
                StrandCount, RopeTotalLengthM, RopeMassKg,
                CollarCount, CollarUboltCount, ThimbleCount, ClipCount, AnchorCount, GroundRebarCount);
        }
    }

    /// <summary>
    /// 材料用量计算：钢管按环形截面、拉索按建模路径、附件按规格表计数。
    /// 钢密度 7850 kg/m³；φ16 6×19+FC 钢丝绳名义重量 0.857 kg/m（GB/T 20118 近似值）。
    /// </summary>
    internal static class ChimneyCableTakeoff
    {
        /// <summary>钢密度（kg/m³）。</summary>
        internal const double SteelDensityKgPerCubicMeter = 7850.0;

        /// <summary>φ16 6×19+FC 钢丝绳名义重量（kg/m）。</summary>
        internal const double RopeKilogramPerMeter = 0.857;

        /// <summary>φ30 圆钢理论重量（kg/m）：0.00617×30² ≈ 5.55。</summary>
        internal const double GroundRingKilogramPerMeter = 5.55;

        /// <summary>混凝土密度（kg/m³），用于基础方量与重量换算。</summary>
        internal const double ConcreteDensityKgPerCubicMeter = 2400.0;

        internal static ChimneyCableMaterials Of(ChimneyCableSpec spec, EngineeringPlan plan)
        {
            if (spec == null)
            {
                throw new ArgumentNullException("spec");
            }

            if (plan == null)
            {
                throw new ArgumentNullException("plan");
            }

            var materials = new ChimneyCableMaterials();

            // ---- 排气筒钢管：环形截面（外径 D、壁厚 t）；长度取总高减去基础预埋板顶面
            double thickness = spec.WallThicknessMm;
            double meanDiameter = spec.DiameterMm - thickness;
            double areaSquareMeters = Math.PI * meanDiameter * thickness / 1e6;
            double shellLengthM = (spec.HeightMm - spec.ShellBottomMm) / 1000.0;
            materials.StackThicknessMm = thickness;
            materials.StackMassKgPerMeter = areaSquareMeters * SteelDensityKgPerCubicMeter;
            materials.StackLengthM = shellLengthM;
            materials.StackMassKg = materials.StackMassKgPerMeter * shellLengthM;
            materials.StackSurfaceSquareMeters = Math.PI * spec.DiameterMm / 1000.0 * shellLengthM;

            // ---- 基础：混凝土 + 环形预埋板 + 加劲肋 + 地脚螺栓 + 检修门（只有生成基础时才有）
            if (spec.GenerateBase)
            {
                materials.FoundationVolumeM3 = spec.FoundationSideMm * spec.FoundationSideMm *
                    spec.FoundationThicknessMm / 1e9;
                materials.FoundationMassKg = materials.FoundationVolumeM3 * ConcreteDensityKgPerCubicMeter;

                materials.PlateCount = 1;
                materials.PlateMassKg = AnnulusMassKg(
                    Math.Max(1.0, spec.DiameterMm / 2.0 - ChimneyBaseConstants.PlateInnerInsetRadius),
                    spec.EmbeddedPlateDiameterMm / 2.0,
                    ChimneyBaseConstants.BasePlateThickness);

                materials.RibCount = spec.BoltCount;
                materials.RibMassKg = RibMassKg();
                materials.AnchorBoltCount = spec.BoltCount;
                materials.CleanoutCount = CleanoutCount(spec);
            }

            // ---- 拉索：按建模路径累加，单根 = 两挂点距离 + 两端绳眼（绕鸡心环到绳尾）
            materials.StrandCount = spec.CableCount;
            materials.StrandLengthM = spec.CableCount > 0 ? StrandLengthMm(plan) / 1000.0 : 0.0;
            materials.RopeTotalLengthM = materials.StrandLengthM * materials.StrandCount;
            materials.RopeMassKg = materials.RopeTotalLengthM * RopeKilogramPerMeter;

            // ---- 连接环板：每根拉索一件环形板（内缘 R−3、外缘 R+100、厚 20）
            materials.CollarCount = spec.CableCount;
            materials.CollarMassKg = AnnulusMassKg(
                spec.RadiusMm - ChimneyCableCatalog.CollarEmbedMm,
                spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm,
                ChimneyCableCatalog.CollarThicknessMm);

            // ---- 上端吊筋：每根拉索一套 M20 U 形螺栓 + 2 个 M20 螺母
            materials.CollarUboltCount = spec.CableCount;
            materials.CollarNutCount = spec.CableCount * 2;

            // ---- 绳眼配件：每根拉索 2 个鸡心环、2 套绳夹（每个绳眼 3 只）
            materials.ThimbleCount = spec.CableCount * 2;
            materials.ClipCount = spec.CableCount * 2 * ChimneyCableCatalog.ClipCount;

            // ---- 地面固定：锚墩 + 埋入的 φ30 吊环
            materials.AnchorCount = spec.AnchorCount;
            materials.AnchorMassKg = Math.PI * ChimneyCableCatalog.AnchorRadiusMm *
                ChimneyCableCatalog.AnchorRadiusMm * ChimneyCableCatalog.AnchorHeightMm /
                1e9 * SteelDensityKgPerCubicMeter;
            materials.GroundRebarCount = spec.AnchorCount;
            materials.GroundRebarLengthM = GroundRingLengthMm() / 1000.0;
            materials.GroundRebarMassKg = materials.GroundRebarLengthM * GroundRingKilogramPerMeter;

            materials.Lines = BuildLines(materials, spec);
            materials.Rows = BuildRows(materials, spec);
            materials.SteelMassKg = materials.StackMassKg +
                materials.PlateMassKg * materials.PlateCount +
                materials.RibMassKg * materials.RibCount +
                materials.CollarMassKg * materials.CollarCount +
                materials.AnchorMassKg * materials.AnchorCount +
                materials.GroundRebarMassKg * materials.GroundRebarCount;
            materials.TotalMassKg = materials.SteelMassKg + materials.RopeMassKg +
                materials.FoundationMassKg;
            return materials;
        }

        /// <summary>
        /// 单块加劲肋重量（kg）：把底座模块的梯形轮廓按鞋带公式求面积，再乘板厚与钢密度。
        /// 与 <c>ChimneyBaseCalculator.AddRibs</c> 用同一组常量，改肋板尺寸时两边自动一致。
        /// </summary>
        private static double RibMassKg()
        {
            EngineeringPoint[] profile = ChimneyBaseCatalog.RibProfilePoints(
                ChimneyBaseConstants.RibHeight,
                ChimneyBaseConstants.RibTopWidth,
                ChimneyBaseConstants.RibLength,
                ChimneyBaseConstants.RibOuterHeight);

            double twiceArea = 0.0;
            for (int index = 0; index < profile.Length; index++)
            {
                EngineeringPoint current = profile[index];
                EngineeringPoint next = profile[(index + 1) % profile.Length];
                twiceArea += current.X * next.Y - next.X * current.Y;
            }

            double area = Math.Abs(twiceArea) / 2.0;
            return area * ChimneyBaseConstants.RibThickness / 1e9 * SteelDensityKgPerCubicMeter;
        }

        /// <summary>检修门套数：风管直径不足 450 宽门框时底座模块不生成，这里同步为 0。</summary>
        private static int CleanoutCount(ChimneyCableSpec spec)
        {
            double frameWidth = ChimneyBaseConstants.CleanoutDoorWidth +
                2.0 * ChimneyBaseConstants.CleanoutFrameMargin;
            return spec.DiameterMm > frameWidth + 2.0 ? 1 : 0;
        }

        /// <summary>
        /// 材料统计表行：与 <see cref="BuildLines"/> 同源，只是拆成可绑定/可导出的字段。
        /// 附件（U 形螺栓、螺母、鸡心环、绳夹）只计数量，不计重量。
        /// </summary>
        private static List<ChimneyCableMaterialRow> BuildRows(
            ChimneyCableMaterials materials, ChimneyCableSpec spec)
        {
            var rows = new List<ChimneyCableMaterialRow>();

            rows.Add(new ChimneyCableMaterialRow
            {
                Item = "排气筒钢管",
                Specification = string.Format(CultureInfo.CurrentCulture, "φ{0:0.#}×{1:0.#}，长 {2:0.##} m",
                    spec.DiameterMm, materials.StackThicknessMm, materials.StackLengthM),
                Quantity = materials.StackLengthM,
                Unit = "m",
                UnitMassKg = materials.StackMassKgPerMeter,
                TotalMassKg = materials.StackMassKg,
                Weighed = true,
                Note = string.Format(CultureInfo.CurrentCulture, "外表面积 {0:0.##} m²",
                    materials.StackSurfaceSquareMeters)
            });

            // ---- 基础（生成基础时才出现）
            if (spec.GenerateBase)
            {
                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "混凝土基础",
                    Specification = string.Format(CultureInfo.CurrentCulture, "{0:0}×{0:0}×{1:0}（C30 混凝土）",
                        spec.FoundationSideMm, spec.FoundationThicknessMm),
                    Quantity = materials.FoundationVolumeM3,
                    Unit = "m³",
                    UnitMassKg = ConcreteDensityKgPerCubicMeter,
                    TotalMassKg = materials.FoundationMassKg,
                    Weighed = true,
                    Note = "按 2400 kg/m³ 换算"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "环形预埋钢板",
                    Specification = string.Format(CultureInfo.CurrentCulture, "外径 φ{0:0}、内径 φ{1:0}、厚 {2:0}",
                        spec.EmbeddedPlateDiameterMm,
                        2.0 * Math.Max(1.0, spec.DiameterMm / 2.0 -
                            ChimneyBaseConstants.PlateInnerInsetRadius),
                        ChimneyBaseConstants.BasePlateThickness),
                    Quantity = materials.PlateCount,
                    Unit = "件",
                    UnitMassKg = materials.PlateMassKg,
                    TotalMassKg = materials.PlateMassKg * materials.PlateCount,
                    Weighed = true,
                    Note = "板底与地面齐平"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "加劲肋",
                    Specification = string.Format(CultureInfo.CurrentCulture,
                        "梯形 {0:0}×{1:0}×{2:0}、厚 {3:0}",
                        ChimneyBaseConstants.RibHeight, ChimneyBaseConstants.RibLength,
                        ChimneyBaseConstants.RibTopWidth, ChimneyBaseConstants.RibThickness),
                    Quantity = materials.RibCount,
                    Unit = "块",
                    UnitMassKg = materials.RibMassKg,
                    TotalMassKg = materials.RibMassKg * materials.RibCount,
                    Weighed = true,
                    Note = "按相邻地脚螺栓半齿距均布"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "地脚螺栓",
                    Specification = string.Format(CultureInfo.CurrentCulture,
                        "M{0:0}，分布圆 φ{1:0}，每套含 1 螺母 + 1 垫圈",
                        ChimneyBaseConstants.AnchorRodDiameter, spec.BoltCircleDiameterMm),
                    Quantity = materials.AnchorBoltCount,
                    Unit = "套",
                    Weighed = false,
                    Note = "底部 J 形弯钩埋入基础"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "弧形检修门",
                    Specification = string.Format(CultureInfo.CurrentCulture, "{0:0}×{1:0}（+Y 面）",
                        ChimneyBaseConstants.CleanoutDoorWidth, ChimneyBaseConstants.CleanoutDoorHeight),
                    Quantity = materials.CleanoutCount,
                    Unit = "套",
                    Weighed = false,
                    Note = "门框/密封垫/门板/两组合页/两把压紧锁"
                });
            }

            // ---- 拉索与地面固定（不生成拉索时整组不出现）
            if (spec.GenerateCables)
            {
                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "钢丝绳",
                    Specification = "φ16（6×19+FC）",
                    Quantity = materials.StrandCount,
                    Unit = "根",
                    UnitMassKg = materials.StrandLengthM * RopeKilogramPerMeter,
                    TotalMassKg = materials.RopeMassKg,
                    Weighed = true,
                    Note = string.Format(CultureInfo.CurrentCulture, "单根 {0:0.##} m，总长 {1:0.##} m",
                        materials.StrandLengthM, materials.RopeTotalLengthM)
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "连接环板",
                    Specification = string.Format(CultureInfo.CurrentCulture, "外径 φ{0:0}、宽 {1:0}、厚 {2:0}",
                        2.0 * (spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm),
                        ChimneyCableCatalog.CollarWidthMm, ChimneyCableCatalog.CollarThicknessMm),
                    Quantity = materials.CollarCount,
                    Unit = "件",
                    UnitMassKg = materials.CollarMassKg,
                    TotalMassKg = materials.CollarMassKg * materials.CollarCount,
                    Weighed = true,
                    Note = "每根拉索一件"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "M20 U 形螺栓",
                    Specification = "上端吊筋，穿 φ24 孔",
                    Quantity = materials.CollarUboltCount,
                    Unit = "套",
                    Weighed = false,
                    Note = string.Format(CultureInfo.CurrentCulture, "配 M20 螺母 {0} 个",
                        materials.CollarNutCount)
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "M20 螺母",
                    Specification = "板面压紧",
                    Quantity = materials.CollarNutCount,
                    Unit = "个",
                    Weighed = false,
                    Note = "每套 U 形螺栓 2 个"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "鸡心环",
                    Specification = "φ38 环带",
                    Quantity = materials.ThimbleCount,
                    Unit = "件",
                    Weighed = false,
                    Note = "每根拉索两端各一件"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "绳夹",
                    Specification = "16 规格（M14 U 形螺栓 + 螺母）",
                    Quantity = materials.ClipCount,
                    Unit = "套",
                    Weighed = false,
                    Note = string.Format(CultureInfo.CurrentCulture, "M14 螺栓 {0}、螺母 {1}",
                        materials.ClipCount, materials.ClipCount * 2)
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "地面锚墩",
                    Specification = string.Format(CultureInfo.CurrentCulture, "φ{0:0}×{1:0}",
                        ChimneyCableCatalog.AnchorRadiusMm * 2.0, ChimneyCableCatalog.AnchorHeightMm),
                    Quantity = materials.AnchorCount,
                    Unit = "个",
                    UnitMassKg = materials.AnchorMassKg,
                    TotalMassKg = materials.AnchorMassKg * materials.AnchorCount,
                    Weighed = true,
                    Note = "每个吊点一个"
                });

                rows.Add(new ChimneyCableMaterialRow
                {
                    Item = "地面 φ30 吊环",
                    Specification = string.Format(CultureInfo.CurrentCulture,
                        "φ30（两腿净距 100、外露 100、埋深 900），单个 {0:0.##} m",
                        materials.GroundRebarLengthM),
                    Quantity = materials.GroundRebarCount,
                    Unit = "个",
                    UnitMassKg = materials.GroundRebarMassKg,
                    TotalMassKg = materials.GroundRebarMassKg * materials.GroundRebarCount,
                    Weighed = true,
                    Note = "埋入锚墩，两端 180° 回钩"
                });
            }

            return rows;
        }

        private static List<string> BuildLines(ChimneyCableMaterials materials, ChimneyCableSpec spec)
        {
            var lines = new List<string>();
            lines.Add(string.Format(CultureInfo.CurrentCulture,
                "排气筒钢管  φ{0:0.#}×{1:0.#}，长 {2:0.##} m：{3:0.#} kg/m，共 {4:0} kg；外表面积 {5:0.##} m²",
                spec.DiameterMm, materials.StackThicknessMm, materials.StackLengthM,
                materials.StackMassKgPerMeter, materials.StackMassKg, materials.StackSurfaceSquareMeters));

            if (spec.GenerateBase)
            {
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "混凝土基础  {0:0}×{0:0}×{1:0}，{2:0.##} m³ / {3:0.#} kg；环形预埋板 φ{4:0} 一件 {5:0.#} kg",
                    spec.FoundationSideMm, spec.FoundationThicknessMm,
                    materials.FoundationVolumeM3, materials.FoundationMassKg,
                    spec.EmbeddedPlateDiameterMm, materials.PlateMassKg));
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "底座附件    加劲肋 {0} 块（单块 {1:0.#} kg）；地脚螺栓 {2} 套（每套 1 螺母 + 1 垫圈）；弧形检修门 {3} 套",
                    materials.RibCount, materials.RibMassKg, materials.AnchorBoltCount,
                    materials.CleanoutCount));
            }

            if (spec.GenerateCables)
            {
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "钢丝绳      φ16（6×19+FC），单根 {0:0.##} m × {1} 根 = {2:0.##} m，共 {3:0.##} kg",
                    materials.StrandLengthM, materials.StrandCount, materials.RopeTotalLengthM,
                    materials.RopeMassKg));
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "连接环板    {0} 件（外径 φ{1:0}、宽 {2:0}、厚 {3:0}），单件 {4:0.#} kg，共 {5:0.#} kg",
                    materials.CollarCount, 2.0 * (spec.RadiusMm + ChimneyCableCatalog.CollarWidthMm),
                    ChimneyCableCatalog.CollarWidthMm, ChimneyCableCatalog.CollarThicknessMm,
                    materials.CollarMassKg, materials.CollarMassKg * materials.CollarCount));
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "上端吊筋    M20 U 形螺栓 {0} 套、M20 螺母 {1} 个",
                    materials.CollarUboltCount, materials.CollarNutCount));
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "绳眼配件    鸡心环 φ38 {0} 件；绳夹 {1} 套（每套 M14 U 形螺栓 1 + 螺母 2，共螺栓 {1}、螺母 {2}）",
                    materials.ThimbleCount, materials.ClipCount, materials.ClipCount * 2));
                lines.Add(string.Format(CultureInfo.CurrentCulture,
                    "地面固定    锚墩 {0} 个（φ{1:0}×{2:0}，单件 {3:0.#} kg）；φ30 吊环 {4} 个（单个 {5:0.###} m、{6:0.##} kg，共 {7:0.##} kg）",
                    materials.AnchorCount, ChimneyCableCatalog.AnchorRadiusMm * 2.0,
                    ChimneyCableCatalog.AnchorHeightMm,
                    materials.AnchorMassKg, materials.GroundRebarCount, materials.GroundRebarLengthM,
                    materials.GroundRebarMassKg, materials.GroundRebarMassKg * materials.GroundRebarCount));
            }
            else
            {
                lines.Add("拉索与地面吊环：自立式，不生成。");
            }

            return lines;
        }

        /// <summary>圆环板重量（kg）：内半径、外半径、厚度均为 mm。</summary>
        private static double AnnulusMassKg(double innerRadiusMm, double outerRadiusMm, double thicknessMm)
        {
            double area = Math.PI * (outerRadiusMm * outerRadiusMm - innerRadiusMm * innerRadiusMm);
            return area * thicknessMm / 1e9 * SteelDensityKgPerCubicMeter;
        }

        /// <summary>
        /// φ30 吊环展开长度（mm）：两腿直段 + 环顶半圆 + 两个 180° 回钩 + 两段回钩直肢。
        /// 默认参数下 ≈ 2215.6 mm（2.216 m），与几何路径一致。
        /// </summary>
        private static double GroundRingLengthMm()
        {
            double half = ChimneyCableCatalog.GroundRingHalfMm;
            double shoulder = ChimneyCableCatalog.GroundRingCrownMm - half;
            double legBottom = ChimneyCableCatalog.GroundRingLegBottomMm;
            double hook = ChimneyCableCatalog.GroundRingHookRadiusMm;
            double tip = ChimneyCableCatalog.GroundRingHookTipMm;

            double legs = 2.0 * (shoulder - legBottom);
            double crown = Math.PI * half;
            double hooks = 2.0 * Math.PI * hook;
            double tails = 2.0 * (tip - legBottom);
            return legs + crown + hooks + tails;
        }

        /// <summary>
        /// 单根拉索长度（mm）：两绳眼顶点之间的距离 + 两端“顶点→绳尾”的路径长度。
        /// 直接读建模出来的绳圈路径，绳眼绕鸡心环的那一段不会漏算。
        /// </summary>
        private static double StrandLengthMm(EngineeringPlan plan)
        {
            foreach (EngineeringBody body in plan.Bodies)
            {
                if (body.Name.IndexOf("拉索 ", StringComparison.Ordinal) != 0 ||
                    body.Name.IndexOf("绳眼", StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                EngineeringShape cylinder = null;
                var eyes = new List<EngineeringShape>();
                foreach (EngineeringShape shape in body.Add)
                {
                    if (shape.Kind == EngineeringShapeKind.Cone)
                    {
                        cylinder = shape;
                    }
                    else if (shape.Kind == EngineeringShapeKind.Loft ||
                             shape.Kind == EngineeringShapeKind.Sweep)
                    {
                        eyes.Add(shape);
                    }
                }

                if (cylinder == null)
                {
                    continue;
                }

                if (eyes.Count == 0)
                {
                    // 短索退化成一个圆柱，没有绳眼。
                    return Distance(cylinder.Start, cylinder.End);
                }

                double best = 0.0;
                for (int index = 0; index < eyes.Count; index++)
                {
                    for (int other = index + 1; other < eyes.Count; other++)
                    {
                        double length = EyeLengthMm(eyes[index], eyes[other]);
                        if (length > best)
                        {
                            best = length;
                        }
                    }
                }

                if (best > 0.0)
                {
                    return best;
                }
            }

            return 0.0;
        }

        /// <summary>两只绳眼之间的拉索长度：两顶点距离 + 两个“顶点→绳尾”的路径长度。</summary>
        private static double EyeLengthMm(EngineeringShape first, EngineeringShape second)
        {
            int crownFirst;
            int crownSecond;
            double tailFirst = CrownToTailMm(first, out crownFirst);
            double tailSecond = CrownToTailMm(second, out crownSecond);
            return Distance(first.Points[crownFirst], second.Points[crownSecond]) + tailFirst + tailSecond;
        }

        /// <summary>
        /// 从绳眼顶点到绳尾末端沿路径的长度（mm）：顶点取“离路径末点最远”的路径点，
        /// 因为绳尾末端与顶点正好在绳圈两侧。
        /// </summary>
        private static double CrownToTailMm(EngineeringShape eye, out int crown)
        {
            crown = 0;
            int last = eye.Points.Length - 1;
            double farthest = -1.0;
            for (int index = 0; index < eye.Points.Length; index++)
            {
                double distance = Distance(eye.Points[index], eye.Points[last]);
                if (distance > farthest)
                {
                    farthest = distance;
                    crown = index;
                }
            }

            double length = 0.0;
            for (int index = crown; index < last; index++)
            {
                length += SegmentLengthMm(eye, index);
            }

            return length;
        }

        private static double SegmentLengthMm(EngineeringShape shape, int index)
        {
            EngineeringPoint start = shape.Points[index];
            EngineeringPoint end = shape.Points[index + 1];
            EngineeringPoint? middle = shape.ArcMiddles == null || index >= shape.ArcMiddles.Length
                ? null
                : shape.ArcMiddles[index];
            if (!middle.HasValue)
            {
                return Distance(start, end);
            }

            // 三点定圆：用外接圆半径与弦长求真圆弧长度。
            double chord = Distance(start, end);
            double sideA = Distance(start, middle.Value);
            double sideB = Distance(middle.Value, end);
            double area2 = CrossMagnitude(Subtract(start, middle.Value), Subtract(end, middle.Value));
            if (chord < 1e-9 || sideA < 1e-9 || sideB < 1e-9 || area2 < 1e-9)
            {
                return chord;
            }

            double radius = sideA * sideB * chord / (2.0 * area2);
            double ratio = chord / (2.0 * radius);
            if (ratio >= 1.0)
            {
                return chord;
            }

            return radius * 2.0 * Math.Asin(ratio);
        }

        private static double CrossMagnitude(EngineeringPoint first, EngineeringPoint second)
        {
            double x = first.Y * second.Z - first.Z * second.Y;
            double y = first.Z * second.X - first.X * second.Z;
            double z = first.X * second.Y - first.Y * second.X;
            return Math.Sqrt(x * x + y * y + z * z);
        }

        private static EngineeringPoint Subtract(EngineeringPoint first, EngineeringPoint second)
        {
            return new EngineeringPoint(
                first.X - second.X, first.Y - second.Y, first.Z - second.Z);
        }

        private static double Distance(EngineeringPoint first, EngineeringPoint second)
        {
            double x = first.X - second.X;
            double y = first.Y - second.Y;
            double z = first.Z - second.Z;
            return Math.Sqrt(x * x + y * y + z * z);
        }
    }
}
