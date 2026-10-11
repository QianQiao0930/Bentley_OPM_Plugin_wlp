using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Serialization.Json;

namespace SteelSectionProbe
{
    /// <summary>
    /// 灭火器箱原项目的规格、选型容量及独立嵌入的外观配方。
    /// </summary>
    internal static class FireCabinetCatalog
    {
        internal const string LibraryName = "FireProtectionComponents";
        internal const string ItemTypeName = "FireExtinguisherBoxWithModel_CSHARP";
        internal const string LegacyItemPrefix = "FireExtinguisherBoxWithModel_";
        internal const string CellName = "FireExtinguisherBoxWithModel";
        internal const double WallThicknessMm = 2;
        internal const double InteriorGapMm = 50;
        internal const double InteriorClearanceMm = 2;
        internal static readonly string[] Types = { "干粉灭火器", "二氧化碳灭火器", "水基型灭火器", "洁净气体灭火器" };
        internal static readonly FireCabinetPreset[] Boxes =
        {
            CreateBox("XMDDG12", 330, 160, 530, 450, 225, 80, 120),
            CreateBox("XMDDG22", 410, 200, 680, 600, 300, 140, 140),
            CreateBox("XMDDG32", 470, 240, 830, 750, 375, 200, 170)
        };
        private static readonly Lazy<FireExtinguisherRecipe[]> recipes =
            new Lazy<FireExtinguisherRecipe[]>(LoadRecipes);

        internal static FireExtinguisherRecipe[] Recipes
        {
            get
            {
                return recipes.Value;
            }
        }

        internal static int[] Capacities(string type)
        {
            ValidateType(type);
            return type == "二氧化碳灭火器" ? new[] { 2, 3 } : new[] { 2, 3, 4, 5, 6 };
        }

        internal static string Unit(string type)
        {
            ValidateType(type);
            return type == "水基型灭火器" ? "L" : "kg";
        }

        internal static FireCabinetPreset[] EligibleBoxes(string type, int capacity)
        {
            if (!Capacities(type).Contains(capacity))
            {
                throw new InvalidOperationException("所选灭火器类型不支持此容量。");
            }

            int first;
            if (type == "二氧化碳灭火器")
            {
                first = capacity == 2 ? 1 : 2;
            }
            else if (type == "水基型灭火器")
            {
                first = capacity <= 2 ? 0 : capacity <= 3 ? 1 : 2;
            }
            else
            {
                first = capacity <= 2 ? 0 : capacity <= 4 ? 1 : 2;
            }

            return Boxes.Skip(first).ToArray();
        }

        private static void ValidateType(string type)
        {
            if (!Types.Contains(type))
            {
                throw new InvalidOperationException("请选择支持的灭火器类型。");
            }
        }

        private static FireCabinetPreset CreateBox(string key, double width, double depth,
            double height, double bodyHeight, double middleHeight, double load, double testDiameter)
        {
            return new FireCabinetPreset
            {
                Key = key,
                WidthMm = width,
                DepthMm = depth,
                HeightMm = height,
                BodyHeightMm = bodyHeight,
                MidHeightMm = middleHeight,
                LidHeightMm = 80,
                LoadN = load,
                TestCylinderDiameterMm = testDiameter
            };
        }

        private static FireExtinguisherRecipe[] LoadRecipes()
        {
            using (var stream = typeof(FireCabinetCatalog).Assembly.GetManifestResourceStream(
                "SteelSectionProbe.fire_extinguisher_recipes.json"))
            {
                if (stream == null)
                {
                    throw new InvalidOperationException("缺少灭火器外观配方资源。");
                }

                var serializer = new DataContractJsonSerializer(typeof(FireExtinguisherRecipe[]));
                var result = (FireExtinguisherRecipe[])serializer.ReadObject(stream);
                if (result == null || result.Length != 5 || result.Any(item => item.Parts == null || item.Parts.Length < 10))
                {
                    throw new InvalidOperationException("灭火器外观配方不完整。");
                }

                return result;
            }
        }
    }
}
