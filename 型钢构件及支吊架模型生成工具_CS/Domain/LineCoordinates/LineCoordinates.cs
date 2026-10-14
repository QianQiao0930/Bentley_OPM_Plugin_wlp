namespace SteelSectionProbe
{
    internal struct LineCoordinatePoint
    {
        internal readonly double X, Y, Z;
        internal LineCoordinatePoint(double x, double y, double z) { X = x; Y = y; Z = z; }
    }

    /// <summary>活动模型笛卡尔坐标，单位毫米；与视图、ACS 和注释比例无关。</summary>
    internal sealed class LineCoordinates
    {
        internal readonly LineCoordinatePoint Start, End;
        internal LineCoordinates(LineCoordinatePoint start, LineCoordinatePoint end) { Start = start; End = end; }
    }
}
