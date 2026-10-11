namespace SteelSectionProbe
{
    /// <summary>G11 表 2 的截面及锚固尺寸，长度单位为毫米。</summary>
    internal sealed class G11CantileverVariant
    {
        internal D2CantileverVariant Section { get; set; }
        internal double BoltSpacingMm { get; set; }
        internal double ConcreteEdgeDistanceMm { get; set; }
    }

    /// <summary>锚栓与混凝土接触面的局部坐标，X 沿悬臂，Y 横向，Z 向上。</summary>
    internal sealed class G11AnchorLocation
    {
        internal double XMm { get; set; }
        internal double YMm { get; set; }
        internal double ZMm { get; set; }
    }

    /// <summary>G11 锚固及连接段计算结果，不持有宿主模型对象。</summary>
    internal sealed class G11CantileverPlan
    {
        internal G11CantileverVariant Variant { get; set; }
        internal G2AnchorPlan Bolt { get; set; }
        internal G11AnchorLocation[] Anchors { get; set; }
        internal double ConnectionLengthMm { get; set; }
        internal double ConnectionStartXMm { get; set; }
        internal double ConnectionStartZMm { get; set; }
        internal double ConnectionStartYMm { get; set; }
        /// <summary>槽钢连接段截面宽度沿横向，高度沿悬臂反向，开口与横担一致。</summary>
        internal bool ConnectionWidthAlongSide { get; set; }
        /// <summary>混凝土外法向在悬臂局部坐标中的单位分量。</summary>
        internal int BoltNormalX { get; set; }
        internal int BoltNormalY { get; set; }
        internal int BoltNormalZ { get; set; }
        internal int BeamVerticalSign { get; set; }
    }
}
