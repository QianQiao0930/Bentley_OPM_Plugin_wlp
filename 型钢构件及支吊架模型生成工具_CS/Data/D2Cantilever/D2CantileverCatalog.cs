using System;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>D2/D3 表 1、表 2；未给出的荷载用 null 表示，不外推。</summary>
    internal static class D2CantileverCatalog
    {
        internal const string Keys = "ABCDEFGHJ";
        internal const string SupportType = "D2-[端焊悬臂架]";
        internal const string CellName = "D2_END_WELDED_CANTILEVER";
        internal const string AssemblyItemName = "PipeSupportAssembly_D2_CANTILEVER";
        internal static readonly double[] LoadColumns = { 250, 500, 750, 1000 };
        private static readonly D2CantileverVariant[] Items = {
            V('A', "equal_angle", "L50x50x6", "∠50×6", 1.4, 0.5, null, null),
            V('B', "equal_angle", "L75x75x7", "∠75×7", 3.6, 1.8, 0.9, 0.5),
            V('C', "equal_angle", "L100x100x10", "∠100×10", 10, 5, 2, 1.2),
            V('D', "parallel_channel", "12.6", "[12.6", 12, 5.8, 2.5, 1.4),
            V('E', "parallel_channel", "16a", "[16a", 20, 10, 5, 2.8),
            V('F', "hot_rolled_h", "H125x125x6.5x9xr", "H125×125×6.5×9", 39, 19, 13, 7.6),
            V('G', "hot_rolled_h", "H150x150x7x10xr", "H150×150×7×10", 65, 32, 22, 15),
            V('H', "hot_rolled_h", "H200x200x8x12xr", "H200×200×8×12", null, 70, 46, 33),
            V('J', "hot_rolled_h", "H250x250x9x14xr", "H250×250×9×14", null, 120, 83, 60)
        };

        private static readonly D2CantileverVariant[] SideWeldedItems = {
            V('A', "equal_angle", "L50x50x6", "∠50×6", 1.4, 0.5, null, null),
            V('B', "equal_angle", "L75x75x7", "∠75×7", 3.6, 1.8, 0.9, 0.5),
            V('C', "equal_angle", "L100x100x10", "∠100×10", 10, 5, 2, 1.2),
            V('D', "parallel_channel", "12.6", "[12.6", 12, 5.8, 2.5, 1.4),
            V('E', "parallel_channel", "16a", "[16a", 20, 10, 5, 2.8),
            V('F', "parallel_channel", "20a", "[20a", 31, 15, 8.8, 5),
            V('G', "parallel_channel", "25a", "[25a", 40, 20, 12, 6.8)
        };

        internal static string KeysFor(string kind)
        {
            if (kind == "D2") return Keys;
            if (kind == "D3") return "ABCDEFG";
            if (kind == "G11") return G11CantileverCatalog.Keys;
            throw new InvalidOperationException("悬臂架只支持 D2、D3 或 G11。");
        }

        internal static D2CantileverVariant Require(string kind, char key)
        {
            KeysFor(kind);
            if (kind == "D2") return Require(key);
            if (kind == "G11") return G11CantileverCatalog.Require(key).Section;
            foreach (var item in SideWeldedItems) if (item.Key == key) return item;
            throw new InvalidOperationException("D3 子项只支持 A～G。");
        }

        internal static string SupportTypeFor(string kind)
        {
            KeysFor(kind);
            if (kind == "G11") return "G11-[混凝土上生根的悬臂架]";
            return kind == "D2" ? SupportType : "D3-[侧焊悬臂架]";
        }

        internal static string CellNameFor(string kind)
        {
            KeysFor(kind);
            if (kind == "G11") return "G11_CONCRETE_CANTILEVER";
            return kind == "D2" ? CellName : "D3_SIDE_WELDED_CANTILEVER";
        }

        internal static string AssemblyItemNameFor(string kind)
        {
            KeysFor(kind);
            return "PipeSupportAssembly_" + kind + "_CANTILEVER";
        }

        internal static string ComponentItemName(string kind, string role)
        {
            KeysFor(kind);
            return "PipeSupportComponent_" + kind + "_CANTILEVER_" + role;
        }

        private static D2CantileverVariant V(char key, string family, string profile,
            string section, params double?[] loads)
        {
            return new D2CantileverVariant { Key = key, Family = family,
                ProfilePrefix = profile, Section = section, Loads = loads };
        }

        internal static D2CantileverVariant Require(char key)
        {
            foreach (var item in Items) if (item.Key == key) return item;
            throw new InvalidOperationException("D2 子项应为 A～H 或 J（不含 I）。");
        }

        internal static ProfileData Profile(D2CantileverVariant variant)
        {
            var family = ProfileLookup.Family(RuntimeData.Families, variant.Family);
            var profile = family == null ? null : family.Profiles.FirstOrDefault(p =>
                variant.Family == "hot_rolled_h"
                    ? p.Name.StartsWith(variant.ProfilePrefix, StringComparison.Ordinal)
                    : p.Name == variant.ProfilePrefix);
            if (profile == null) throw new InvalidOperationException("型钢目录缺少 " + variant.Section);
            return profile;
        }

        internal static ModeData Mode(D2CantileverVariant variant)
        {
            string mode = variant.Family == "equal_angle" ? "outer_corner" :
                variant.Family == "parallel_channel" ? "lower_left" : "geometric_center";
            return ProfileLookup.Mode(RuntimeData.Families, variant.Family, Profile(variant).Name, mode);
        }

        internal static string ComponentItemName(string role)
        {
            return "PipeSupportComponent_D2_CANTILEVER_" + role;
        }
    }
}
