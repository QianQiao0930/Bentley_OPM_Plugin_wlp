using System;
namespace SteelSectionProbe
{
    internal sealed class WallLadderParameters
    {
        internal double WidthMm = 400, StandoffMm = 220, FirstRungMm = 400, BracketSpacingMm = 1500, HeadingDegrees;
        internal bool CageEnabled = true;
    }
    /// <summary>局部毫米坐标：X出梯，Y梯宽，Z向上。</summary>
    internal struct WallLadderPoint
    {
        internal readonly double X, Y, Z;
        internal WallLadderPoint(double x, double y, double z) { X=x; Y=y; Z=z; }
        internal double Length { get { return Math.Sqrt(X*X+Y*Y+Z*Z); } }
        public static WallLadderPoint operator +(WallLadderPoint a, WallLadderPoint b) { return new WallLadderPoint(a.X+b.X,a.Y+b.Y,a.Z+b.Z); }
        public static WallLadderPoint operator -(WallLadderPoint a, WallLadderPoint b) { return new WallLadderPoint(a.X-b.X,a.Y-b.Y,a.Z-b.Z); }
        public static WallLadderPoint operator *(WallLadderPoint a,double s) { return new WallLadderPoint(a.X*s,a.Y*s,a.Z*s); }
        internal static WallLadderPoint Cross(WallLadderPoint a,WallLadderPoint b) { return new WallLadderPoint(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X); }
        internal WallLadderPoint Unit() { double l=Length; if(l<1e-12)throw new InvalidOperationException("路径方向退化。"); return this*(1/l); }
    }
    internal sealed class WallLadderSegment
    {
        internal WallLadderPoint Start, Middle, End;
        internal bool IsArc;
        internal double RadiusMm;
        internal static WallLadderSegment Line(WallLadderPoint a,WallLadderPoint b) { return new WallLadderSegment { Start=a,End=b }; }
        internal static WallLadderSegment Arc(double n,double z,double a,double b)
        {
            double r=WallLadderCatalog.CageRadiusMm;
            Func<double,WallLadderPoint> p=deg=>new WallLadderPoint(n+r*Math.Cos(deg*Math.PI/180),r*Math.Sin(deg*Math.PI/180),z);
            return new WallLadderSegment { Start=p(a),Middle=p((a+b)/2),End=p(b),IsArc=true,RadiusMm=r };
        }
        internal WallLadderSegment Reversed() { return new WallLadderSegment { Start=End,Middle=Middle,End=Start,IsArc=IsArc,RadiusMm=RadiusMm }; }
    }
    internal enum WallLadderPartKind { Box, Cylinder, Angle, Sweep }
    internal sealed class WallLadderPart
    {
        internal WallLadderPartKind Kind;
        internal WallLadderPoint Center, U, V, W, Size;
        internal WallLadderSegment[] Path;
        internal bool Spatial;
    }
    internal sealed class WallLadderPlan
    {
        internal WallLadderParameters Parameters;
        internal double HeightMm, StileWidthMm, StileThicknessMm, RungLengthMm;
        internal double[] RungLevels, BracketLevels, HoopRungs, HoopLevels;
        internal WallLadderPart[] LadderParts, CageParts;
        internal WallLadderPoint[] CageStations, CageTangents;
    }
}
