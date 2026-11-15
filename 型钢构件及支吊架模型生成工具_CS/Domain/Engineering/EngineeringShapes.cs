using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>毫米坐标点；三维建模统一使用 mm，构建时再换算为模型 UOR。</summary>
    internal struct EngineeringPoint
    {
        internal readonly double X;
        internal readonly double Y;
        internal readonly double Z;

        internal EngineeringPoint(double x, double y, double z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        internal static EngineeringPoint Origin
        {
            get { return new EngineeringPoint(0, 0, 0); }
        }

        internal EngineeringPoint Offset(double dx, double dy, double dz)
        {
            return new EngineeringPoint(X + dx, Y + dy, Z + dz);
        }

        internal EngineeringPoint RotateZ(double degrees)
        {
            double radians = degrees * Math.PI / 180.0;
            double cosine = Math.Cos(radians);
            double sine = Math.Sin(radians);
            return new EngineeringPoint(X * cosine - Y * sine, X * sine + Y * cosine, Z);
        }
    }

    /// <summary>实体构造方式。全部参数均为毫米，最终由 <see cref="EngineeringSolidFactory"/> 转成 Bentley 实体。</summary>
    internal enum EngineeringShapeKind
    {
        /// <summary>两端半径可不同的圆台（圆柱取相同半径）。</summary>
        Cone,

        /// <summary>径向闭合轮廓（X=半径、Z=高度）绕 Z 轴回转 360°。</summary>
        Revolve,

        /// <summary>闭合轮廓沿矢量拉伸。</summary>
        Extrude,

        /// <summary>正六棱柱。</summary>
        HexPrism,

        /// <summary>圆环（真圆环管）。</summary>
        Torus,

        /// <summary>圆环的一段（真圆环管，按扫掠角截取），用于弯头、弯钩等。</summary>
        TorusArc,

        /// <summary>圆截面沿折线路径扫掠。</summary>
        Sweep,

        /// <summary>
        /// 圆截面沿路径逐段放样成**单一**光滑管面（不产生逐段横向棱线）；
        /// 内核拒绝放样时自动退回 <see cref="Sweep"/>。
        /// </summary>
        Loft,

        /// <summary>圆截面沿光滑插值样条（B 样条）路径扫掠。</summary>
        SplineSweep,

        /// <summary>矩形截面（带）沿光滑插值样条路径扫掠，用于鸡心环一类的扁带环。</summary>
        SplineBand
    }

    /// <summary>一个构造形状。不同 <see cref="Kind"/> 只使用其中一部分字段。</summary>
    internal sealed class EngineeringShape
    {
        internal EngineeringShapeKind Kind;

        /// <summary>圆台/扫掠的起点。</summary>
        internal EngineeringPoint Start;

        /// <summary>圆台/六棱柱的终点。</summary>
        internal EngineeringPoint End;

        /// <summary>拉伸方向（长度 = 拉伸高度）。</summary>
        internal EngineeringPoint Direction;

        /// <summary>起点半径。</summary>
        internal double RadiusStart;

        /// <summary>终点半径。</summary>
        internal double RadiusEnd;

        /// <summary>圆环主半径（中心到管中心）。</summary>
        internal double MajorRadius;

        /// <summary>圆环管半径。</summary>
        internal double MinorRadius;

        /// <summary>圆环平面基向量（TorusArc 使用；起点 = Start + AxisX×MajorRadius）。</summary>
        internal EngineeringPoint AxisX;

        /// <summary>圆环平面基向量（TorusArc 使用；扫掠朝 AxisY 方向）。</summary>
        internal EngineeringPoint AxisY;

        /// <summary>回转/拉伸/扫掠轮廓，或扫掠路径点。</summary>
        internal EngineeringPoint[] Points = new EngineeringPoint[0];

        /// <summary>
        /// 与 <see cref="Points"/> 等长的圆弧中间点：元素 i 非空表示 Points[i]→Points[i+1]
        /// 是一段真圆弧（三点定圆），为空表示直线。null 表示整个轮廓/路径全是直线。
        /// </summary>
        internal EngineeringPoint?[] ArcMiddles;

        internal static EngineeringShape Cone(EngineeringPoint start, EngineeringPoint end, double radiusStart, double radiusEnd)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Cone,
                Start = start,
                End = end,
                RadiusStart = radiusStart,
                RadiusEnd = radiusEnd
            };
        }

        internal static EngineeringShape Cylinder(EngineeringPoint start, EngineeringPoint end, double radius)
        {
            return Cone(start, end, radius, radius);
        }

        internal static EngineeringShape Revolve(EngineeringPoint[] radialProfile)
        {
            return new EngineeringShape { Kind = EngineeringShapeKind.Revolve, Points = radialProfile };
        }

        internal static EngineeringShape Extrude(EngineeringPoint[] outline, EngineeringPoint direction)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Extrude,
                Points = outline,
                Direction = direction
            };
        }

        /// <summary>闭合轮廓沿矢量拉伸；<paramref name="arcMiddles"/> 与轮廓点等长，用真圆弧代替折线。</summary>
        internal static EngineeringShape Extrude(
            EngineeringPoint[] outline, EngineeringPoint direction, EngineeringPoint?[] arcMiddles)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Extrude,
                Points = outline,
                Direction = direction,
                ArcMiddles = arcMiddles
            };
        }

        internal static EngineeringShape HexPrism(EngineeringPoint start, EngineeringPoint end, double acrossFlats)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.HexPrism,
                Start = start,
                End = end,
                RadiusStart = acrossFlats / Math.Sqrt(3.0)
            };
        }

        internal static EngineeringShape Torus(EngineeringPoint center, double majorRadius, double minorRadius)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Torus,
                Start = center,
                MajorRadius = majorRadius,
                MinorRadius = minorRadius
            };
        }

        /// <summary>真圆环的一段：从 center+axisX·major 起，朝 axisY 方向扫过 sweepRadians。</summary>
        internal static EngineeringShape TorusArc(
            EngineeringPoint center, EngineeringPoint axisX, EngineeringPoint axisY,
            double majorRadius, double minorRadius, double sweepRadians)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.TorusArc,
                Start = center,
                AxisX = axisX,
                AxisY = axisY,
                MajorRadius = majorRadius,
                MinorRadius = minorRadius,
                RadiusStart = sweepRadians
            };
        }

        internal static EngineeringShape Sweep(EngineeringPoint[] path, double radius)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Sweep,
                Points = path,
                RadiusStart = radius
            };
        }

        /// <summary>圆截面沿路径扫掠；<paramref name="arcMiddles"/> 与路径点等长，用真圆弧代替折线。</summary>
        internal static EngineeringShape Sweep(
            EngineeringPoint[] path, double radius, EngineeringPoint?[] arcMiddles)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Sweep,
                Points = path,
                RadiusStart = radius,
                ArcMiddles = arcMiddles
            };
        }

        /// <summary>
        /// 圆截面沿路径放样成单一光滑管面：<paramref name="arcMiddles"/> 与路径点等长，
        /// 用真圆弧描述路径；<paramref name="outOfPlane"/> 为路径平面法向，
        /// 用于固定每个截面圆的 0° 方向，保证放样不扭转。放样失败时内核层退回扫掠。
        /// </summary>
        internal static EngineeringShape Loft(
            EngineeringPoint[] path, double radius, EngineeringPoint?[] arcMiddles,
            EngineeringPoint outOfPlane)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Loft,
                Points = path,
                RadiusStart = radius,
                ArcMiddles = arcMiddles,
                AxisX = outOfPlane
            };
        }

        /// <summary>圆截面沿光滑插值样条路径扫掠（路径点作为拟合点，曲线真正光滑）。</summary>
        internal static EngineeringShape SplineSweep(EngineeringPoint[] fitPoints, double radius)        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.SplineSweep,
                Points = fitPoints,
                RadiusStart = radius
            };
        }

        /// <summary>
        /// 矩形截面沿光滑插值样条路径扫掠：带宽沿 <paramref name="outOfPlane"/>，
        /// 带厚沿路径平面内法向（用于鸡心环环带）。
        /// </summary>
        internal static EngineeringShape SplineBand(
            EngineeringPoint[] fitPoints, double width, double thickness, EngineeringPoint outOfPlane)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.SplineBand,
                Points = fitPoints,
                RadiusStart = width,
                RadiusEnd = thickness,
                AxisX = outOfPlane
            };
        }
    }

    /// <summary>
    /// 一个可独立成型的实体：先合并 Add 中的形状，再依次减去 Cut 中的形状。
    /// 每个实体最终转成一个 DGN 元素并单独着色。
    /// </summary>
    internal sealed class EngineeringBody
    {
        internal string Name = "";

        internal readonly List<EngineeringShape> Add = new List<EngineeringShape>();

        internal readonly List<EngineeringShape> Cut = new List<EngineeringShape>();

        /// <summary>实体颜色（RGB 0～255）。</summary>
        internal int Red = 174;

        internal int Green = 185;

        internal int Blue = 194;

        /// <summary>为 false 时只把第一个 Add 形状作为基体（其余仍相并，仅为兼容保留）。</summary>
        internal bool UnionAdd = true;

        /// <summary>
        /// 为 true 时，某个 Cut 刀体与基体不相交或内核拒绝该次布尔时跳过该刀体，
        /// 不让整个构件失败；用于“让位槽”一类只影响局部的装饰性差集。
        /// </summary>
        internal bool BestEffortCut;

        internal EngineeringBody(string name)
        {
            Name = name;
        }

        internal EngineeringBody Color(int red, int green, int blue)
        {
            Red = red;
            Green = green;
            Blue = blue;
            return this;
        }
    }

    /// <summary>
    /// 一次放置的完整实体计划。坐标为毫米局部坐标，Z 向上；原点即用户点取的基点。
    /// </summary>
    internal sealed class EngineeringPlan
    {
        internal readonly List<EngineeringBody> Bodies = new List<EngineeringBody>();

        /// <summary>生成的普通单元（Cell）名称。</summary>
        internal string CellName = "ENGINEERING_PART";

        /// <summary>放置后绕竖轴的旋转角（°）。</summary>
        internal double HeadingDegrees;

        /// <summary>放置后绕 X 轴的旋转角（°）；用于把局部 Y 定义为竖直轴向的构件。</summary>
        internal double RotateXDegrees;

        internal EngineeringBody Add(string name)
        {
            var body = new EngineeringBody(name);
            Bodies.Add(body);
            return body;
        }

        internal int PartCount
        {
            get { return Bodies.Count; }
        }
    }
}
