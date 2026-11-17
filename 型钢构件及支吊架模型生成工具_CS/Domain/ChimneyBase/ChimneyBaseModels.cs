using System;

namespace SteelSectionProbe
{
    /// <summary>
    /// 烟囱（排气筒）底座三维参数：迁移自 AutoCAD 版 <c>ChimneyBaseOptions</c> 的建模部分。
    /// 全部尺寸单位为 mm；局部原点取预埋板底面中心，Z 向上。
    /// D2、D3 填 0 表示按 D1 自动取值（D1+350 / D1+700）。
    /// </summary>
    internal sealed class ChimneyBaseParameters
    {
        /// <summary>排气筒（风管）外径 D1（mm），必填。</summary>
        internal double ExhaustDiameterMm = 1000.0;

        /// <summary>地脚螺栓路径直径 D2（mm）；0 表示自动取 D1 + 350。</summary>
        internal double BoltCircleDiameterMm;

        /// <summary>环形预埋钢板外径 D3（mm）；0 表示自动取 D1 + 700。</summary>
        internal double EmbeddedPlateDiameterMm;

        /// <summary>地脚螺栓个数（沿圆周均布）。</summary>
        internal int BoltCount = ChimneyBaseConstants.DefaultBoltCount;

        /// <summary>地脚螺栓露出预埋板顶面的长度（mm），含螺母与丝扣。</summary>
        internal double AbovePlateMm = ChimneyBaseConstants.DefaultAbovePlateMm;

        /// <summary>混凝土基础厚度（mm），自预埋板底面向下。</summary>
        internal double FoundationThicknessMm = ChimneyBaseConstants.DefaultFoundationThicknessMm;

        /// <summary>混凝土基础边长（mm）；0 表示自动取 D3 + 200。</summary>
        internal double FoundationWidthMm;

        /// <summary>放置后绕竖轴（Z）的旋转角（°）。</summary>
        internal double HeadingDegrees;
    }

    /// <summary>
    /// 烟囱底座的三维固定尺寸与输入范围，逐项对齐 AutoCAD 版
    /// <c>ChimneyBaseSolidService</c> / <c>ChimneyBaseGeometry</c> / <c>ChimneyBaseOptions</c>。
    /// 纯常量，不依赖 Bentley。
    /// </summary>
    internal static class ChimneyBaseConstants
    {
        /// <summary>风管壁厚（mm）。</summary>
        internal const double DuctWallThickness = 10.0;

        /// <summary>风管高度（mm，自预埋板顶面起算）。</summary>
        internal const double DuctHeight = 1500.0;

        /// <summary>环形预埋钢板厚度（mm）。</summary>
        internal const double BasePlateThickness = 10.0;

        /// <summary>环形预埋钢板内径相对风管外径的半径内缩量（mm）。</summary>
        internal const double PlateInnerInsetRadius = 50.0;

        /// <summary>加劲肋厚度（mm，沿切向）。</summary>
        internal const double RibThickness = 10.0;

        /// <summary>加劲肋在筒壁处的高度（mm）。三维取值 300，二维剖面为 280。</summary>
        internal const double RibHeight = 300.0;

        /// <summary>加劲肋顶部平台宽度（mm）。</summary>
        internal const double RibTopWidth = 100.0;

        /// <summary>加劲肋径向总长度（mm）。</summary>
        internal const double RibLength = 280.0;

        /// <summary>加劲肋外端高度（mm）。</summary>
        internal const double RibOuterHeight = 100.0;

        /// <summary>风管顶部断管台阶高低差（mm）。</summary>
        internal const double TopStepHeight = 175.0;

        /// <summary>风管顶部断管台阶水平过渡宽度（mm）。</summary>
        internal const double TopStepWidth = 100.0;

        /// <summary>顶部断管切割体的最小半跨长度（mm），即沿世界 X 自 −半跨 拉到 +半跨。</summary>
        internal const double TopCutReach = 2000.0;

        /// <summary>地脚螺栓杆直径（mm）。</summary>
        internal const double AnchorRodDiameter = 24.0;

        /// <summary>地脚螺栓 J 形弯钩的竖直直段长度（mm）。</summary>
        internal const double AnchorHookLength = 40.0;

        /// <summary>J 形弯钩顶端距预埋板底面的距离（mm）。</summary>
        internal const double HookTopClearance = 50.0;

        /// <summary>J 形弯钩半圆弯曲半径（mm）。</summary>
        internal const double HookBendRadius = 40.0;

        /// <summary>J 形弯钩半圆的采样点数（不含向上直段端点）。</summary>
        internal const int HookSampleCount = 32;

        /// <summary>六角螺母对边尺寸（mm）。</summary>
        internal const double NutAcrossFlats = 36.0;

        /// <summary>六角螺母厚度（mm）。</summary>
        internal const double NutHeight = 12.0;

        /// <summary>垫圈外径（mm）。</summary>
        internal const double WasherDiameter = 48.0;

        /// <summary>垫圈厚度（mm）。</summary>
        internal const double WasherThickness = 4.0;

        /// <summary>D2 自动取值时相对 D1 的增量（mm）。</summary>
        internal const double AutoBoltCircleMargin = 350.0;

        /// <summary>D3 自动取值时相对 D1 的增量（mm）。</summary>
        internal const double AutoPlateDiameterMargin = 700.0;

        /// <summary>混凝土基础自动边长时相对 D3 的外扩余量（mm）。</summary>
        internal const double FoundationMargin = 200.0;

        /// <summary>清扫口门底距风管底部的距离（mm）。</summary>
        internal const double CleanoutDoorBottomOffset = 400.0;

        /// <summary>清扫口门板宽（mm）。</summary>
        internal const double CleanoutDoorWidth = 400.0;

        /// <summary>清扫口门板高（mm）。</summary>
        internal const double CleanoutDoorHeight = 600.0;

        /// <summary>门框相对门板四周的外扩量（mm）。</summary>
        internal const double CleanoutFrameMargin = 25.0;

        /// <summary>门板相对门洞的重叠量（mm）。</summary>
        internal const double CleanoutOverlap = 10.0;

        /// <summary>弧形门框板厚（mm）。</summary>
        internal const double CleanoutFrameThickness = 3.0;

        /// <summary>密封垫厚度（mm）。</summary>
        internal const double CleanoutGasketThickness = 1.0;

        /// <summary>门板厚度（mm）。</summary>
        internal const double CleanoutDoorThickness = 3.0;

        /// <summary>合页总长（mm）。</summary>
        internal const double CleanoutHingeLength = 60.0;

        /// <summary>两组合页距门中心的上下距离（mm）。</summary>
        internal const double CleanoutHingeOffset = 150.0;

        /// <summary>合页轴节半径（mm）。</summary>
        internal const double CleanoutKnuckleRadius = 3.5;

        /// <summary>合页销轴半径（mm）。</summary>
        internal const double CleanoutPinRadius = 1.5;

        /// <summary>压紧锁距门边的距离（mm）。</summary>
        internal const double CleanoutLockEdgeOffset = 35.0;

        /// <summary>两把压紧锁距门中心的上下距离（mm）。</summary>
        internal const double CleanoutLockVerticalOffset = 150.0;

        /// <summary>合页五段轴节中固定叶占用的段号。</summary>
        internal static readonly int[] CleanoutFixedSegments = { 0, 2, 4 };

        /// <summary>合页五段轴节中活动叶占用的段号。</summary>
        internal static readonly int[] CleanoutMovingSegments = { 1, 3 };

        /// <summary>D1 允许范围下限（mm）。</summary>
        internal const double MinDiameterMm = 100.0;

        /// <summary>D1/D2/D3 允许范围上限（mm）。</summary>
        internal const double MaxDiameterMm = 20000.0;

        /// <summary>螺栓个数下限。</summary>
        internal const int MinBoltCount = 2;

        /// <summary>螺栓个数上限。</summary>
        internal const int MaxBoltCount = 200;

        /// <summary>螺栓露出长度下限（mm）。</summary>
        internal const double MinAbovePlateMm = 20.0;

        /// <summary>螺栓露出长度上限（mm）。</summary>
        internal const double MaxAbovePlateMm = 500.0;

        /// <summary>混凝土基础厚度默认值（mm）。</summary>
        internal const double DefaultFoundationThicknessMm = 200.0;

        /// <summary>地脚螺栓个数默认值（烟囱拉索模块并入底座时共用）。</summary>
        internal const int DefaultBoltCount = 12;

        /// <summary>地脚螺栓露出预埋板顶面的默认长度（mm）。</summary>
        internal const double DefaultAbovePlateMm = 30.0;

        /// <summary>混凝土基础厚度下限（mm）。</summary>
        internal const double MinFoundationThicknessMm = 160.0;

        /// <summary>混凝土基础厚度上限（mm）。</summary>
        internal const double MaxFoundationThicknessMm = 5000.0;

        /// <summary>混凝土基础手动宽度下限（mm）。</summary>
        internal const double MinFoundationWidthMm = 300.0;

        /// <summary>混凝土基础宽度上限（mm）。</summary>
        internal const double MaxFoundationWidthMm = 100000.0;
    }
}
