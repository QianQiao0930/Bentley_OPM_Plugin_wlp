using System;
using System.Collections.Generic;
using System.Globalization;
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
                throw new Exception(label);
        }
        private static void Reject(Action action, string label)
        {
            try
            {
                action();
            }
            catch (InvalidOperationException) { checks++; return; }
            throw new Exception(label);
        }
        private static void Main()
        {
            try
            {
                Run();
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception.GetType().FullName);
                try
                {
                    Console.Error.WriteLine(exception.Message);
                }
                catch { }
                Console.Error.WriteLine(exception.StackTrace);
                Environment.ExitCode = 1;
            }
        }

        private static void Run()
        {
            var serializer = new JavaScriptSerializer();
            var cases = serializer.Deserialize<List<Dictionary<string, object>>>(File.ReadAllText(
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "python_reference.json")));
            foreach (Dictionary<string, object> reference in cases)
            {
                var parameters = new FireCabinetParameters
                {
                    ExtinguisherType = (string)reference["Type"],
                    Capacity = Convert.ToInt32(reference["Capacity"]),
                    BoxKey = (string)reference["Box"],
                    HeadingDegrees = 45
                };
                FireCabinetPlan plan = FireCabinetCalculator.Calculate(parameters);
                Check((plan.Interior == null ? 0 : plan.Interior.Capacity) == Convert.ToInt32(reference["VisualCapacity"]),
                    "选型与 Python 一致");
                Check(plan.CapacityUnit == (parameters.ExtinguisherType == "水基型灭火器" ? "L" : "kg"), "容量单位");
                Check(plan.Box.HeightMm == plan.Box.BodyHeightMm + plan.Box.LidHeightMm, "箱体总高度");
                Dictionary<string, object> metadata = FireCabinetStatisticsCalculator.Metadata(plan, plan.Interior == null ? 0 : 2);
                Check((int)metadata["BoxQuantity"] == 1 && (int)metadata["ExtinguisherQuantity"] == 2, "配置数量");
                Check((int)metadata["ExtinguisherCapacity"] == parameters.Capacity, "采购数量保留原选型容量");
                Check(metadata.Count == 32, "31 个兼容字段及实际模型数量");
                if (plan.Interior != null)
                {
                    Check(Math.Abs(2 * plan.HalfSeparationMm - plan.Interior.BodyDiameterMm - 50) < 1e-9, "两具净距 50 mm");
                    Check(plan.Interior.TotalHeightMm + 2 < plan.Box.BodyHeightMm, "外观模型不越过上盖");
                }
            }

            foreach (FireExtinguisherRecipe recipe in FireCabinetCatalog.Recipes)
            {
                Check(recipe.Parts.Count(part => part.Kind == "rounded_bottle") == 1, "真圆角瓶身配方");
                Check(recipe.Parts.Any(part => part.Name == "pressure_gauge_face"), "压力表");
                Check(recipe.Parts.Any(part => part.Kind == "torus"), "保险拉环");
                Check(recipe.Parts.All(part => part.Color.Length == 3), "RGB 配色");
                FireGeometryPart hose = recipe.Parts.FirstOrDefault(part => part.Kind == "hose");
                if (hose == null)
                    Check(recipe.Capacity == 2, "2 kg 直喷嘴");
                else
                {
                    double length = 0;
                    for (int index = 1; index < hose.Points.Length; index++)
                    {
                        double distance = Math.Sqrt(Enumerable.Range(0, 3).Sum(axis =>
                            Math.Pow(hose.Points[index][axis] - hose.Points[index - 1][axis], 2)));
                        Check(distance > 0, "软管无重复点");
                        length += distance;
                    }
                    Check(Math.Abs(length - 400) < 0.000001, "400 mm 软管参考长度");
                    Check(Math.Abs(length - recipe.HoseLengthMm) < 0.000001, "软管保存长度");
                }
            }

            Reject(() => FireCabinetCalculator.Calculate(new FireCabinetParameters { ExtinguisherType = "未知" }), "非法灭火器类型");
            Reject(() => FireCabinetCalculator.Calculate(new FireCabinetParameters { Capacity = 8 }), "不支持容量");
            Reject(() => FireCabinetCalculator.Calculate(new FireCabinetParameters { Capacity = 6, BoxKey = "XMDDG12" }), "箱体过小");
            Reject(() => FireCabinetCalculator.Calculate(new FireCabinetParameters { HeadingDegrees = double.NaN }), "非法方向");
            Reject(() => FireCabinetCalculator.Calculate(new FireCabinetParameters { HeadingDegrees = double.PositiveInfinity }), "无限方向");
            Check(FireCabinetCatalog.ItemTypeName == "FireExtinguisherBoxWithModel_CSHARP", "类型名称固定");
            Check(FireCabinetCatalog.ItemTypeName.StartsWith(FireCabinetCatalog.LegacyItemPrefix, StringComparison.Ordinal), "兼容原带模型前缀");

            FireCabinetPlan defaultPlan = FireCabinetCalculator.Calculate(new FireCabinetParameters());
            var first = FireCabinetStatisticsCalculator.Metadata(defaultPlan, 2);
            var empty = FireCabinetStatisticsCalculator.Metadata(defaultPlan, 0);
            var legacy = FireCabinetStatisticsCalculator.Metadata(defaultPlan, 2);
            legacy.Remove("ActualInteriorModelQuantity");
            var report = FireCabinetStatisticsCalculator.Summarize(new[]
            {
                new FireCabinetRecord { ModelName = "模型 1", ElementId = "9007199254740993", Properties = first },
                new FireCabinetRecord { ModelName = "模型 2", ElementId = "2", Properties = empty },
                new FireCabinetRecord { ModelName = "Python旧模型", ElementId = "3", Properties = legacy }
            });
            Check(report.TotalBoxCount == 3 && report.TotalExtinguisherCount == 6, "跨模型配置数量汇总");
            Check(report.TotalInteriorModelCount == 4, "空箱实际数量和旧记录兼容");
            Check((string)empty["InteriorModelCell"] == "（无）" && (double)empty["InteriorHeightMm"] == 0, "空箱不虚报模型规格");
            Check(report.Summary.Count == 1, "相同选型汇总");
            string directory = Path.Combine(Path.GetTempPath(), "FireCabinetCheck_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            try
            {
                string jsonPath = Path.Combine(directory, "report.json"), excelPath = Path.Combine(directory, "report.xlsx");
                FireCabinetExporter.WriteJson(jsonPath, report);
                FireCabinetExporter.WriteExcel(excelPath, report);
                var json = serializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(jsonPath));
                Check(Convert.ToInt32(json["totalExtinguisherCount"]) == 6, "JSON 配置具数");
                Check(File.ReadAllText(jsonPath).Contains("9007199254740993"), "元素 ID 作为字符串保留精度");
                using (var zip = ZipFile.OpenRead(excelPath))
                {
                    Check(zip.GetEntry("xl/worksheets/sheet2.xml") != null, "Excel 两张表");
                    var document = new XmlDocument();
                    using (Stream stream = zip.GetEntry("xl/worksheets/sheet2.xml").Open())
                    {
                        document.Load(stream);
                    }
                    var namespaces = new XmlNamespaceManager(document.NameTable);
                    namespaces.AddNamespace("s", "http://schemas.openxmlformats.org/spreadsheetml/2006/main");
                    Check(document.SelectNodes("//s:row", namespaces).Count == 4, "Excel 一箱一行明细");
                    Check(document.SelectSingleNode("//s:c[@r='L2']/s:v", namespaces).InnerText == "2", "Excel 正常箱模型数量");
                    Check(document.SelectSingleNode("//s:c[@r='L3']/s:v", namespaces).InnerText == "0", "Excel 空箱模型数量");
                    Check(document.SelectSingleNode("//s:c[@r='L4']/s:v", namespaces).InnerText == "2", "Excel 旧记录模型数量");
                    foreach (ZipArchiveEntry entry in zip.Entries.Where(item => item.FullName.EndsWith(".xml", StringComparison.Ordinal)))
                    {
                        using (XmlReader reader = XmlReader.Create(entry.Open()))
                        {
                            while (reader.Read())
                            {
                            }
                        }
                        Check(true, "Excel XML 可解析");
                    }
                }
            }
            finally { Directory.Delete(directory, true); }
            Console.WriteLine("FireCabinetCheck: " + checks.ToString(CultureInfo.InvariantCulture) + " checks passed.");
        }
    }
}
