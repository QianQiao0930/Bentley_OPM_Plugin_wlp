using System;
using System.Collections.Generic;
using System.Text;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>
    /// 按 COM 单元/复杂元素的实际包含关系读取设备。依赖关系和空间包含不作为所有权证据。
    /// 每次 Capture 都重新读取宿主，快照仅保存数值，不能用旧 COM 句柄证明写入成功。
    /// </summary>
    internal sealed class EquipmentLevelTree
    {
        internal const int MaxDepth = 64;
        internal const int MaxElements = 20000;
        private readonly Action<int> progress;

        internal EquipmentLevelTree(Action<int> progress = null) { this.progress = progress; }

        internal EquipmentLevelSnapshot Capture(ulong rootId)
        {
            var root = Find(rootId);
            if (!root.IsCellElement() || root.IsSharedCellElement())
                throw new InvalidOperationException("设备 " + rootId + " 不是可遍历的普通单元。");
            var snapshot = new EquipmentLevelSnapshot { RootId = rootId };
            var visited = new HashSet<ulong> { rootId };
            var ancestors = new HashSet<ulong> { rootId };
            ReadChildren(root, rootId, 0, snapshot, visited, ancestors);
            return snapshot;
        }

        internal static Com.Element Find(ulong id)
        {
            var app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if (app == null) throw new InvalidOperationException("OPM COM 应用对象不可用。");
            var active = app.ActiveModelReference;
            if (active == null) throw new InvalidOperationException("OPM COM 活动模型不可用。");
            var element = active.GetElementByID64(checked((long)id));
            if (element == null) throw new InvalidOperationException("COM 取不到图元 " + id + "。");
            if (checked((ulong)element.ID64) != id)
                throw new InvalidOperationException("COM 按 ID 查找 " + id + " 实际返回 " + Describe(element) + "，不能作为目标写入。");
            return element;
        }

        /// <summary>重新沿快照的包含路径定位，不用模型级按内部件 ID 查找代替组件定位。</summary>
        internal Com.Element Resolve(EquipmentLevelSnapshot snapshot, EquipmentLevelNode target)
        {
            var path = new List<EquipmentLevelNode>();
            var step = target;
            while (true)
            {
                if (path.Count >= MaxDepth) throw new InvalidOperationException("内部件路径超过深度上限。");
                path.Add(step);
                if (step.ParentId == snapshot.RootId) break;
                if (!snapshot.Nodes.TryGetValue(step.ParentId, out step))
                    throw new InvalidOperationException("图元 " + target.Id + " 的计划父路径不完整。");
            }
            path.Reverse();
            var current = Find(snapshot.RootId);
            if (!current.IsCellElement() || current.IsSharedCellElement() || current.IsSmartSolidElement)
                throw new InvalidOperationException("设备根 " + snapshot.RootId + " 不再是普通单元。");
            foreach (var expected in path)
            {
                ulong parentId = checked((ulong)current.ID64);
                if (parentId != expected.ParentId)
                    throw new InvalidOperationException("图元 " + expected.Id + " 的实际父路径变化。");
                if (current.IsLocked) throw new InvalidOperationException("父单元 " + parentId + " 已锁定。");
                var children = LogicalChildren(current, parentId);
                if (children == null) throw new InvalidOperationException("父图元 " + parentId + " 不再允许展开设备组件。");
                Com.Element found = null;
                int enumerated = 0;
                while (children.MoveNext())
                {
                    if (++enumerated > MaxElements) throw new InvalidOperationException("定位内部件时枚举超过上限。");
                    var child = children.Current;
                    if (child == null) throw new InvalidOperationException("父图元 " + parentId + " 含不可读内部件。");
                    if (checked((ulong)child.ID64) != expected.Id) continue;
                    found = child;
                    break;
                }
                if (found == null)
                    throw new InvalidOperationException("设备 " + snapshot.RootId + " 的父单元 " + parentId +
                        " 中找不到计划内部件 " + expected.Id + "，拒绝改写其他对象。");
                RequireIdentity(expected, found);
                current = found;
            }
            return current;
        }

        internal static void RequireIdentity(EquipmentLevelNode expected, Com.Element actual)
        {
            if (checked((ulong)actual.ID64) != expected.Id || actual.Type.ToString() != expected.Type ||
                actual.IsSharedCellElement() != expected.IsSharedInstance || actual.IsSmartSolidElement != expected.IsAtomicSolid ||
                actual.IsCellElement() != expected.IsCell || actual.IsGraphical != expected.IsGraphic)
                throw new InvalidOperationException("图元身份不一致：预期 id=" + expected.Id + " 类型=" + expected.Type +
                    " 共享实例=" + expected.IsSharedInstance + " 智能实体=" + expected.IsAtomicSolid +
                    " 普通单元=" + expected.IsCell + " 图形=" + expected.IsGraphic +
                    "；实际 " + Describe(actual) + "。");
            if (expected.IsSharedInstance)
            {
                var shared = actual.AsSharedCellElement();
                if (shared == null || shared.Name != expected.SharedName)
                    throw new InvalidOperationException("共享实例 " + expected.Id + " 的定义引用不一致。");
            }
        }

        private static string Describe(Com.Element element)
        {
            return "id=" + element.ID64 + " 类型=" + element.Type + " 共享实例=" + element.IsSharedCellElement() +
                " 智能实体=" + element.IsSmartSolidElement + " 普通单元=" + element.IsCellElement() + " 图形=" + element.IsGraphical;
        }

        internal static void LogModelLookup(EquipmentLevelSnapshot snapshot)
        {
            // 仅诊断每台设备的首个图形，不将模型级查找结果用于内部件写入。
            foreach (var node in snapshot.Nodes.Values)
            {
                if (!node.RequiresAppearance) continue;
                try
                {
                    var actual = Find(node.Id);
                    RequireIdentity(node, actual);
                    EquipmentLevelLog.Write("寻址对照：设备 " + snapshot.RootId + "，模型查找与包含路径的身份一致：" + Describe(actual));
                }
                catch (Exception ex)
                {
                    EquipmentLevelLog.Write("寻址对照（仅诊断，写入使用包含路径）：设备 " + snapshot.RootId +
                        "，内部件 " + node.Id + "：" + ex.Message);
                }
                break;
            }
        }

        private bool ReadChildren(Com.Element parent, ulong parentId, int depth,
            EquipmentLevelSnapshot snapshot, HashSet<ulong> visited, HashSet<ulong> ancestors)
        {
            try { return ReadChildrenCore(parent, parentId, depth, snapshot, visited, ancestors); }
            catch (Exception ex)
            {
                throw new InvalidOperationException("展开图元 " + parentId + " 的内部件失败：" + ex.Message, ex);
            }
        }

        private bool ReadChildrenCore(Com.Element parent, ulong parentId, int depth,
            EquipmentLevelSnapshot snapshot, HashSet<ulong> visited, HashSet<ulong> ancestors)
        {
            var children = LogicalChildren(parent, parentId);
            if (children == null) return false;

            bool hasChildren = false;
            int enumerated = 0;
            while (children.MoveNext())
            {
                hasChildren = true;
                if (++enumerated > MaxElements)
                    throw new InvalidOperationException("图元 " + parentId + " 枚举超过上限，未修改。");
                if (depth >= MaxDepth)
                    throw new InvalidOperationException("设备嵌套超过 " + MaxDepth + " 层，未修改。");
                var element = children.Current;
                if (element == null) throw new InvalidOperationException("图元 " + parentId + " 含无法读取的内部件。");
                ulong id = checked((ulong)element.ID64);
                if (id == 0) throw new InvalidOperationException("图元 " + parentId + " 含无持久 ID 的内部件。");
                if (ancestors.Contains(id))
                    throw new InvalidOperationException("设备包含关系成环：" + parentId + " → " + id + "。");
                // 某些复杂元素枚举可能重复报告同一内部件，不重复计数或写入。
                if (!visited.Add(id)) continue;
                if (snapshot.Nodes.Count >= MaxElements)
                    throw new InvalidOperationException("设备图元超过 " + MaxElements + " 个，未修改。");

                var node = new EquipmentLevelNode
                {
                    Id = id, ParentId = parentId, Depth = depth + 1,
                    Type = element.Type.ToString(), IsCell = element.IsCellElement(),
                    IsGraphic = element.IsGraphical, IsLocked = element.IsLocked,
                    IsAtomicSolid = element.IsSmartSolidElement,
                    IsSharedInstance = element.IsSharedCellElement()
                };
                if (node.Type == "DgnStoreHeader" || node.Type == "DgnStoreComponent")
                    throw new InvalidOperationException("图元 " + parentId + " 暴露内部存储记录 " + id +
                        "（" + node.Type + "），不能作为普通图形展开或修改。请先核对实体类型。");
                snapshot.Nodes.Add(id, node);
                if (progress != null) progress(snapshot.Nodes.Count);
                ancestors.Add(id);
                node.HasChildren = ReadChildren(element, id, depth + 1, snapshot, visited, ancestors);
                ancestors.Remove(id);
                if (node.IsGraphic) ReadAppearance(element, node);
            }
            return hasChildren;
        }

        private static Com.ElementEnumerator LogicalChildren(Com.Element parent, ulong parentId)
        {
            // 共享单元仅处理实例覆盖；GetSubElements 指向公共定义，不能递归写入。
            if (parent.IsSharedCellElement()) return null;
            // 智能实体也是 type-2/复杂元素，但其 GetSubElements 是内部存储/显示表示，
            // 不是可以逐条 Rewrite 的设备构件。必须在实体边界停止，保持 BRep 整体。
            if (parent.IsSmartSolidElement) return null;
            Com.ElementEnumerator children;
            if (parent.IsCellElement())
            {
                var cell = parent.AsCellElement();
                if (cell == null) throw new InvalidOperationException("图元 " + parentId + " 标记为单元，但 COM AsCellElement 返回空。");
                children = cell.GetSubElements();
            }
            else if (parent.IsComplexStringElement() || parent.IsComplexShapeElement())
            {
                var complex = parent.AsComplexElement();
                if (complex == null) throw new InvalidOperationException("图元 " + parentId + " 标记为复杂元素，但 COM AsComplexElement 返回空。");
                children = complex.GetSubElements();
            }
            else
            {
                if (parent.Type.ToString() == "CellHeader")
                    throw new InvalidOperationException("图元 " + parentId +
                        " 是特殊 CellHeader，但宿主未将其识别为普通单元或 SmartSolid；已拒绝修改其内部表示。");
                return null;
            }
            if (children == null)
                throw new InvalidOperationException("图元 " + parentId + " 的 GetSubElements 返回空，无法确认读取完整。");

            return children;
        }

        private static void ReadAppearance(Com.Element element, EquipmentLevelNode node)
        {
            try
            {
                // 单元头可能没有 Level 对象；必须先判清容器，不能直接解引用。
                var level = element.Level;
                if (level == null)
                    throw new InvalidOperationException("COM Level 返回空。");
                node.LevelId = level.ID;
                node.Color = element.Color;
                if (node.IsSharedInstance)
                {
                    var shared = element.AsSharedCellElement();
                    if (shared == null) throw new InvalidOperationException("COM AsSharedCellElement 返回空。");
                    node.SharedName = shared.Name;
                    node.OverridesComponentLevel = shared.OverridesComponentLevel;
                    node.OverridesComponentColor = shared.OverridesComponentColor;
                }
                node.HasAppearance = true;
            }
            catch (Exception ex)
            {
                string detail = "图元 " + node.Id + "（" + node.Type + "）读取图层/颜色失败：" + ex.Message;
                if (!node.IsContainer) throw new InvalidOperationException(detail, ex);
                // 不可读的容器头不写属性，其内部图形仍必须完整读取并通过双重校验。
                EquipmentLevelLog.Write(detail + "；保留容器头属性，仅处理内部图形。");
            }
        }

        internal static string Format(EquipmentLevelSnapshot snapshot, string title)
        {
            var text = new StringBuilder();
            text.AppendLine("==== " + title + " / COM GetSubElements ====");
            text.AppendLine("设备根 id=" + snapshot.RootId + "（不写根元素）");
            foreach (var node in snapshot.Nodes.Values)
                text.AppendLine("d" + node.Depth + " id=" + node.Id + " parent=" + node.ParentId +
                    " 类型=" + node.Type + " 层=" + (node.HasAppearance ? node.LevelId.ToString() : "不可读/无属性") +
                    " 颜色=" + (node.HasAppearance ? node.Color.ToString() : "不可读/无属性") +
                    " 容器=" + node.IsContainer + " 智能实体=" + node.IsAtomicSolid +
                    " 共享实例=" + node.IsSharedInstance +
                    (node.IsSharedInstance ? " 名称=" + node.SharedName + " 覆盖层=" + node.OverridesComponentLevel +
                        " 覆盖色=" + node.OverridesComponentColor : "") +
                    " 图形=" + node.IsGraphic + " 锁定=" + node.IsLocked);
            text.AppendLine("总计 " + snapshot.Nodes.Count + " 个内部件；不含 GetDependants 或包围盒补集。");
            text.AppendLine("SmartSolid 按一个实体处理，不展开其内部存储记录与显示表示。");
            text.AppendLine("共享单元按一个实例处理，仅修改实例层色覆盖，不展开或修改公共定义。");
            text.AppendLine("写入时从设备根沿此包含路径重新定位组件，并核对实际 ID/类型；不直接按内部件 ID 定位写入对象。");
            return text.ToString();
        }
    }

    /// <summary>一次完整读取的数值快照，不保存 Bentley/COM 元素对象。</summary>
    internal sealed class EquipmentLevelSnapshot
    {
        internal ulong RootId;
        internal readonly Dictionary<ulong, EquipmentLevelNode> Nodes = new Dictionary<ulong, EquipmentLevelNode>();
    }

    internal sealed class EquipmentLevelNode
    {
        internal ulong Id;
        internal ulong ParentId;
        internal int Depth;
        internal string Type;
        internal int LevelId;
        internal int Color;
        internal bool IsGraphic;
        internal bool IsCell;
        internal bool IsAtomicSolid;
        internal bool IsSharedInstance;
        internal string SharedName;
        internal bool OverridesComponentLevel;
        internal bool OverridesComponentColor;
        internal bool IsLocked;
        internal bool HasChildren;
        internal bool HasAppearance;
        // 单元头可以不接受属性；复杂链/复杂形头本身仍属于需要校验的图形。
        internal bool IsContainer { get { return IsCell && HasChildren && !IsSharedInstance; } }
        internal bool RequiresAppearance { get { return IsGraphic && !IsContainer; } }

        internal bool Matches(int levelId, int byLevelColor)
        {
            return HasAppearance && LevelId == levelId && Color == byLevelColor;
        }
    }
}
