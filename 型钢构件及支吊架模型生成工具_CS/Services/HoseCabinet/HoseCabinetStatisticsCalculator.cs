using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 配套清单始终保留配置数量；实体数量单独记录，避免关闭内件时误报。
    /// </summary>
    internal static class HoseCabinetStatisticsCalculator
    {
        internal static List<HoseBomRow> Bom(HoseCabinetParameters parameters)
        {
            var rows = new List<HoseBomRow>
            {
                Row(1, "Cabinet", "轻便消防水龙柜", "钢", Specification(parameters), "个"),
                Row(2, "HoseReel", "轻便消防水龙卷盘", "钢喷塑", "P380", "个"),
                Row(3, "Hose", "轻便消防水龙", "衬胶", "LQG16-30", "条"),
                Row(4, "SprayGun", "直流喷雾喷枪", "全铜", "当量喷嘴直径 φ6", "支"),
                Row(5, "QuickCoupling", "快速接口", "全铜", "成品", "个"),
                Row(6, "QuickConnector", "快速接头", "钢或铜", "DN25", "个"),
                Row(7, "Valve", "阀门", "全铜", "DN25", "个"),
                Row(8, "PipeSleeve", "管套", "钢（扣压成型）", "成品", "个"),
            };
            if (parameters.ExtinguisherQuantity > 0)
            {
                rows.Add(Row(9, "Extinguisher", "手提式灭火器", "用户配套",
                    parameters.ExtinguisherModel, "具", parameters.ExtinguisherQuantity));
            }
            return rows;
        }

        internal static Dictionary<string, object> Metadata(HoseCabinetPlan plan)
        {
            HoseCabinetParameters parameters = plan.Parameters;
            bool hasModel = parameters.WithEquipment && plan.Interior != null;
            return new Dictionary<string, object>
            {
                { "ComponentName", "轻便消防水龙柜" },
                { "CabinetModel", "15S202-P53 轻便消防水龙柜（二）" },
                { "Standard", "15S202" }, { "DrawingPage", "53" },
                { "WidthMm", parameters.WidthMm }, { "DepthMm", parameters.DepthMm },
                { "HeightMm", parameters.HeightMm }, { "LowerCompartmentHeightMm", parameters.LowerHeightMm },
                { "ReelModel", "P380" }, { "ReelDiameterMm", 380.0 },
                { "HoseModel", "LQG16-30" }, { "GunModel", "直流喷雾喷枪" },
                { "GunNozzleDiameterMm", 6.0 }, { "ValveSize", "DN25" },
                { "ExtinguisherModel", parameters.ExtinguisherModel },
                { "ExtinguisherQuantity", parameters.ExtinguisherQuantity }, { "ExtinguisherUnit", "具" },
                { "ExtinguisherVisualCell", hasModel ? plan.Interior.CellName : "（无）" },
                { "ExtinguisherVisualSpec", hasModel ? plan.Interior.Model + " 外观示意" : "（无）" },
                { "ExtinguisherVisualDiameterMm", hasModel ? plan.Interior.BodyDiameterMm : 0.0 },
                { "ExtinguisherVisualHeightMm", hasModel ? plan.Interior.TotalHeightMm : 0.0 },
                { "CabinetQuantity", 1 }, { "ComponentKinds", Bom(parameters).Count },
                { "BomJson", new JavaScriptSerializer().Serialize(Bom(parameters).Select(row => new
                {
                    no = row.Number, code = row.Code, name = row.Name, material = row.Material,
                    spec = row.Specification, unit = row.Unit, qty = row.Quantity
                })) },
                { "SurfaceFinish", "钢制柜体，门面喷塑" }, { "FrontText", "轻便消防水龙柜" },
                { "FirePhoneText", "火警电话 119" },
                { "CoordinateConvention", "X=宽，Y=进深，Z=高，正面朝局部-Y；基点=底部前侧中心" },
                { "Unit", "套" }, { "ActualExtinguisherQuantity", hasModel ? parameters.ExtinguisherQuantity : 0 },
                { "ActualReelQuantity", parameters.WithEquipment ? 1 : 0 },
                { "WithEquipment", parameters.WithEquipment ? 1 : 0 },
                { "HeadingDegrees", parameters.HeadingDegrees },
                { "GeometryVersion", "CSHARP_DETAIL_1" }
            };
        }

        internal static HoseCabinetSnapshot Summarize(List<FireCabinetRecord> records)
        {
            var snapshot = new HoseCabinetSnapshot { Records = records };
            var groups = records.GroupBy(record => new
            {
                Size = Text(record.Properties, "WidthMm") + "×" + Text(record.Properties, "DepthMm") + "×" + Text(record.Properties, "HeightMm"),
                Model = Text(record.Properties, "ExtinguisherModel")
            });
            foreach (var group in groups)
            {
                snapshot.Summary.Add(new HoseCabinetSummary
                {
                    Specification = group.Key.Size,
                    ExtinguisherModel = group.Key.Model,
                    CabinetCount = group.Sum(record => Count(record.Properties, "CabinetQuantity")),
                    ExtinguisherCount = group.Sum(record => checked(Count(record.Properties, "CabinetQuantity") * Count(record.Properties, "ExtinguisherQuantity"))),
                    // 旧脚本未记录实际生成数量，不能从选型字段猜测。
                    ActualExtinguisherCount = group.Sum(record => checked(Count(record.Properties, "CabinetQuantity") * Count(record.Properties, "ActualExtinguisherQuantity")))
                });
            }
            snapshot.TotalCabinetCount = snapshot.Summary.Sum(item => item.CabinetCount);
            snapshot.TotalExtinguisherCount = snapshot.Summary.Sum(item => item.ExtinguisherCount);
            snapshot.TotalActualExtinguisherCount = snapshot.Summary.Sum(item => item.ActualExtinguisherCount);
            snapshot.Materials = records.SelectMany(record => RecordBom(record).Select(row =>
                Row(row.Number, row.Code, row.Name, row.Material, row.Specification, row.Unit,
                    checked(row.Quantity * Count(record.Properties, "CabinetQuantity")))))
                .GroupBy(row => new { row.Number, row.Name, row.Material, row.Specification, row.Unit })
                .Select(group => Row(group.Key.Number, "", group.Key.Name, group.Key.Material,
                    group.Key.Specification, group.Key.Unit, group.Sum(row => row.Quantity)))
                .OrderBy(row => row.Number).ToList();
            return snapshot;
        }

        internal static List<HoseBomRow> RecordBom(FireCabinetRecord record)
        {
            try
            {
                var serializer = new JavaScriptSerializer();
                var entries = serializer.DeserializeObject(Text(record.Properties, "BomJson")) as object[];
                if (entries != null && entries.Length > 0)
                {
                    var rows = new List<HoseBomRow>();
                    foreach (var item in entries)
                    {
                        var row = item as Dictionary<string, object>;
                        if (row == null)
                        {
                            throw new ArgumentException("器材行格式不正确。");
                        }
                        rows.Add(Row(Convert.ToInt32(row["no"], CultureInfo.InvariantCulture),
                            row.ContainsKey("code") ? Convert.ToString(row["code"]) : "",
                            Convert.ToString(row["name"]), Convert.ToString(row["material"]),
                            Convert.ToString(row["spec"]), Convert.ToString(row["unit"]),
                            Convert.ToInt32(row["qty"], CultureInfo.InvariantCulture)));
                    }
                    if (rows.All(row => row.Number > 0 && row.Quantity >= 0 && !string.IsNullOrEmpty(row.Name)))
                    {
                        return rows;
                    }
                }
            }
            catch (Exception exception) when (exception is ArgumentException || exception is InvalidOperationException ||
                exception is KeyNotFoundException || exception is FormatException || exception is OverflowException)
            {
                // 与原脚本兼容：损坏、缺失或形状不匹配的清单按已存配置字段重建。
            }
            return Bom(new HoseCabinetParameters
            {
                WidthMm = Number(record.Properties, "WidthMm"),
                DepthMm = Number(record.Properties, "DepthMm"),
                HeightMm = Number(record.Properties, "HeightMm"),
                ExtinguisherModel = Text(record.Properties, "ExtinguisherModel"),
                ExtinguisherQuantity = Count(record.Properties, "ExtinguisherQuantity")
            });
        }

        internal static int Count(Dictionary<string, object> properties, string key)
        {
            return FireCabinetStatisticsCalculator.Count(properties, key);
        }

        internal static string Text(Dictionary<string, object> properties, string key)
        {
            return FireCabinetStatisticsCalculator.Text(properties, key);
        }

        private static double Number(Dictionary<string, object> properties, string key)
        {
            return Convert.ToDouble(Text(properties, key), CultureInfo.InvariantCulture);
        }

        private static string Specification(HoseCabinetParameters parameters)
        {
            return string.Format(CultureInfo.InvariantCulture, "{0:0}×{1:0}×{2:0}",
                parameters.WidthMm, parameters.DepthMm, parameters.HeightMm);
        }

        private static HoseBomRow Row(int number, string code, string name, string material,
            string specification, string unit, int quantity = 1)
        {
            return new HoseBomRow
            {
                Number = number,
                Code = code,
                Name = name,
                Material = material,
                Specification = specification,
                Unit = unit,
                Quantity = quantity
            };
        }
    }
}
