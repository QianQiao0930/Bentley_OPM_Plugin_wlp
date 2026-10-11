using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>
    /// 纯毫米螺旋样条数据；让实际卷绕路径和螺纹的边界可在宿主外验证。
    /// </summary>
    internal static class HoseHelixCalculator
    {
        internal static HoseHelixPath Calculate(double x, double y, double z, double radius,
            double travel, int turns, bool axisY)
        {
            if (radius <= 0 || turns < 1 || turns > 100 || travel == 0)
            {
                throw new InvalidOperationException("卷绕半径、圈数或轴向长度无效。");
            }
            var result = new HoseHelixPath();
            // 展示模型每圈八段即可；不采用制造级的密集路径。
            int segments = turns * 8;
            Func<double, double[]> point = fraction =>
            {
                double angle = fraction * turns * 2 * Math.PI;
                return axisY ? new[] { x + radius * Math.Cos(angle), y + travel * fraction, z + radius * Math.Sin(angle) } :
                    new[] { x + travel * fraction, y + radius * Math.Cos(angle), z + radius * Math.Sin(angle) };
            };
            Func<double, double[]> derivative = fraction =>
            {
                double angle = fraction * turns * 2 * Math.PI;
                double factor = radius * turns * 2 * Math.PI;
                return axisY ? new[] { -factor * Math.Sin(angle), travel, factor * Math.Cos(angle) } :
                    new[] { travel, -factor * Math.Sin(angle), factor * Math.Cos(angle) };
            };
            result.StartTangent = derivative(0);
            result.Poles.Add(point(0));
            for (int index = 0; index < segments; index++)
            {
                double start = index / (double)segments;
                double end = (index + 1) / (double)segments;
                double[] first = point(start);
                double[] last = point(end);
                double[] firstTangent = derivative(start);
                double[] lastTangent = derivative(end);
                double handle = 1.0 / segments / 3;
                result.Poles.Add(new[] { first[0] + firstTangent[0] * handle, first[1] + firstTangent[1] * handle, first[2] + firstTangent[2] * handle });
                result.Poles.Add(new[] { last[0] - lastTangent[0] * handle, last[1] - lastTangent[1] * handle, last[2] - lastTangent[2] * handle });
                result.Poles.Add(last);
                if (index < segments - 1)
                {
                    result.Knots.AddRange(new[] { end, end, end });
                }
            }
            result.Knots.AddRange(new[] { 1.0, 1, 1, 1 });
            return result;
        }
    }
}
