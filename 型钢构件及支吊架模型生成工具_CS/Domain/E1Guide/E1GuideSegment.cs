namespace SteelSectionProbe
{
    internal sealed class E1GuideSegment
    {
        internal double StartX,StartY,StartZ,EndX,EndY,EndZ;
        internal E1GuideSegment(double sx,double sy,double sz,double ex,double ey,double ez)
        {
            StartX=sx;StartY=sy;StartZ=sz;EndX=ex;EndY=ey;EndZ=ez;
        }
    }
}
