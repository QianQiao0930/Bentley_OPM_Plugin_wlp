using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace SteelSectionProbe
{
    /// <summary>
    /// 型钢页「当前截面参数」显示表的检查。断言对象是
    /// <see cref="SteelSectionCatalog"/> 与 Python 原版
    /// <c>型钢截面生成器/steel_sections/steel_registry.py</c> 的 <c>family.fields</c> 完全一致，
    /// 并且每个字段在嵌入的 profiles.bin 里都存在（否则界面上会少一行、或又漏出英文键）。
    /// <para>
    /// 运行：<c>dotnet run --project Development/SteelSectionCheck/SteelSectionCheck.csproj -c Release</c>。
    /// 本工程自带一份 profiles.bin 嵌入资源，所以能读真实数据。
    /// </para>
    /// </summary>
    internal static class Program
    {
        /// <summary>Python 原版注册表里每个型钢类型的字段顺序（界面只显示这些）。</summary>
        private static readonly Dictionary<string, string[]> Expected =
            new Dictionary<string, string[]>(StringComparer.Ordinal)
        {
            { "parallel_channel", new string[] { "H", "B", "tw", "tf", "r", "Z0" } },
            { "ordinary_ibeam", new string[] { "H", "B", "tw", "tf", "r1", "r2", "A", "mass" } },
            { "hot_rolled_h", new string[] { "H", "B", "t1", "t2", "r", "area", "mass" } },
            { "tapered_channel", new string[] { "H", "B", "tw", "tf", "r1", "r2", "area", "mass", "Z0_cm" } },
            { "equal_angle", new string[] { "B", "t", "r1", "r2", "area", "mass", "Z0_cm" } },
            { "unequal_angle", new string[] { "BL", "BS", "t", "r1", "r2", "area", "mass", "X0_cm", "Y0_cm" } },
            { "hk_section", new string[] { "H", "B", "t1", "t2", "r", "area", "mass" } },
        };

        /// <summary>允许出现在界面上的单位。</summary>
        private static readonly string[] Units = { "mm", "cm", "cm²", "kg/m" };

        private static readonly Regex Cjk = new Regex("[\u4e00-\u9fff]");

        private static void True(bool value, string label)
        { if (!value) throw new Exception(label); }

        private static void Main()
        {
            FamilyData[] families = RuntimeData.Families;
            True(families.Length == Expected.Count,
                "profiles.bin 里的型钢类型数（" + families.Length + "）与显示表不一致（" + Expected.Count + "）。");

            int fieldCount = 0;
            foreach (FamilyData family in families)
            {
                True(SteelSectionCatalog.FamilyIds.Contains(family.Id),
                    "显示表缺少型钢类型：" + family.Id + "（" + family.Label + "）——界面会一条参数都不显示。");

                SectionField[] fields = SteelSectionCatalog.FieldsFor(family.Id);
                string[] expected = Expected[family.Id];
                True(fields.Length == expected.Length,
                    family.Id + " 的显示字段数 " + fields.Length + " ≠ " + expected.Length);

                for (int i = 0; i < expected.Length; i++)
                {
                    SectionField field = fields[i];
                    True(field.Key == expected[i],
                        family.Id + " 第 " + (i + 1) + " 个字段应为 " + expected[i] + "，实际 " + field.Key);
                    True(Cjk.IsMatch(field.Label),
                        family.Id + "." + field.Key + " 的中文名里没有汉字（界面不允许出现纯英文标签）：" + field.Label);
                    bool unitOk = false;
                    foreach (string unit in Units) if (unit == field.Unit) unitOk = true;
                    True(unitOk, family.Id + "." + field.Key + " 的单位不在允许列表里：" + field.Unit);

                    // 每个规格都必须有该字段，否则界面上会静默少一行。
                    foreach (ProfileData profile in family.Profiles)
                    {
                        True(profile.Dimensions.ContainsKey(field.Key),
                            family.Label + " " + profile.Name + " 缺少字段 " + field.Key);
                    }
                    fieldCount++;
                }
            }

            // 未登记的型钢类型必须返回空表，绝不能把原始英文键漏到界面上。
            True(SteelSectionCatalog.FieldsFor("no_such_family").Length == 0, "未登记类型应返回空表");
            True(SteelSectionCatalog.FieldsFor(null).Length == 0, "空类型应返回空表");

            Console.WriteLine("型钢截面参数表：" + families.Length + " 个类型 / " + fieldCount
                + " 个字段与 Python 原版注册表一致，中文名与单位合法，数据字段齐备。");
        }
    }
}
