using System;

namespace SteelSectionProbe
{
    /// <summary>G11 表 1、表 2；空荷载档位保留为 null，不外推。</summary>
    internal static class G11CantileverCatalog
    {
        internal const string Keys = "ABCD";
        internal const double FirstBoltDistanceMm = 75;
        internal static readonly double[] LoadColumnsMm = { 500, 750, 1000 };

        private static readonly G11CantileverVariant[] Items =
        {
            Create('A', "equal_angle", "L50x50x6", "∠50×6", 75, 75, 0.5, 0.2, null),
            Create('B', "equal_angle", "L75x75x7", "∠75×7", 100, 100, 2, 1, null),
            Create('C', "equal_angle", "L100x100x10", "∠100×10", 125, 150, null, 4, 2),
            Create('D', "parallel_channel", "16a", "[16a", 150, 200, null, 6, 3)
        };

        internal static G11CantileverVariant Require(char key)
        {
            foreach (G11CantileverVariant item in Items)
            {
                if (item.Section.Key == key)
                {
                    return item;
                }
            }

            throw new InvalidOperationException("G11 子项只支持 A～D。");
        }

        private static G11CantileverVariant Create(char key, string family, string profile,
            string section, double spacingMm, double edgeDistanceMm, params double?[] loads)
        {
            return new G11CantileverVariant
            {
                Section = new D2CantileverVariant
                {
                    Key = key,
                    Family = family,
                    ProfilePrefix = profile,
                    Section = section,
                    Loads = loads
                },
                BoltSpacingMm = spacingMm,
                ConcreteEdgeDistanceMm = edgeDistanceMm
            };
        }
    }
}
