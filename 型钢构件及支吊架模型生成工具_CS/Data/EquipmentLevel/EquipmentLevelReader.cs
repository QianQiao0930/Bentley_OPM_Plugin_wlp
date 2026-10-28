using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 读取"设备"及其图形子元素。<b>只读</b>，不创建、不修改任何模型元素。
    /// <para>
    /// 判定设备只用一条硬判据：元素是普通单元（<c>CellHeaderElement.IsNormalCell</c>），
    /// 且它的 EC 实例上存在属性 <c>ElementType</c>，值为 <c>Equipment</c>
    /// （即 <c>DgnElementSchema.NormalCellElement.ElementType</c>）。
    /// 判不出来就当"不是设备"，宁可拒绝也不猜。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelReader
    {
        /// <summary>EC 属性名（DgnElementSchema.NormalCellElement.ElementType）。</summary>
        internal const string ElementTypeProperty = "ElementType";

        /// <summary>设备在该属性上的取值。</summary>
        internal const string EquipmentValue = "Equipment";

        /// <summary>递归展开的最大层数，防止异常结构导致无限下钻。</summary>
        internal const int MaxDepth = 8;

        /// <summary>单台设备最多展开的图元数，超限直接拒绝。</summary>
        internal const int MaxElements = 20000;

        /// <summary>取活动模型；没有活动模型时抛中文异常。</summary>
        internal static DgnModel ActiveModel()
        {
            DgnModel model = Session.Instance.GetActiveDgnModel();
            if (model == null) throw new InvalidOperationException("没有活动模型，不能修改设备图层。");
            return model;
        }

        /// <summary>判定一个选中元素是否可以参与改层。</summary>
        internal static EquipmentLevelEntry Classify(DgnModelRef modelRef, ulong id)
        {
            var entry = new EquipmentLevelEntry { ElementId = id };
            DgnModel model = ComponentPropertyReader.ResolveModel(modelRef);
            if (model == null)
            {
                entry.Verdict = EquipmentLevelVerdict.Missing;
                entry.Reason = "没有可用的模型";
                return entry;
            }

            ElementId elementId = new ElementId(ref id);
            Element element = model.FindElementById(elementId);
            if (element == null || !element.IsValid)
            {
                entry.Verdict = EquipmentLevelVerdict.Missing;
                entry.Reason = "元素已不存在";
                return entry;
            }

            entry.Name = SafeName(element);
            if (LocatedElement.IsReference(modelRef))
            {
                entry.Verdict = EquipmentLevelVerdict.FromReference;
                entry.Reason = "元素在参考文件里，不能在活动模型里修改";
                return entry;
            }

            // 先按 EC 判据认设备：ElementType = Equipment。
            // 这一步不依赖单元的子类，避免普通单元被包装成 Type2Element 之类时被误拒。
            bool isEquipment;
            string ecDetail;
            try
            {
                isEquipment = HasEquipmentElementType(element, out ecDetail);
            }
            catch (Exception ex)
            {
                isEquipment = false;
                ecDetail = "读取 EC 异常：" + ex.Message;
            }
            if (!isEquipment)
            {
                entry.Verdict = EquipmentLevelVerdict.NotEquipment;
                entry.Reason = string.IsNullOrEmpty(ecDetail) ? "EC 属性 ElementType 不是 Equipment" : ecDetail;
                return entry;
            }

            // 是设备，再确认它是"可以安全改子元素的普通单元"。
            CellHeaderElement cell = element as CellHeaderElement;
            if (cell == null && !(element is Type2Element))
            {
                entry.Verdict = EquipmentLevelVerdict.NotACell;
                entry.Reason = "有设备属性，但不是单元（" + SafeTypeName(element) + "）";
                return entry;
            }
            if (cell != null && !cell.IsNormalCell)
            {
                entry.Verdict = EquipmentLevelVerdict.UnsupportedCell;
                entry.Reason = "是共享单元或参数化单元，本版本不处理";
                return entry;
            }

            entry.Verdict = EquipmentLevelVerdict.Equipment;
            return entry;
        }

        /// <summary>
        /// 判断元素上是否存在 <c>ElementType = Equipment</c> 的 EC 属性。
        /// <para>
        /// 按<b>属性名</b>匹配再取值，而不是直接写访问字符串：
        /// <c>DgnElementSchema.NormalCellElement.ElementType</c> 可能是继承来的属性，
        /// 直接 <c>instance["ElementType"]</c> 不一定取得到；这里遍历
        /// <c>ClassDefinition.Properties(true)</c>（含继承）逐个比对。
        /// </para>
        /// </summary>
        internal static bool HasEquipmentElementType(Element element, out string detail)
        {
            detail = null;
            var found = new List<string>();
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                foreach (IDgnECInstance instance in instances)
                {
                    string className;
                    try { className = instance.ClassDefinition.Name; }
                    catch { className = "未知类"; }
                    found.Add(className);

                    try
                    {
                        foreach (var property in instance.ClassDefinition.Properties(true))
                        {
                            string name = property.Name;
                            if (name == null) continue;
                            // 本体名就是 ElementType，或继承访问串以 ".ElementType" 结尾，两者都认。
                            if (!name.Equals(ElementTypeProperty, StringComparison.OrdinalIgnoreCase) &&
                                !name.EndsWith("." + ElementTypeProperty, StringComparison.OrdinalIgnoreCase)) continue;
                            string value = ReadTextProperty(instance, name);
                            if (value == null) continue;
                            if (!value.Trim().Equals(EquipmentValue, StringComparison.OrdinalIgnoreCase)) continue;
                            detail = "ElementType = " + value.Trim() + "（类 " + className + "）";
                            return true;
                        }
                    }
                    catch (Exception ex)
                    {
                        EquipmentLevelLog.Write("读取 EC 属性失败（类 " + className + "）：" + ex.Message);
                    }
                }
            }
            detail = found.Count == 0
                ? "元素上没有找到任何 EC 实例"
                : "已找到的 EC 类：" + string.Join("、", found.ToArray()) + "，都不含 ElementType = Equipment";
            return false;
        }

        /// <summary>读一个 EC 实例上的文字属性；属性不存在或读不到时返回 null。</summary>
        private static string ReadTextProperty(IDgnECInstance instance, string name)
        {
            try
            {
                IECPropertyValue value = instance[name];
                if (value == null || value.IsNull) return null;
                if (value.IsArray || value.IsStruct) return null;
                object native = value.NativeValue;
                return native == null ? value.XmlStringValue : Convert.ToString(native, CultureInfo.InvariantCulture);
            }
            catch
            {
                // 该类没有这个属性是正常情况，继续看下一个实例。
                return null;
            }
        }

        private static string SafeName(Element element)
        {
            try
            {
                var cell = element as CellHeaderElement;
                string name = cell == null ? null : cell.CellName;
                if (!string.IsNullOrWhiteSpace(name)) return name;
                string description = element.Description;
                return string.IsNullOrWhiteSpace(description) ? SafeTypeName(element) : description;
            }
            catch
            {
                return "（未命名）";
            }
        }

        private static string SafeTypeName(Element element)
        {
            try { return element.TypeName; }
            catch { return "未知类型"; }
        }
    }
}
