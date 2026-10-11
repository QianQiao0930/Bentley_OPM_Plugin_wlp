using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>
    /// 构件实例元数据及消防清单汇总，不引用 Bentley API。
    /// </summary>
    internal static class FireCabinetStatisticsCalculator
    {
        internal static Dictionary<string, object> Metadata(FireCabinetPlan plan, int interiorModelCount)
        {
            FireCabinetPreset box = plan.Box;
            bool hasInterior = interiorModelCount == 2 && plan.Interior != null;
            return new Dictionary<string, object>
            {
                { "ComponentName", "XMDDG单体-置地型-翻盖式灭火器箱（含灭火器外观模型）" },
                { "BoxModel", box.Key + "｜单体-置地型-翻盖式（2具）" },
                { "ExtinguisherModel", plan.ExtinguisherLabel },
                { "ExtinguisherType", plan.Parameters.ExtinguisherType },
                { "ExtinguisherCapacity", plan.Parameters.Capacity },
                { "CapacityUnit", plan.CapacityUnit },
                { "CapacityDescription", Description(box.Key) },
                { "InteriorModelCell", hasInterior ? plan.Interior.CellName : "（无）" },
                { "InteriorModelSpec", hasInterior ? "Ø" + plan.Interior.BodyDiameterMm + "×" + plan.Interior.TotalHeightMm + " mm（外观简化模型）" : "未生成箱内外观模型" },
                { "InteriorDiameterMm", hasInterior ? plan.Interior.BodyDiameterMm : 0.0 },
                { "InteriorHeightMm", hasInterior ? plan.Interior.TotalHeightMm : 0.0 },
                { "WidthMm", box.WidthMm }, { "DepthMm", box.DepthMm }, { "HeightMm", box.HeightMm },
                { "L1Mm", box.WidthMm }, { "L2Mm", box.DepthMm },
                { "L4Mm", box.BodyHeightMm }, { "L5Mm", box.MidHeightMm }, { "L6Mm", box.LidHeightMm },
                { "LoadN", box.LoadN }, { "StiffnessTestCylinderDiameterMm", box.TestCylinderDiameterMm },
                { "BoxQuantity", 1 }, { "ExtinguisherQuantity", 2 }, { "ActualInteriorModelQuantity", interiorModelCount },
                { "SurfaceColor", "红色" }, { "TextColor", "黄色" },
                { "FrontText", "灭火器箱" }, { "EnglishFrontText", "Fire Extinguisher Cabinet" },
                { "FireAlarmText", "火警电话" }, { "TopText", "消防器材，严禁挪用" },
                { "CoordinateConvention", "X=长边，Y=短边/进深，Z=高度，正面朝-Y" }, { "Unit", "箱" }
            };
        }

        internal static FireCabinetSnapshot Summarize(IEnumerable<FireCabinetRecord> records)
        {
            var snapshot = new FireCabinetSnapshot { Records = records.ToList() };
            snapshot.Summary = snapshot.Records.GroupBy(record => new
            {
                Box = Text(record.Properties, "BoxModel"),
                Extinguisher = Text(record.Properties, "ExtinguisherModel")
            }).OrderBy(group => group.Key.Box).ThenBy(group => group.Key.Extinguisher)
                .Select(group => new FireCabinetSummary
                {
                    BoxModel = group.Key.Box,
                    ExtinguisherModel = group.Key.Extinguisher,
                    BoxCount = group.Sum(record => Count(record.Properties, "BoxQuantity")),
                    ExtinguisherCount = group.Sum(record => Count(record.Properties, "ExtinguisherQuantity")),
                    InteriorModelCount = group.Sum(record => ActualModelCount(record.Properties))
                }).ToList();
            snapshot.TotalBoxCount = snapshot.Summary.Sum(item => item.BoxCount);
            snapshot.TotalExtinguisherCount = snapshot.Summary.Sum(item => item.ExtinguisherCount);
            snapshot.TotalInteriorModelCount = snapshot.Summary.Sum(item => item.InteriorModelCount);
            return snapshot;
        }

        internal static string Text(Dictionary<string, object> properties, string name)
        {
            object value;
            return properties.TryGetValue(name, out value) ? Convert.ToString(value, CultureInfo.InvariantCulture) : "";
        }

        internal static int Count(Dictionary<string, object> properties, string name)
        {
            int value;
            return int.TryParse(Text(properties, name), NumberStyles.Integer, CultureInfo.InvariantCulture, out value) ? value : 0;
        }

        internal static int ActualModelCount(Dictionary<string, object> properties)
        {
            if (properties.ContainsKey("ActualInteriorModelQuantity"))
            {
                return Count(properties, "ActualInteriorModelQuantity");
            }
            // Python 旧记录没有实际模型数量；仅依据已保存的模型名称推算，不回写旧记录。
            string cell = Text(properties, "InteriorModelCell");
            return cell.StartsWith("HUAHAI_", StringComparison.Ordinal) ? Count(properties, "ExtinguisherQuantity") : 0;
        }

        private static string Description(string key)
        {
            switch (key)
            {
                case "XMDDG12":
                    return "2L水基 / 2kg干粉 / 2kg洁净气体（均为2具）";
                case "XMDDG22":
                    return "2kg二氧化碳 / 3L水基 / 4kg干粉 / 4kg洁净气体（均为2具）";
                default:
                    return "3kg二氧化碳 / 6L水基 / 6kg干粉 / 6kg洁净气体（均为2具）";
            }
        }
    }
}
