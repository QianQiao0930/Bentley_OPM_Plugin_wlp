using System;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 箱体局部毫米坐标转换为模型 UOR；前面朝局部 −Y。
    /// </summary>
    internal sealed class FireCabinetFrame
    {
        private readonly DPoint3d origin;
        private readonly double cosine;
        private readonly double sine;
        internal double Scale
        {
            get;
        }

        internal FireCabinetFrame(DPoint3d origin, double scale, double headingDegrees)
        {
            if (scale <= 0 || double.IsNaN(scale) || double.IsInfinity(scale) ||
                !IsFinite(origin.X) || !IsFinite(origin.Y) || !IsFinite(origin.Z))
            {
                throw new InvalidOperationException("放置点或模型长度单位无效。");
            }

            this.origin = origin;
            Scale = scale;
            double radians = headingDegrees * Math.PI / 180;
            cosine = Math.Cos(radians);
            sine = Math.Sin(radians);
        }

        internal DPoint3d Point(double x, double y, double z)
        {
            return new DPoint3d(origin.X + Scale * (cosine * x - sine * y),
                origin.Y + Scale * (sine * x + cosine * y), origin.Z + Scale * z);
        }

        internal DPoint3d Point(double[] point)
        {
            return Point(point[0], point[1], point[2]);
        }
        internal DVector3d Direction(double x, double y, double z)
        {
            return new DVector3d(cosine * x - sine * y, sine * x + cosine * y, z);
        }

        internal DVector3d Vector(double x, double y, double z)
        {
            DVector3d direction = Direction(x, y, z);
            return new DVector3d(direction.X * Scale, direction.Y * Scale, direction.Z * Scale);
        }

        private static bool IsFinite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }
    }
}
