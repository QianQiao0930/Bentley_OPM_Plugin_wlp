using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>真实直线段优先；快照没有轴线时必须尝试显示几何，不能用包围盒跳过该通道。</summary>
    internal static class E1GuideAxisResolver
    {
        internal static E1GuideSegment Resolve(IList<E1GuideSegment> segments,
            E1GuideSegment snapshotAxis, Func<E1GuideSegment> readNativeAxis,
            double clickX, double clickY, double clickZ)
        {
            if (segments != null && segments.Count > 0)
                return E1GuideSegmentSelector.Nearest(segments, clickX, clickY, clickZ);
            if (snapshotAxis != null) return snapshotAxis;
            return readNativeAxis();
        }
    }
}
