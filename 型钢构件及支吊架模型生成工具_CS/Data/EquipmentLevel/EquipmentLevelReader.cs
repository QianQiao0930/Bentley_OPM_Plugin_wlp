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

            CellHeaderElement cell = element as CellHeaderElement;
            if (cell == null)
            {
                entry.Verdict = EquipmentLevelVerdict.NotACell;
                entry.Reason = "不是单元（" + SafeTypeName(element) + "）";
                return entry;
            }
            if (!cell.IsNormalCell)
            {
                entry.Verdict = EquipmentLevelVerdict.UnsupportedCell;
                entry.Reason = "是共享单元或参数化单元，本版本不处理";
                return entry;
            }

            bool isEquipment;
            string error;
            try
            {
                isEquipment = HasEquipmentElementType(element, out error);
            }
            catch (Exception ex)
            {
                isEquipment = false;
                error = ex.Message;
            }
            if (!isEquipment)
            {
                entry.Verdict = EquipmentLevelVerdict.NotEquipment;
                entry.Reason = string.IsNullOrEmpty(error)
                    ? "EC 属性 ElementType 不是 Equipment"
                    : "读取 EC 属性失败：" + error;
                return entry;
            }

            entry.Verdict = EquipmentLevelVerdict.Equipment;
            return entry;
        }

        /// <summary>判断元素上是否存在 ElementType=Equipment 的 EC 属性。</summary>
        internal static bool HasEquipmentElementType(Element element, out string error)
        {
            error = null;
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                foreach (IDgnECInstance instance in instances)
                {
                    string value = ReadTextProperty(instance, ElementTypeProperty);
                    if (value == null) continue;
                    if (value.Trim().Equals(EquipmentValue, StringComparison.OrdinalIgnoreCase)) return true;
                }
            }
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

        /// <summary>
        /// 取元素的直接子元素快照。先整体复制到列表再处理，
        /// 避免"边枚举边替换"把枚举器搞坏。
        /// </summary>
        internal static List<Element> ReadChildren(Element parent)
        {
            var list = new List<Element>();
            if (parent == null) return list;
            try
            {
                object children = parent.GetChildren();
                if (children == null) return list;
                var enumerable = children as System.Collections.IEnumerable;
                if (enumerable == null) return list;
                foreach (object item in enumerable)
                {
                    Element child = item as Element;
                    if (child == null || !child.IsValid) continue;
                    list.Add(child);
                }
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("读取子元素失败：" + ex.Message);
            }
            return list;
        }

        /// <summary>递归收集全部后代的快照（只读用途）。</summary>
        internal static void CollectDescendants(Element parent, List<Element> output, int depth)
        {
            if (parent == null || depth > MaxDepth || output.Count >= MaxElements) return;
            var children = ReadChildren(parent);
            foreach (var child in children)
            {
                if (output.Count >= MaxElements) return;
                output.Add(child);
                CollectDescendants(child, output, depth + 1);
            }
        }

        /// <summary>递归统计后代数量。</summary>
        internal static int CountDescendants(Element parent, int depth)
        {
            if (parent == null || depth > MaxDepth) return 0;
            int count = 0;
            var children = ReadChildren(parent);
            foreach (var child in children)
            {
                count++;
                count += CountDescendants(child, depth + 1);
                if (count >= MaxElements) return count;
            }
            return count;
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
