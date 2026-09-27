using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    internal static class E1GuideSegmentSelector
    {
        internal static E1GuideSegment Nearest(IEnumerable<E1GuideSegment> segments,
            double clickX,double clickY,double clickZ)
        {
            if(segments==null)throw new ArgumentNullException("segments");
            E1GuideSegment nearest=null;
            double best=double.MaxValue;
            foreach(var segment in segments)
            {
                if(segment==null)continue;
                double dx=segment.EndX-segment.StartX;
                double dy=segment.EndY-segment.StartY;
                double dz=segment.EndZ-segment.StartZ;
                double lengthSquared=dx*dx+dy*dy+dz*dz;
                if(lengthSquared<1e-12)continue;
                double t=((clickX-segment.StartX)*dx+
                    (clickY-segment.StartY)*dy+(clickZ-segment.StartZ)*dz)/lengthSquared;
                t=Math.Max(0,Math.Min(1,t));
                double rx=clickX-(segment.StartX+t*dx);
                double ry=clickY-(segment.StartY+t*dy);
                double rz=clickZ-(segment.StartZ+t*dz);
                double distanceSquared=rx*rx+ry*ry+rz*rz;
                if(distanceSquared>=best)continue;
                best=distanceSquared;nearest=segment;
            }
            if(nearest==null)throw new InvalidOperationException("所选多段线没有有效直线段。");
            return nearest;
        }
    }
}
