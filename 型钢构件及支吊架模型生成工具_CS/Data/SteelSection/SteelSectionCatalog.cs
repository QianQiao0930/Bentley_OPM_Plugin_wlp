using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>截面参数表的一行：数据键 + 界面显示用中文名 + 单位。</summary>
    internal sealed class SectionField
    {
        internal readonly string Key;
        internal readonly string Label;
        internal readonly string Unit;

        internal SectionField(string key, string label, string unit)
        {
            Key = key;
            Label = label;
            Unit = unit;
        }
    }

    /// <summary>
    /// 截面参数显示表：显示哪些字段、显示成什么中文名、单位是什么。
    /// <para>
    /// 与 Python 原版 <c>型钢截面生成器/steel_sections/steel_registry.py</c> 每个家族的
    /// <c>fields</c> 逐项一致 —— 原版**只显示这份精选字段**。C# 侧曾把 profiles.bin 里的
    /// 全部原始键直接铺到界面（<c>mass</c> / <c>area</c> / <c>surface_area</c> / <c>Ix</c> …），
    /// 于是"03 当前截面参数"里出现英文、而且比原版多出一倍行数。
    /// </para>
    /// ⚠️ 界面只认中文：没有登记在本表里的字段一律不显示，不要让英文键漏到界面上。
    /// </summary>
    internal static class SteelSectionCatalog
    {
        private static readonly SectionField[] Empty = new SectionField[0];

        private static readonly Dictionary<string, SectionField[]> Fields =
            new Dictionary<string, SectionField[]>(StringComparer.Ordinal)
        {
            { "parallel_channel", new SectionField[]
                {
                    new SectionField("H", "高度 H", "mm"),
                    new SectionField("B", "宽度 B", "mm"),
                    new SectionField("tw", "腹板厚度 tw", "mm"),
                    new SectionField("tf", "翼缘厚度 tf", "mm"),
                    new SectionField("r", "根部圆角 r", "mm"),
                    new SectionField("Z0", "重心距 Z0", "mm"),
                } },
            { "ordinary_ibeam", new SectionField[]
                {
                    new SectionField("H", "高度 H", "mm"),
                    new SectionField("B", "宽度 B", "mm"),
                    new SectionField("tw", "腹板厚度 tw", "mm"),
                    new SectionField("tf", "翼缘平均厚度 tf", "mm"),
                    new SectionField("r1", "腹板圆角 r1", "mm"),
                    new SectionField("r2", "翼缘端圆角 r2", "mm"),
                    new SectionField("A", "截面面积 A", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                } },
            { "hot_rolled_h", new SectionField[]
                {
                    new SectionField("H", "高度 H", "mm"),
                    new SectionField("B", "宽度 B", "mm"),
                    new SectionField("t1", "腹板厚度 t1", "mm"),
                    new SectionField("t2", "翼缘厚度 t2", "mm"),
                    new SectionField("r", "根部圆角 r", "mm"),
                    new SectionField("area", "截面面积", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                } },
            { "tapered_channel", new SectionField[]
                {
                    new SectionField("H", "高度 H", "mm"),
                    new SectionField("B", "宽度 B", "mm"),
                    new SectionField("tw", "腹板厚度 tw", "mm"),
                    new SectionField("tf", "翼缘平均厚度 tf", "mm"),
                    new SectionField("r1", "腹板圆角 r1", "mm"),
                    new SectionField("r2", "翼缘端圆角 r2", "mm"),
                    new SectionField("area", "截面面积", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                    new SectionField("Z0_cm", "重心距 Z0", "cm"),
                } },
            { "equal_angle", new SectionField[]
                {
                    new SectionField("B", "边长 B", "mm"),
                    new SectionField("t", "厚度 t", "mm"),
                    new SectionField("r1", "内圆角 r1", "mm"),
                    new SectionField("r2", "端部圆角 r2", "mm"),
                    new SectionField("area", "截面面积", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                    new SectionField("Z0_cm", "重心距 Z′0", "cm"),
                } },
            { "unequal_angle", new SectionField[]
                {
                    new SectionField("BL", "长边 BL", "mm"),
                    new SectionField("BS", "短边 BS", "mm"),
                    new SectionField("t", "厚度 t", "mm"),
                    new SectionField("r1", "内圆角 r1", "mm"),
                    new SectionField("r2", "端部圆角 r2", "mm"),
                    new SectionField("area", "截面面积", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                    new SectionField("X0_cm", "重心距 X0", "cm"),
                    new SectionField("Y0_cm", "重心距 Y0", "cm"),
                } },
            { "hk_section", new SectionField[]
                {
                    new SectionField("H", "高度 H", "mm"),
                    new SectionField("B", "宽度 B", "mm"),
                    new SectionField("t1", "腹板厚度 t1", "mm"),
                    new SectionField("t2", "翼缘厚度 t2", "mm"),
                    new SectionField("r", "根部圆角 r", "mm"),
                    new SectionField("area", "截面面积", "cm²"),
                    new SectionField("mass", "理论重量", "kg/m"),
                } },
        };

        /// <summary>某个型钢类型要显示的参数字段；未登记的类型返回空表（宁可少显示，也不漏英文键）。</summary>
        internal static SectionField[] FieldsFor(string familyId)
        {
            if (string.IsNullOrEmpty(familyId)) return Empty;
            SectionField[] fields;
            return Fields.TryGetValue(familyId, out fields) ? fields : Empty;
        }

        /// <summary>表中登记过的型钢类型编号（供检查工程比对）。</summary>
        internal static ICollection<string> FamilyIds
        {
            get { return Fields.Keys; }
        }
    }
}
