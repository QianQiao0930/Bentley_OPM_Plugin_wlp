using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>
    /// 卷盘及接口的展示细节；不将外观卷绕长度当作 LQG16-30 产品的精确制造尺寸。
    /// </summary>
    internal static class HoseCabinetEquipmentBuilder
    {
        internal static Element Build(HoseCabinetPlan plan, HoseCabinetGeometry geometry)
        {
            var parts = new List<Element>();
            try
            {
                parts.Add(Reel(plan, geometry));
                parts.Add(Supply(plan, geometry));
                parts.Add(Gun(plan, geometry));
                return geometry.Cell("LIGHT_HOSE_EQUIPMENT", parts);
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException("水龙柜内部设备生成失败：" + exception.Message, exception);
            }
        }

        private static Element Reel(HoseCabinetPlan plan, HoseCabinetGeometry geometry)
        {
            double x = plan.ReelCenterXmm;
            double z = plan.ReelCenterZmm;
            double front = plan.ReelFrontYmm;
            var parts = new List<Element>
            {
                geometry.Cylinder(x, front, z, x, front + 120, z, 45, geometry.Red),
                geometry.Cylinder(x, front - 6, z, x, front + 120, z, 18, geometry.Steel)
            };
            foreach (double y in new[] { front, front + 117 })
            {
                var flange = geometry.CylinderBody(x, y, z, x, y + 3, z, 190);
                var holes = new List<Bentley.DgnPlatformNET.SolidKernelEntity>();
                for (int index = 0; index < 8; index++)
                {
                    double angle = index * Math.PI / 4;
                    double holeX = x + 130 * Math.Cos(angle);
                    double holeZ = z + 130 * Math.Sin(angle);
                    holes.Add(geometry.CylinderBody(holeX, y - 1, holeZ, holeX, y + 4, holeZ, 26));
                }
                SolidPrimitiveFactory.Subtract(ref flange, holes, "卷盘侧板减重孔");
                parts.Add(SolidPrimitiveFactory.Element(flange, geometry.Red));
                parts.Add(geometry.Torus(x, y + 1.5, z, 186, 3, true, geometry.Red));
            }
            // 只展示一层盘绕软管：一条五圈螺旋线，圆截面一次放样。
            // 螺距 18 mm 大于软管直径 16 mm，避免相邻圈接触拖慢几何内核。
            parts.Add(geometry.Helix(x, front + 15, z, 145, 90, 5, 8, true, geometry.Hose));
            // 中心盖、四颗可见紧固件和背部支架。
            parts.Add(geometry.Cylinder(x, front - 7, z, x, front, z, 30, geometry.Red));
            for (int index = 0; index < 4; index++)
            {
                double angle = index * Math.PI / 2;
                parts.Add(geometry.Cylinder(x + 23 * Math.Cos(angle), front - 9, z + 23 * Math.Sin(angle),
                    x + 23 * Math.Cos(angle), front - 7, z + 23 * Math.Sin(angle), 3, geometry.Steel));
            }
            parts.Add(geometry.Box(x - 30, front + 120, z - 50, x + 30, plan.Parameters.DepthMm - 1.5, z + 50, geometry.Steel));
            return geometry.Cell("P380_DETAILED_REEL", parts);
        }

        private static Element Supply(HoseCabinetPlan plan, HoseCabinetGeometry geometry)
        {
            double left = -plan.Parameters.WidthMm / 2;
            double outer = left - 120;
            double valve = left + 100;
            const double y = 60;
            double z = plan.Parameters.LowerHeightMm + 100;
            var parts = new List<Element>
            {
                geometry.TubeX(outer, left + 200, y, z, 17, 12, geometry.Brass),
                geometry.TubeX(left - 20, left + 20, y, z, 21, 17.5, geometry.Steel),
                geometry.TubeX(outer, outer + 28, y, z, 18, 12, geometry.Brass),
                geometry.HexX(outer + 28, outer + 40, y, z, 24, 12, geometry.Brass),
                // 接口螺纹只保留三道圆环示意，避免小尺寸多圈螺旋扫掠。
                geometry.Torus(outer + 5, y, z, 18.2, 0.65, false, geometry.Brass),
                geometry.Torus(outer + 13, y, z, 18.2, 0.65, false, geometry.Brass),
                geometry.Torus(outer + 21, y, z, 18.2, 0.65, false, geometry.Brass),
                geometry.Torus(outer + 41, y, z, 17.5, 1.4, false, geometry.Rubber),
                geometry.TubeX(valve - 23, valve + 23, y, z, 24, 12, geometry.Brass),
                geometry.HexX(valve - 32, valve - 23, y, z, 26, 12, geometry.Brass),
                geometry.HexX(valve + 23, valve + 32, y, z, 26, 12, geometry.Brass),
                geometry.Cylinder(valve, y, z + 20, valve, y, z + 64, 7, geometry.Brass)
            };
            // 手轮空心轮缘、轮毂及四根辐条，替代原实心圆盘。
            var wheel = geometry.CylinderBody(valve, y, z + 60, valve, y, z + 68, 50);
            SolidPrimitiveFactory.Subtract(ref wheel, new[]
            {
                geometry.CylinderBody(valve, y, z + 59, valve, y, z + 69, 43)
            }, "阀门手轮内孔");
            parts.Add(SolidPrimitiveFactory.Element(wheel, geometry.Red));
            parts.Add(geometry.Cylinder(valve, y, z + 60, valve, y, z + 68, 12, geometry.Red));
            parts.Add(geometry.Box(valve - 46, y - 3, z + 61, valve + 46, y + 3, z + 67, geometry.Red));
            parts.Add(geometry.Box(valve - 3, y - 46, z + 61, valve + 3, y + 46, z + 67, geometry.Red));
            // 给水管末端的快接套筒、锁紧环与通向卷盘中心的供水连接。
            double end = left + 200;
            parts.Add(geometry.TubeX(end - 24, end, y, z, 23, 12, geometry.Brass));
            parts.Add(geometry.Torus(end - 20, y, z, 22.5, 1.5, false, geometry.Steel));
            parts.Add(geometry.Torus(end - 5, y, z, 22.5, 1.5, false, geometry.Steel));
            parts.Add(geometry.Cylinder(end - 10, y, z + 20, end - 10, y, plan.ReelCenterZmm,
                8, geometry.Hose));
            parts.Add(geometry.Cylinder(end - 10, y, plan.ReelCenterZmm, plan.ReelCenterXmm,
                plan.ReelFrontYmm + 60, plan.ReelCenterZmm, 8, geometry.Hose));
            return geometry.Cell("DN25_VALVE_AND_CONNECTORS", parts);
        }

        private static Element Gun(HoseCabinetPlan plan, HoseCabinetGeometry geometry)
        {
            double x = -plan.Parameters.WidthMm / 2 + 70;
            double y = plan.Parameters.DepthMm - 30;
            double z = plan.Parameters.LowerHeightMm + 90;
            var parts = new List<Element>
            {
                geometry.TubeX(x, x + 220, y, z, 8, 3, geometry.Brass),
                geometry.TubeX(x + 220, x + 240, y, z, 12, 3, geometry.Brass),
                geometry.TubeX(x, x + 22, y, z, 14, 3, geometry.Brass),
                geometry.Torus(x + 5, y, z, 14, 1.5, false, geometry.Steel),
                geometry.Torus(x + 18, y, z, 14, 1.5, false, geometry.Steel),
                geometry.Cylinder(x + 40, y, z - 65, x + 40, y, z - 5, 9, geometry.Rubber),
                geometry.Cylinder(x + 40, y, z - 80, x + 40, y, z - 65, 10, geometry.Brass)
            };
            return geometry.Cell("BRASS_SPRAY_GUN", parts);
        }
    }
}
