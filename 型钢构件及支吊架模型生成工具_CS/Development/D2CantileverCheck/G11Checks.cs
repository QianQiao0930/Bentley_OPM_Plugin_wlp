using System;
using System.Linq;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static void CheckG11()
        {
            double?[,] loads = { { 0.5, 0.2, null }, { 2, 1, null }, { null, 4, 2 }, { null, 6, 3 } };
            double[] spacing = { 75, 100, 125, 150 };
            double[] edge = { 75, 100, 150, 200 };
            double[] diameters = { 8, 12, 16, 20 };
            double[] boltLengths = { 80, 120, 140, 180 };
            double[] heights = { 50, 75, 100, 160 };
            for (int row = 0; row < 4; row++)
            {
                char key = "ABCD"[row];
                for (int type = 1; type <= 5; type++)
                {
                    foreach (double heading in new[] { 0.0, 45, 90, 180, -90 })
                    {
                        var parameters = new D2CantileverParameters
                        {
                            Kind = "G11", Type = type, Subtype = key, Name = "G11", LoadDistanceMm = 600
                        };
                        D2CantileverPlan plan = D2CantileverCalculator.Calculate(parameters, 1100, heading);
                        G11CantileverPlan anchor = plan.ConcreteAnchor;
                        Equal(plan.BeamLengthMm, 1100, "G11 辅助线整长");
                        Equal(plan.SectionHeightMm, heights[row], "G11 真实截面高度");
                        True(plan.Number == "G11-" + type + "-" + key + "-1100", "G11 编号");
                        True(plan.Plate == null && anchor != null, "G11 无附加锚板");
                        Equal(anchor.Variant.BoltSpacingMm, spacing[row], "G11 表 2 S");
                        Equal(anchor.Variant.ConcreteEdgeDistanceMm, edge[row], "G11 表 2 C");
                        Equal(anchor.Bolt.BoltDiameterMm, diameters[row], "G11 锚栓直径");
                        Equal(anchor.Bolt.BoltLengthMm, boltLengths[row], "G11 锚栓总长");
                        Equal(anchor.Bolt.ActualEmbedmentMm + anchor.Bolt.BoltOutLengthMm,
                            boltLengths[row], "G11 埋深与露头合计");
                        True(anchor.Bolt.ActualEmbedmentMm >= anchor.Bolt.RequiredEmbedmentMm, "G11 有效埋深");
                        True(anchor.Bolt.BoltCount == 2 && anchor.Anchors.Length == 2, "G11 两根锚栓");
                        True(!plan.HorizontalLoadKn.HasValue, "G11 不套用 D2 水平荷载系数");
                        Equal(anchor.BoltNormalX, type == 2 || type == 3 ? 1 : 0, "G11 墙面法向");
                        Equal(anchor.BoltNormalY, type == 1 ? 1 : 0, "G11 侧面法向");
                        Equal(anchor.BoltNormalZ, type == 4 ? 1 : type == 5 ? -1 : 0, "G11 楼板法向");
                        bool connection = type == 2 || type == 3;
                        Equal(anchor.ConnectionLengthMm, connection ? spacing[row] + 150 : 0, "G11 竖向段实长");
                        if (connection)
                        {
                            CheckG11Connection(plan);
                        }

                        for (int index = 0; index < 2; index++)
                        {
                            double station = 75 + index * spacing[row];
                            G11AnchorLocation location = anchor.Anchors[index];
                            Equal(location.XMm, connection ? 0 : station, "G11 螺栓沿轴站位");
                            Equal(location.ZMm, type == 2 ? station : type == 3 ? -(row < 3 ? new[] { 6.0, 7, 10 }[row] : heights[row]) - station :
                                type == 1 ? -heights[row] / 2 : type == 4 ? -heights[row] : 0, "G11 螺栓标高");
                        }

                        ModeData mode = D2CantileverCatalog.Mode(plan.Variant);
                        double[] z = mode.Segments.SelectMany(segment => new[] { segment.Y0, segment.Y1 })
                            .Select(value => plan.SectionAnchorZmm + anchor.BeamVerticalSign * value).ToArray();
                        Equal(z.Max(), 0, "五类型横担顶面均在辅助线标高");
                        Equal(z.Min(), -heights[row], "五类型横担底面");
                        if (row < 3)
                        {
                            double thickness = D2CantileverCatalog.Profile(plan.Variant).Dimensions["t"];
                            True(mode.Segments.Any(segment =>
                                Math.Abs(segment.Y0 - thickness) < 0.000001 || Math.Abs(segment.Y1 - thickness) < 0.000001),
                                "角钢保留实际翼缘厚度");
                        }
                    }

                    for (int column = 0; column < 3; column++)
                    {
                        foreach (double distance in new[] { G11CantileverCatalog.LoadColumnsMm[column],
                            column == 0 ? 0.001 : G11CantileverCatalog.LoadColumnsMm[column - 1] + 0.001 })
                        {
                            var parameters = new D2CantileverParameters
                            {
                                Kind = "G11", Type = type, Subtype = key, Name = "G11", LoadDistanceMm = distance
                            };
                            D2CantileverPlan plan = D2CantileverCalculator.Calculate(parameters, 1100, 0);
                            True(plan.VerticalLoadKn == loads[row, column], "G11 表 1 分档及空档");
                        }
                    }
                }
            }

            var input = new D2CantileverParameters { Kind = "G11", Name = " ", LoadDistanceMm = 200 };
            True(D2CantileverCalculator.Calculate(input, 200, 0).Number == "G11-1-A-200", "G11 没有 150 mm 末端限制");
            foreach (double invalid in new[] { 0.0, -1, double.NaN, double.PositiveInfinity })
            {
                Reject(() => D2CantileverCalculator.Calculate(input, invalid, 0), "G11 非法 L");
            }

            foreach (double invalid in new[] { 0.0, -1, 1000.001, double.NaN, double.PositiveInfinity })
            {
                input.LoadDistanceMm = invalid;
                Reject(() => D2CantileverCalculator.Calculate(input, 1100, 0), "G11 非法 B");
            }

            input.LoadDistanceMm = 201;
            Reject(() => D2CantileverCalculator.Calculate(input, 200, 0), "G11 B 超过 L");
            input.LoadDistanceMm = 100;
            Reject(() => D2CantileverCalculator.Calculate(input, 155, 0), "G11 第二根垫圈超出横担");
            input.Type = 0;
            Reject(() => D2CantileverCalculator.Calculate(input, 1100, 0), "G11 类型下限");
            input.Type = 6;
            Reject(() => D2CantileverCalculator.Calculate(input, 1100, 0), "G11 类型上限");
            input.Type = 1;
            input.Subtype = 'E';
            Reject(() => D2CantileverCalculator.Calculate(input, 1100, 0), "G11 无 E 子项");
            input.Subtype = 'A';
            input.AddPlate = true;
            Reject(() => D2CantileverCalculator.Calculate(input, 1100, 0), "G11 不附加端板");
            input.AddPlate = false;
            Reject(() => D2CantileverCalculator.Calculate(input, 1100, double.NaN), "G11 非法方向");
            True(D2CantileverCatalog.AssemblyItemNameFor("G11") == "PipeSupportAssembly_G11_CANTILEVER", "G11 固定装配类型名");
            True(D2CantileverCatalog.ComponentItemName("G11", "MemberB") !=
                D2CantileverCatalog.ComponentItemName("D2", "MemberB"), "G11 清单与 D2 隔离");
        }

        /// <summary>用真实截面验证连接段朝向、贴合面和螺栓的受夹厚度。</summary>
        private static void CheckG11Connection(D2CantileverPlan plan)
        {
            G11CantileverPlan anchor = plan.ConcreteAnchor;
            ProfileData profile = D2CantileverCatalog.Profile(plan.Variant);
            bool isAngle = plan.Variant.Family == "equal_angle";
            ModeData mode = ProfileLookup.Mode(RuntimeData.Families, plan.Variant.Family, profile.Name,
                anchor.ConnectionWidthAlongSide ? "lower_left" : "outer_corner");
            double[][] points = mode.Segments.SelectMany(segment => new[]
            {
                new[] { segment.X0, segment.Y0 }, new[] { segment.X1, segment.Y1 }
            }).ToArray();
            double[] x = points.Select(point => anchor.ConnectionStartXMm +
                (anchor.ConnectionWidthAlongSide ? -point[1] : point[0])).ToArray();
            double[] y = points.Select(point => anchor.ConnectionStartYMm +
                (anchor.ConnectionWidthAlongSide ? point[0] : point[1])).ToArray();
            Equal(x.Min(), 0, "连接段墙面背面在 X=0");
            if (isAngle)
            {
                double thickness = profile.Dimensions["t"];
                double innerFaceY = -plan.SectionWidthMm / 2 + thickness;
                Equal(anchor.Bolt.PlateThicknessMm, thickness, "角钢锚固肢厚");
                Equal(y.Min(), plan.Parameters.Type == 3 ? innerFaceY : -plan.SectionWidthMm / 2,
                    "下置角钢侧面贴合横担竖直肢内表面");
                Equal(anchor.ConnectionStartZMm, plan.Parameters.Type == 3 ? -thickness : 0,
                    "下置角钢上端面贴合横担水平肢下表面");
                foreach (G11AnchorLocation bolt in anchor.Anchors)
                {
                    Equal(bolt.YMm, anchor.ConnectionStartYMm + plan.SectionWidthMm / 2,
                        "角钢锚栓随连接段横移");
                }
            }
            else
            {
                True(anchor.ConnectionWidthAlongSide, "槽钢连接段绕竖轴旋转 90 度");
                Equal(x.Max(), 160, "槽钢截面高度沿悬臂");
                Equal(y.Min(), -31.5, "连接段与横担腹板外侧共面");
                Equal(y.Max(), 31.5, "连接段和横担开口均朝横向正方向");
                Equal(anchor.Bolt.PlateThicknessMm, 10, "槽钢连接段以翼缘厚度计算锚栓");
                // 墙面翼缘从 X=0 至 tf，垫圈起点必须贴合其内表面。
                True(points.Any(point => Math.Abs(point[1] - 10) < 0.000001),
                    "真实轮廓具有锚固翼缘内表面");
                foreach (G11AnchorLocation bolt in anchor.Anchors)
                {
                    Equal(bolt.YMm, 0, "槽钢锚栓位于锚固翼缘横向中间");
                }
            }
        }
    }
}
