using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 开口箱体、隔板和带双观察窗的柜门。所有子件离线生成后封装为一个单元。
    /// </summary>
    internal static class HoseCabinetBuilder
    {
        internal static FireCabinetBuildResult Build(HoseCabinetPlan plan, DPoint3d origin)
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null || !model.Is3d)
            {
                throw new InvalidOperationException("轻便消防水龙柜需要三维活动模型。");
            }
            var parameters = plan.Parameters;
            var frame = new FireCabinetFrame(origin, model.GetModelInfo().UorPerMeter / 1000, parameters.HeadingDegrees);
            var geometry = new HoseCabinetGeometry(frame);
            double left = -parameters.WidthMm / 2;
            double right = parameters.WidthMm / 2;
            double depth = parameters.DepthMm;
            double height = parameters.HeightMm;
            double divider = parameters.LowerHeightMm;
            const double wall = HoseCabinetCalculator.WallMm;
            var shell = geometry.BoxBody(left, 0, 0, right, depth, height);
            SolidPrimitiveFactory.Subtract(ref shell, new[]
            {
                geometry.BoxBody(left + wall, -1, wall, right - wall, depth - wall, height - wall)
            }, "水龙柜内腔");
            var parts = new List<Element>
            {
                SolidPrimitiveFactory.Element(shell, geometry.Red),
                geometry.Box(left + wall, 0, divider, right - wall, depth - wall, divider + wall, geometry.Red)
            };
            var door = geometry.BoxBody(left, -wall, 0, right, 0, height);
            foreach (double[] window in new[]
            {
                new[] { Math.Max(divider + 150, plan.ReelCenterZmm - 200), height - 20 },
                new[] { 60.0, divider - 15 }
            })
            {
                if (window[1] > window[0])
                {
                    SolidPrimitiveFactory.Subtract(ref door, new[]
                    {
                        geometry.BoxBody(left + 45, -wall - 1, window[0], right - 45, 1, window[1])
                    }, "柜门观察窗");
                }
            }
            parts.Add(SolidPrimitiveFactory.Element(door, geometry.Red));
            // 门拉手采用独立立柱与圆柱握柄，避免原实心矩形块遮挡中部标识。
            foreach (double z in new[] { divider + 30, divider + 130 })
            {
                parts.Add(geometry.Cylinder(right - 62, -wall, z, right - 62, -16, z, 5, geometry.Steel));
            }
            parts.Add(geometry.Cylinder(right - 62, -16, divider + 30, right - 62, -16, divider + 130, 5, geometry.Steel));
            double titleHeight = Math.Max(18, Math.Min(height * 0.05, 34));
            titleHeight = Math.Min(titleHeight, (parameters.WidthMm - 160) / 7);
            parts.Add(FireCabinetBuilder.Text("轻便消防水龙柜", frame, -20, -wall - 0.3, divider + 95, titleHeight, true));
            parts.Add(FireCabinetBuilder.Text("火警电话 119", frame, -20, -wall - 0.3, divider + 50, Math.Max(12, titleHeight * 0.6), true));
            if (parameters.WithEquipment)
            {
                parts.Add(HoseCabinetEquipmentBuilder.Build(plan, geometry));
                foreach (double x in plan.BottleCentersMm)
                {
                    var innerFrame = new FireCabinetFrame(frame.Point(x, depth / 2, wall), frame.Scale, parameters.HeadingDegrees);
                    parts.Add(FireExtinguisherBuilder.Build(plan.Interior, innerFrame));
                }
            }
            return new FireCabinetBuildResult
            {
                Cell = geometry.Cell("LightHoseCabinet", parts),
                InteriorModelCount = parameters.WithEquipment ? parameters.ExtinguisherQuantity : 0,
                Warning = parameters.WithEquipment ? "" : "仅生成柜体；清单保留配套配置，实际内件数量为零。"
            };
        }
    }
}
