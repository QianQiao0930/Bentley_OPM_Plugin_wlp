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

        /// <summary>圆截面沿折线路径扫掠。</summary>
        Sweep
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

        /// <summary>回转/拉伸/扫掠轮廓，或扫掠路径点。</summary>
        internal EngineeringPoint[] Points = new EngineeringPoint[0];

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

        internal static EngineeringShape Sweep(EngineeringPoint[] path, double radius)
        {
            return new EngineeringShape
            {
                Kind = EngineeringShapeKind.Sweep,
                Points = path,
                RadiusStart = radius
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
