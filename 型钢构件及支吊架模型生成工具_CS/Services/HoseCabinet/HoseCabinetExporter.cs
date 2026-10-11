using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    internal static class HoseCabinetExporter
    {
        internal static void WriteJson(string path, HoseCabinetSnapshot snapshot)
        {
            var payload = new
            {
                exportedAt = DateTimeOffset.Now.ToString("o"),
                standard = "15S202",
                drawingPage = "53",
                totalCabinetCount = snapshot.TotalCabinetCount,
                totalExtinguisherCount = snapshot.TotalExtinguisherCount,
                totalActualExtinguisherCount = snapshot.TotalActualExtinguisherCount,
                summary = snapshot.Summary,
                materials = snapshot.Materials,
                records = snapshot.Records
            };
            File.WriteAllText(path, new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(payload), new UTF8Encoding(false));
        }

        internal static void WriteExcel(string path, HoseCabinetSnapshot snapshot)
        {
            var summary = new List<object[]> { new object[] { "轻便消防水龙柜清单", "15S202 第53页" },
                new object[] { "柜体总数", snapshot.TotalCabinetCount },
                new object[] { "配置灭火器", snapshot.TotalExtinguisherCount },
                new object[] { "已记录实际灭火器模型", snapshot.TotalActualExtinguisherCount },
                new object[] { "柜体规格", "灭火器型号", "柜数", "配置具数", "已记录模型具数" } };
            foreach (HoseCabinetSummary item in snapshot.Summary)
            {
                summary.Add(new object[] { item.Specification, item.ExtinguisherModel,
                    item.CabinetCount, item.ExtinguisherCount, item.ActualExtinguisherCount });
            }
            var materials = new List<object[]> { new object[] { "序号", "名称", "材质", "规格", "单位", "配置总数量" } };
            foreach (HoseBomRow item in snapshot.Materials)
            {
                materials.Add(new object[] { item.Number, item.Name, item.Material, item.Specification, item.Unit, item.Quantity });
            }
            var details = new List<object[]> { new object[] { "模型", "元素ID", "宽(mm)", "深(mm)", "高(mm)",
                "隔板高(mm)", "柜数", "灭火器型号", "配置具数/柜", "实际模型具数/柜", "卷盘模型数/柜", "外观规格", "内部设备", "旋转角度" } };
            foreach (FireCabinetRecord record in snapshot.Records)
            {
                var values = new List<object> { record.ModelName, record.ElementId };
                foreach (string key in new[] { "WidthMm", "DepthMm", "HeightMm", "LowerCompartmentHeightMm",
                    "CabinetQuantity", "ExtinguisherModel", "ExtinguisherQuantity", "ActualExtinguisherQuantity",
                    "ActualReelQuantity", "ExtinguisherVisualSpec", "WithEquipment", "HeadingDegrees" })
                {
                    object value;
                    values.Add(record.Properties.TryGetValue(key, out value) ? value : "未记录");
                }
                details.Add(values.ToArray());
            }
            SupportStatisticsExporter.WriteWorkbook(path, new List<KeyValuePair<string, List<object[]>>>
            {
                new KeyValuePair<string, List<object[]>>("柜型汇总", summary),
                new KeyValuePair<string, List<object[]>>("配置器材", materials),
                new KeyValuePair<string, List<object[]>>("柜体明细", details)
            });
        }
    }
}
