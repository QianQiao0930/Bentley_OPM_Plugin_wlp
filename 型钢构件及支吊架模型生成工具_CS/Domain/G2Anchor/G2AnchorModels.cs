using System;

namespace SteelSectionProbe
{
    /// <summary>安装面：决定锚栓轴线（局部 +X，混凝土外法向）的世界方向。</summary>
    internal enum G2MountFace
    {
        /// <summary>竖直墙面：局部 +X 在水平面内，绕 Z 旋转（原有行为）。</summary>
        Wall=0,
        /// <summary>水平楼板顶面：局部 +X = 世界 +Z，锚板水平、螺栓向下插入楼板。</summary>
        FloorTop=1,
        /// <summary>水平楼板底面：局部 +X = 世界 -Z，锚板水平、螺栓向上。</summary>
        CeilingBottom=2
    }

    /// <summary>G2 面板输入。长度单位为毫米，朝向为度。</summary>
    internal sealed class G2AnchorParameters
    {
        /// <summary>子项 A / B / C / D。</summary>
        internal string SubtypeKey=G2AnchorCatalog.DefaultSubtypeKey;
        /// <summary>螺栓间距 S（mm）；null 表示取该子项的 MIN.S。</summary>
        internal double? SpacingMm;
        /// <summary>朝向：墙面为绕 Z 的方位角，楼板为绕竖轴的转角。</summary>
        internal double HeadingDegrees=G2AnchorCatalog.DefaultHeadingDegrees;
        internal G2MountFace MountFace=G2MountFace.Wall;
    }

    /// <summary>
    /// G2 解析后的全部毫米尺寸、荷载读数与清单编号。
    /// 纯数据，不引用 Bentley API，可在纯计算检查工程中断言。
    /// </summary>
    internal sealed class G2AnchorPlan
    {
        internal G2AnchorParameters Parameters;
        internal G2AnchorItem Item;

        /// <summary>实际采用的螺栓孔中心距 S。</summary>
        internal double SpacingMm;
        /// <summary>锚板边长 S + 2×50。</summary>
        internal double PlateSideMm;
        internal double PlateThicknessMm;
        internal double HoleDiameterMm;

        internal double BoltDiameterMm;
        /// <summary>锚栓总长 L（不变）。</summary>
        internal double BoltLengthMm;
        /// <summary>螺杆外端相对板背面的距离 = 板厚 + 垫圈厚 + 螺母高 + 露头。</summary>
        internal double BoltOutLengthMm;
        internal double RequiredEmbedmentMm;
        /// <summary>有效埋深 = L − BoltOutLengthMm，必须不小于 RequiredEmbedmentMm。</summary>
        internal double ActualEmbedmentMm;

        internal double SleeveDiameterMm;
        internal double SleeveLengthMm;

        internal double NutAcrossFlatsMm;
        internal double NutHeightMm;
        internal double WasherOutsideMm;
        internal double WasherThicknessMm;

        internal double MinEdgeDistanceMm;
        internal double MinThicknessMm;
        internal double TensionKn;
        internal double ShearKn;

        internal int BoltCount;
        internal string CellName;

        /// <summary>编号，如 G2-A。</summary>
        internal string AssemblyTag;
        /// <summary>锚板规格，如 175×175×10（S=75，4-φ10）。</summary>
        internal string PlateSpecification;
        /// <summary>膨胀锚栓规格，如 M8×80。</summary>
        internal string BoltSpecification;
        /// <summary>整组规格说明，写入 ItemType 的 Specification。</summary>
        internal string AssemblySpecification;

        internal double HeadingRadians
        {
            get { return Parameters.HeadingDegrees*Math.PI/180.0; }
        }
        internal G2MountFace MountFace
        {
            get { return Parameters.MountFace; }
        }
    }
}
