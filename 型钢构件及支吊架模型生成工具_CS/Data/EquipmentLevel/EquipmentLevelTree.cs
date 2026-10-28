using System;
using System.Collections;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>
    /// 设备的图形图元树。<b>只读</b>。
    /// <para>
    /// 取子元素有两条路，按顺序尝试：
    /// </para>
    /// <list type="number">
    /// <item><c>Element.ExposeChildren(Query)</c> + <c>GetChildren()</c>：正常单元的首选路径；</item>
    /// <item>
    /// <b>按父元素扫描整个模型</b>：单元里存的图元在 DGN 文件里本来就是彼此独立的元素，
    /// 只是记录了"父元素"关系。<c>GetChildren()</c> 在 OpenPlant 的设备单元上可能返回空
    /// （单元没有对外暴露子元素），这时遍历模型一次、按 <c>ParentElement</c> 分组就能把它们找回来。
    /// </item>
    /// </list>
    /// <para>
    /// 两条路都取不到时明确报告"取不到子图元"，绝不静默当成"没有图元"。
    /// </para>
    /// </summary>
    internal sealed class EquipmentLevelTree
    {
        /// <summary>递归展开的最大层数，防止异常结构导致无限下钻。</summary>
        internal const int MaxDepth = 8;

        /// <summary>单台设备最多展开的图元数，超限拒绝处理。</summary>
        internal const int MaxElements = 20000;

        private readonly DgnModel model;
        private Dictionary<ulong, List<ulong>> childrenByParent;
        private bool indexBuilt;
        private bool scanFailed;
        private int scannedElements;

        internal EquipmentLevelTree(DgnModel model)
        {
            if (model == null) throw new InvalidOperationException("没有活动模型。");
            this.model = model;
        }

        /// <summary>
        /// 取直接子元素。根元素（设备本身）先走 GetChildren，取不到再看依赖元素；
        /// 更深层的元素只用 GetChildren，最后才扫模型。
        /// </summary>
        internal List<Element> Children(Element parent)
        {
            return Children(parent, false);
        }

        private List<Element> Children(Element parent, bool allowDependants)
        {
            if (parent == null) return new List<Element>();
            var direct = ReadDirectChildren(parent);
            if (direct.Count > 0) return direct;
            if (allowDependants)
            {
                var dependants = ReadDependants(parent);
                if (dependants.Count > 0) return dependants;
            }
            return ReadScannedChildren(parent);
        }

        /// <summary>
        /// 路径二：<c>GetDependants()</c>。
        /// <para>
        /// OpenPlant 的 <c>Equipment</c> 元素上 <c>ExposeChildren</c> 返回 false、
        /// <c>GetChildren()</c> 恒为 0，但 <c>GetDependants()</c> 能给出它的图形图元
        /// （实测一台设备 19 个）。这些元素在模型层面既不是单元子元素、也不在
        /// <c>GetElements()</c> 枚举范围内，只有这条通道能拿到。
        /// </para>
        /// </summary>
        private List<Element> ReadDependants(Element parent)
        {
            var list = new List<Element>();
            try
            {
                object dependants = parent.GetDependants();
                if (dependants == null) return list;
                var enumerable = dependants as IEnumerable;
                if (enumerable == null)
                {
                    EquipmentLevelLog.Write("GetDependants 返回的类型不可枚举：" + dependants.GetType().FullName);
                    return list;
                }
                foreach (object item in enumerable)
                {
                    var element = item as Element;
                    if (element == null || !element.IsValid) continue;
                    list.Add(element);
                }
                if (list.Count > 0)
                    EquipmentLevelLog.Write("改用 GetDependants：找到 " + list.Count + " 个图形图元");
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("读取依赖元素失败：" + ex.Message);
            }
            return list;
        }

        /// <summary>后序遍历全部后代：子元素的子元素先收集，子元素本身随后。</summary>
        internal void CollectPostOrder(Element parent, List<Element> output, int depth)
        {
            var visited = new HashSet<ulong>();
            ulong rootId = SafeId(parent);
            if (rootId != 0) visited.Add(rootId);
            CollectPostOrder(parent, output, depth, visited);
        }

        private void CollectPostOrder(Element parent, List<Element> output, int depth, HashSet<ulong> visited)
        {
            if (parent == null || depth > MaxDepth || output.Count >= MaxElements) return;
            foreach (var child in Children(parent, depth == 0))
            {
                if (output.Count >= MaxElements) return;
                ulong id = SafeId(child);
                // 已访问过就不再下钻：GetDependants 会把祖先一并返回，不去重会指数级膨胀。
                if (id != 0 && !visited.Add(id)) continue;
                CollectPostOrder(child, output, depth + 1, visited);
                if (output.Count >= MaxElements) return;
                output.Add(child);
            }
        }

        /// <summary>无序收集全部后代（校验用）。</summary>
        internal List<Element> Descendants(Element parent)
        {
            var result = new List<Element>();
            var visited = new HashSet<ulong>();
            // 先把根元素自己登记进去：GetDependants 会把祖先一并返回，
            // 不登记根元素就会把它自己当成后代，进而当成"要改层的图元"。
            ulong rootId = SafeId(parent);
            if (rootId != 0) visited.Add(rootId);
            CollectAnyOrder(parent, result, 0, visited);
            if (result.Count >= MaxElements)
                EquipmentLevelLog.Write("遍历达到图元上限 " + MaxElements + "，已截断（可能存在异常结构）");
            return result;
        }

        private void CollectAnyOrder(Element parent, List<Element> output, int depth, HashSet<ulong> visited)
        {
            if (parent == null || depth > MaxDepth || output.Count >= MaxElements) return;
            foreach (var child in Children(parent, depth == 0))
            {
                if (output.Count >= MaxElements) return;
                ulong id = SafeId(child);
                if (id != 0 && !visited.Add(id)) continue;
                output.Add(child);
                CollectAnyOrder(child, output, depth + 1, visited);
            }
        }

        /// <summary>后代数量；取不到子元素时返回 0，由调用方结合诊断信息报告。</summary>
        internal int Count(Element parent)
        {
            return Descendants(parent).Count;
        }

        /// <summary>给"没有子图元"这类结论补一句可判断原因的诊断文字。</summary>
        internal string Diagnose(Element parent)
        {
            if (parent == null) return "元素为空";
            int direct = ReadDirectChildren(parent).Count;
            EnsureIndex();
            List<ulong> scanned;
            childrenByParent.TryGetValue(SafeId(parent), out scanned);
            int scannedCount = scanned == null ? 0 : scanned.Count;
            int dependants = 0;
            try
            {
                object value = parent.GetDependants();
                if (value != null) dependants = CountItems(value);
            }
            catch { }
            return "GetChildren 返回 " + direct + " 个；GetDependants 返回 " + dependants +
                " 个；按父元素扫描模型（" + scannedElements + " 个元素）找到 " + scannedCount + " 个" +
                (scanFailed ? "（扫描失败，见日志）" : "");
        }

        private static int CountItems(object collection)
        {
            var enumerable = collection as IEnumerable;
            if (enumerable == null) return 0;
            int count = 0;
            foreach (object item in enumerable) count++;
            return count;
        }

        /// <summary>路径一：ExposeChildren + GetChildren。</summary>
        private List<Element> ReadDirectChildren(Element parent)
        {
            var list = new List<Element>();
            try
            {
                // 不先 ExposeChildren，GetChildren 在部分元素上会直接返回空。
                try { parent.ExposeChildren(ExposeChildrenReason.Query); }
                catch (Exception ex) { EquipmentLevelLog.Write("ExposeChildren 失败：" + ex.Message); }

                object children = parent.GetChildren();
                if (children == null)
                {
                    EquipmentLevelLog.Write("GetChildren 返回 null（" + SafeTypeName(parent) + "）");
                    return list;
                }
                var enumerable = children as IEnumerable;
                if (enumerable == null)
                {
                    EquipmentLevelLog.Write("GetChildren 返回的类型不可枚举：" + children.GetType().FullName);
                    return list;
                }
                foreach (object item in enumerable)
                {
                    var child = item as Element;
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

        /// <summary>路径二：遍历模型一次，按父元素 ID 分组。</summary>
        private List<Element> ReadScannedChildren(Element parent)
        {
            var list = new List<Element>();
            EnsureIndex();
            List<ulong> ids;
            if (!childrenByParent.TryGetValue(SafeId(parent), out ids) || ids == null) return list;
            foreach (ulong rawId in ids)
            {
                ulong id = rawId;
                try
                {
                    Element child = model.FindElementById(new ElementId(ref id));
                    if (child == null || !child.IsValid) continue;
                    list.Add(child);
                }
                catch (Exception ex)
                {
                    EquipmentLevelLog.Write("按 ID 取子元素失败（" + rawId + "）：" + ex.Message);
                }
            }
            return list;
        }

        private void EnsureIndex()
        {
            if (indexBuilt) return;
            indexBuilt = true;
            childrenByParent = new Dictionary<ulong, List<ulong>>();
            var started = DateTime.UtcNow;
            try
            {
                // 三种集合都扫一遍并去重：GetElements() 可能只给"顶层"元素，
                // 复杂元素/单元内部件常常只有在 GetGraphicElements() 里才拿得到。
                var seen = new Dictionary<ulong, bool>();
                ScanCollection(model.GetElements(), seen, "GetElements");
                ScanCollection(model.GetGraphicElements(), seen, "GetGraphicElements");
                ScanCollection(model.GetControlElements(), seen, "GetControlElements");
                EquipmentLevelLog.Write("模型扫描完成：" + scannedElements + " 个元素，带父元素的 " +
                    childrenByParent.Count + " 组，耗时 " +
                    (DateTime.UtcNow - started).TotalMilliseconds.ToString("F0") + " ms");
            }
            catch (Exception ex)
            {
                scanFailed = true;
                EquipmentLevelLog.Write("模型扫描失败：" + ex.Message);
            }
        }

        /// <summary>把一个元素集合扫进"父元素 → 子元素 ID"索引，按元素 ID 去重。</summary>
        private void ScanCollection(object collection, IDictionary<ulong, bool> seen, string label)
        {
            var enumerable = collection as IEnumerable;
            if (enumerable == null)
            {
                EquipmentLevelLog.Write("  " + label + "：不可枚举（" + (collection == null ? "null" : collection.GetType().Name) + "）");
                return;
            }
            int count = 0;
            int withParent = 0;
            foreach (object item in enumerable)
            {
                var element = item as Element;
                if (element == null || !element.IsValid) continue;
                count++;
                ulong id = SafeId(element);
                if (id != 0)
                {
                    if (seen.ContainsKey(id)) continue;
                    seen[id] = true;
                }
                scannedElements++;
                ulong parentId = ParentIdOf(element);
                if (parentId == 0) continue;
                withParent++;
                List<ulong> list;
                if (!childrenByParent.TryGetValue(parentId, out list))
                {
                    list = new List<ulong>();
                    childrenByParent[parentId] = list;
                }
                list.Add(id);
            }
            EquipmentLevelLog.Write("  " + label + "：枚举 " + count + " 个，其中带父元素 " + withParent + " 个");
        }

        private static ulong ParentIdOf(Element element)
        {
            try
            {
                Element parent = element.ParentElement;
                if (parent == null) return 0;
                return parent.ElementId;
            }
            catch
            {
                return 0;
            }
        }

        private static ulong SafeId(Element element)
        {
            try { return element.ElementId; }
            catch { return 0; }
        }

        private static string SafeTypeName(Element element)
        {
            try { return element.TypeName; }
            catch { return "未知类型"; }
        }
    }
}
