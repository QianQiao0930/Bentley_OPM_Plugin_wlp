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

    /// <summary>点选管道的只读考察数据，单位毫米；来自 Data 层读回的轴线、外径与点取位置。</summary>
    internal sealed class LinePipeSurvey
    {
        internal double AxisStartX, AxisStartY, AxisStartZ;
        internal double AxisEndX, AxisEndY, AxisEndZ;
        /// <summary>管道外表面外径，不含保温；读取不到时保持 0，由服务层拒绝。</summary>
        internal double OutsideDiameterMm;
        /// <summary>用户点取管道时的落点（活动模型坐标，毫米）。</summary>
        internal double PickX, PickY, PickZ;
        /// <summary>OpenPlant 管号，可空，仅用于状态栏提示。</summary>
        internal string PipeNumber;
    }
}
