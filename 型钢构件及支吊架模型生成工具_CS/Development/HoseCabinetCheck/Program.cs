using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Web.Script.Serialization;
using System.Xml;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;

        private static void Check(bool value, string label)
        {
            checks++;
            if (!value)
            {
                throw new InvalidOperationException(label);
            }
        }

        private static void Reject(Action action, string label)
        {
            try
            {
                action();
            }
            catch (InvalidOperationException)
            {
                checks++;
                return;
            }
            throw new InvalidOperationException(label);
        }

        private static void Main()
        {
            try
            {
                Run();
                Console.WriteLine("HoseCabinetCheck: " + checks + " checks passed.");
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception.Message);
                Console.Error.WriteLine(exception.StackTrace);
                Environment.ExitCode = 1;
            }
        }

        private static void Run()
        {
            var serializer = new JavaScriptSerializer();
            var fixtures = serializer.Deserialize<List<Dictionary<string, object>>>(File.ReadAllText(
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "python_reference.json")));
            foreach (var fixture in fixtures)
            {
                var parameters = new HoseCabinetParameters
                {
                    WidthMm = Convert.ToDouble(fixture["Width"]),
                    ExtinguisherModel = (string)fixture["Model"],
                    ExtinguisherQuantity = Convert.ToInt32(fixture["Quantity"])
                };
                if (!(bool)fixture["Valid"])
                {
                    Reject(() => HoseCabinetCalculator.Calculate(parameters), "原 Python 拒绝组合");
                    continue;
                }
                var plan = HoseCabinetCalculator.Calculate(parameters);
                Check((plan.Interior == null ? 0 : plan.Interior.Capacity) == Convert.ToInt32(fixture["VisualCapacity"]), "原 Python 外观规格对照");
                Check(plan.BottleCentersMm.Count == parameters.ExtinguisherQuantity, "实体配置数量");
                foreach (double x in plan.BottleCentersMm)
                {
                    double radius = plan.Interior.BodyDiameterMm / 2;
                    Check(x - radius >= -parameters.WidthMm / 2 + 3.5, "筒体左侧间隙");
                    Check(x + radius + HoseCabinetCalculator.Overhang(plan.Interior) <= parameters.WidthMm / 2 - 3.5, "软管右侧間隙");
                    Check(1.5 + plan.Interior.TotalHeightMm <= parameters.LowerHeightMm - 2, "隔板下净高");
                }
                for (int index = 1; index < plan.BottleCentersMm.Count; index++)
                {
                    Check(plan.BottleCentersMm[index] - plan.BottleCentersMm[index - 1] - plan.Interior.BodyDiameterMm >=
                        HoseCabinetCalculator.Overhang(plan.Interior) + 2 - 1e-8, "相邻软管避让");
                }
            }

            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { WidthMm = double.NaN }), "NaN尺寸");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { HeadingDegrees = double.PositiveInfinity }), "无限角度");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { DepthMm = 130 }), "卷盘前侧凸出");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { HeightMm = 920 }), "卷盘穿隔板");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { WidthMm = 390 }), "卷盘穿侧壁");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { ExtinguisherQuantity = -1 }), "负数具数");
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters { ExtinguisherQuantity = 51 }), "超量具数");
            Check(HoseCabinetCalculator.ParseCapacity("MFZ/ABC2026-8") == 8, "型号末尾数字");
            Check(HoseCabinetCalculator.ParseCapacity("未指定") == 4, "无容量默认值");

            VerifyHelices();
            Reject(() => HoseCabinetCalculator.Calculate(new HoseCabinetParameters
            {
                WithEquipment = false,
                ExtinguisherQuantity = 0,
                HeightMm = 650
            }), "小空柜标识越界");
            var normal = HoseCabinetCalculator.Calculate(new HoseCabinetParameters());
            Check(normal.ReelCenterXmm - 190 >= -275 + 1.5, "默认卷盘左边界");
            Check(normal.ReelCenterZmm + 190 <= 1200 - 1.5, "默认卷盘顶边界");
            Check(normal.ReelFrontYmm - 9 >= 1.5, "默认中心盖前边界");
            Check(normal.ReelFrontYmm + 120 < 160 - 1.5, "卷盘背面间隙");
            var normalValues = HoseCabinetStatisticsCalculator.Metadata(normal);
            Check(normalValues.Count == 34, "兼容29个旧字段加5个新字段");
            Check((int)normalValues["ActualExtinguisherQuantity"] == 2, "默认实际灭火器数量");
            var oldBom = serializer.DeserializeObject((string)normalValues["BomJson"]) as object[];
            Check(oldBom.Length == 9, "旧格式BomJson九项");
            var first = (Dictionary<string, object>)oldBom[0];
            Check(first.ContainsKey("no") && first.ContainsKey("qty") && !first.ContainsKey("Number"), "Python BOM字段兼容");

            var empty = HoseCabinetCalculator.Calculate(new HoseCabinetParameters { WithEquipment = false });
            var emptyValues = HoseCabinetStatisticsCalculator.Metadata(empty);
            Check((int)emptyValues["ActualExtinguisherQuantity"] == 0 && (int)emptyValues["ActualReelQuantity"] == 0, "关闭内件实际数量为零");
            Check((int)emptyValues["ExtinguisherQuantity"] == 2, "关闭内件保留配套");
            var zero = HoseCabinetCalculator.Calculate(new HoseCabinetParameters { ExtinguisherQuantity = 0 });
            Check(HoseCabinetStatisticsCalculator.Bom(zero.Parameters).Count == 8, "零具数不增加器材第9项");

            var oldValues = new Dictionary<string, object>(normalValues);
            foreach (string key in new[] { "ActualExtinguisherQuantity", "ActualReelQuantity", "WithEquipment", "HeadingDegrees", "GeometryVersion" })
            {
                oldValues.Remove(key);
            }
            var custom = new FireCabinetRecord { Properties = new Dictionary<string, object>(normalValues) };
            custom.Properties["BomJson"] = "[{\"no\":7,\"code\":\"Valve\",\"name\":\"阀门\",\"material\":\"全铜\",\"spec\":\"DN25\",\"unit\":\"个\",\"qty\":4}]";
            Check(HoseCabinetStatisticsCalculator.RecordBom(custom).Single().Quantity == 4, "保留Python清单自定义器材数量");
            oldValues["CabinetQuantity"] = 3;
            oldValues["BomJson"] = "malformed";
            var records = new List<FireCabinetRecord>
            {
                new FireCabinetRecord { ModelName = "Model1", ElementId = "9007199254740993", Properties = normalValues },
                new FireCabinetRecord { ModelName = "Model1", ElementId = "2", Properties = emptyValues },
                new FireCabinetRecord { ModelName = "Model2", ElementId = "3", Properties = oldValues }
            };
            var snapshot = HoseCabinetStatisticsCalculator.Summarize(records);
            Check(snapshot.TotalCabinetCount == 5 && snapshot.TotalExtinguisherCount == 10, "跨模型数量及旧柜倍数");
            Check(snapshot.TotalActualExtinguisherCount == 2, "未记录旧模型数量不推断");
            Check(snapshot.Materials.Count == 9, "器材分组九行");
            Check(snapshot.Materials.Single(row => row.Number == 7).Quantity == 5, "阀门配置总量");
            Check(snapshot.Materials.Single(row => row.Number == 9).Quantity == 10, "灭火器总量");
            Check(snapshot.Materials.Single(row => row.Number == 1).Specification == "550×160×1200", "柜体规格及损坏Bom回退");

            string directory = Path.Combine(Path.GetTempPath(), "HoseCabinetCheck_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            try
            {
                string json = Path.Combine(directory, "清单.json");
                string excel = Path.Combine(directory, "清单.xlsx");
                HoseCabinetExporter.WriteJson(json, snapshot);
                HoseCabinetExporter.WriteExcel(excel, snapshot);
                string report = File.ReadAllText(json);
                Check(report.Contains("9007199254740993"), "64位ID保持字符串精度");
                var payload = serializer.Deserialize<Dictionary<string, object>>(report);
                Check(Convert.ToInt32(payload["totalExtinguisherCount"]) == 10, "JSON配置数量");
                using (var archive = ZipFile.OpenRead(excel))
                {
                    Check(archive.Entries.Count(entry => entry.FullName.StartsWith("xl/worksheets/sheet")) == 3, "汇总器材明细三张工作表");
                    foreach (var entry in archive.Entries.Where(entry => entry.FullName.EndsWith(".xml")))
                    {
                        using (var stream = entry.Open())
                        {
                            var document = new XmlDocument();
                            document.Load(stream);
                            Check(document.DocumentElement != null, "Excel XML有效");
                        }
                    }
                    using (var reader = new StreamReader(archive.GetEntry("xl/worksheets/sheet3.xml").Open()))
                    {
                        Check(reader.ReadToEnd().Contains("未记录"), "旧记录缺失字段明示");
                    }
                }
            }
            finally
            {
                Directory.Delete(directory, true);
            }
        }
        private static void VerifyHelices()
        {
            double radius = 145;
            double startY = 50;
            double travel = 90;
            var data = HoseHelixCalculator.Calculate(-75, startY, 1000, radius, travel, 5, true);
            Check(data.Knots.Count == data.Poles.Count + 4, "三次样条节点完整");
            Check(Math.Abs(data.Poles.Last()[1] - startY - travel) < 1e-8, "卷绕层轴向终点");
            double maximumError = 0;
            bool bounded = true;
            bool continuous = true;
            for (int index = 0; index < data.Poles.Count - 1; index += 3)
            {
                for (int sample = 0; sample <= 8; sample++)
                {
                    double t = sample / 8.0;
                    double u = 1 - t;
                    var point = new double[3];
                    for (int axis = 0; axis < 3; axis++)
                    {
                        point[axis] = u * u * u * data.Poles[index][axis] +
                            3 * u * u * t * data.Poles[index + 1][axis] +
                            3 * u * t * t * data.Poles[index + 2][axis] + t * t * t * data.Poles[index + 3][axis];
                    }
                    double radial = Math.Sqrt(Math.Pow(point[0] + 75, 2) + Math.Pow(point[2] - 1000, 2));
                    maximumError = Math.Max(maximumError, Math.Abs(radial - radius));
                    bounded &= radial + 8 < 190 && point[1] - 8 >= 38 && point[1] + 8 <= 152;
                }
                if (index + 4 < data.Poles.Count)
                {
                    for (int axis = 0; axis < 3; axis++)
                    {
                        continuous &= Math.Abs(data.Poles[index + 3][axis] - data.Poles[index + 2][axis] -
                            data.Poles[index + 4][axis] + data.Poles[index + 3][axis]) < 1e-8;
                    }
                }
            }
            Check(maximumError < 0.2, "简化螺旋样条半径误差小于0.2mm");
            Check(bounded, "软管外壁位于两侧板及P380直径内");
            Check(continuous, "卷绕段C1连续");
            var simplified = HoseHelixCalculator.Calculate(-75, 50, 1000, 145, 90, 5, true);
            Check(simplified.Poles.Count <= 125, "单次软管放样控制点数量受限");
            Check(90.0 / 5 > 2 * 8, "螺距大于管径避免相邻圈接触");
        }
    }
}
