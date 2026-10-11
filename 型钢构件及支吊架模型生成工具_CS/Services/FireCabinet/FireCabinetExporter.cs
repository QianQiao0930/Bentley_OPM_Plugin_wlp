using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 导出消防汇总与逐箱明细，Excel 复用现有工作簿写入器。
    /// </summary>
    internal static class FireCabinetExporter
    {
        internal static void WriteJson(string path, FireCabinetSnapshot snapshot)
        {
            var payload = new
            {
                itemTypeLibrary = FireCabinetCatalog.LibraryName,
                totalBoxCount = snapshot.TotalBoxCount,
                totalExtinguisherCount = snapshot.TotalExtinguisherCount,
                totalInteriorModelCount = snapshot.TotalInteriorModelCount,
                summary = snapshot.Summary,
                records = snapshot.Records
            };
            File.WriteAllText(path, new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(payload), new UTF8Encoding(false));
        }

        internal static void WriteExcel(string path, FireCabinetSnapshot snapshot)
        {
            var summary = new List<object[]>
            {
                new object[] { "灭火器箱清单" },
                new object[] { "箱体总数", snapshot.TotalBoxCount },
                new object[] { "配置灭火器总数", snapshot.TotalExtinguisherCount },
                new object[] { "外观模型总数", snapshot.TotalInteriorModelCount },
                new object[] { "箱型", "灭火器选型", "箱体数量", "配置灭火器数量", "外观模型数量" }
            };
            foreach (FireCabinetSummary item in snapshot.Summary)
            {
                summary.Add(new object[] { item.BoxModel, item.ExtinguisherModel, item.BoxCount, item.ExtinguisherCount, item.InteriorModelCount });
            }

            var details = new List<object[]>
            {
                new object[] { "模型", "元素ID", "箱型", "灭火器选型", "配置容量", "容量单位",
                    "宽度(mm)", "深度(mm)", "高度(mm)", "箱体数量", "配置灭火器数量", "外观模型数量", "外观模型规格", "容量说明" }
            };
            foreach (FireCabinetRecord record in snapshot.Records)
            {
                Dictionary<string, object> properties = record.Properties;
                details.Add(new object[]
                {
                    record.ModelName, record.ElementId,
                    Value(properties, "BoxModel"), Value(properties, "ExtinguisherModel"),
                    Value(properties, "ExtinguisherCapacity"), Value(properties, "CapacityUnit"),
                    Value(properties, "WidthMm"), Value(properties, "DepthMm"), Value(properties, "HeightMm"),
                    Value(properties, "BoxQuantity"), Value(properties, "ExtinguisherQuantity"),
                    FireCabinetStatisticsCalculator.ActualModelCount(properties),
                    Value(properties, "InteriorModelSpec"), Value(properties, "CapacityDescription")
                });
            }

            SupportStatisticsExporter.WriteWorkbook(path, new List<KeyValuePair<string, List<object[]>>>
            {
                new KeyValuePair<string, List<object[]>>("消防汇总", summary),
                new KeyValuePair<string, List<object[]>>("箱体明细", details)
            });
        }

        private static object Value(Dictionary<string, object> properties, string name)
        {
            object value;
            return properties.TryGetValue(name, out value) ? value : "";
        }
    }
}
