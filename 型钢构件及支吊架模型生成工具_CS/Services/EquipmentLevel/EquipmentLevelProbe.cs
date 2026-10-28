using System;
using System.Collections;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// <c>STEELPROBE EQPROBE</c>：对选中元素做一次<b>只读</b>探测，把"能不能拿到它的图形图元"
    /// 这件事的每一条通道都试一遍并写进日志。
    /// <para>
    /// 存在的意义：<c>Element.GetChildren()</c> 在 OpenPlant 的设备元素上返回 0，
    /// 而"按父元素扫描模型"也没找到——必须先用实测数据判断到底是
    /// "单元根本没有暴露子元素"、"子元素不在这个模型里"，还是"枚举接口拿到的是被裁剪过的集合"，
    /// 再决定走"原地改子元素"还是"打散→改→重生成"。绝不靠猜。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelProbe
    {
        /// <summary>执行探测；结果写日志，状态栏只给一句摘要。</summary>
        internal static void Run()
        {
            try
            {
                if (!LicenseService.IsActivated)
                {
                    SetStatus("请先激活软件。");
                    return;
                }
                Probe();
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("探测异常：" + ex);
                SetStatus("探测失败：" + ex.Message + "（详见 " + EquipmentLevelLog.FilePath + "）");
            }
        }

        private static void Probe()
        {
            DgnModel model = EquipmentLevelReader.ActiveModel();
            EquipmentLevelLog.Write("==== EQPROBE 开始 ====");

            // 1. 模型层面：三种元素集合各自有多少。
            LogModelCounts(model);

            if (!SelectionSetManager.IsActive() || SelectionSetManager.NumSelected() == 0)
            {
                SetStatus("请先选中一个元素再探测。");
                EquipmentLevelLog.Write("没有选中元素，结束。");
                return;
            }

            uint count = SelectionSetManager.NumSelected();
            var ids = new List<ulong>();
            for (uint i = 0; i < count; i++)
            {
                Element selected = null;
                DgnModelRef modelRef = null;
                if (SelectionSetManager.GetElement(i, ref selected, ref modelRef) != StatusInt.Success) continue;
                if (selected == null) continue;
                ids.Add(selected.ElementId);
            }

            foreach (ulong rawId in ids) ProbeElement(model, rawId);

            EquipmentLevelLog.Write("==== EQPROBE 结束 ====");
            SetStatus("探测完成：选中 " + ids.Count + " 个元素，详细结果见 " + EquipmentLevelLog.FilePath);
        }

        private static void LogModelCounts(DgnModel model)
        {
            try
            {
                EquipmentLevelLog.Write("模型：" + SafeModelName(model));
                EquipmentLevelLog.Write("  GetElementCount(All)=" + SafeCount(model, DgnModelSections.All) +
                    "  GraphicElements=" + SafeCount(model, DgnModelSections.GraphicElements) +
                    "  ControlElements=" + SafeCount(model, DgnModelSections.ControlElements) +
                    "  Model=" + SafeCount(model, DgnModelSections.Model));
                EquipmentLevelLog.Write("  GetElements()=" + CountOf(model.GetElements()) +
                    "  GetGraphicElements()=" + CountOf(model.GetGraphicElements()) +
                    "  GetControlElements()=" + CountOf(model.GetControlElements()));
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  读取模型统计失败：" + ex.Message);
            }
        }

        private static void ProbeElement(DgnModel model, ulong rawId)
        {
            ulong id = rawId;
            EquipmentLevelLog.Write("---- 元素 " + rawId + " ----");
            Element element = model.FindElementById(new ElementId(ref id));
            if (element == null || !element.IsValid)
            {
                EquipmentLevelLog.Write("  元素不存在");
                return;
            }

            EquipmentLevelLog.Write("  TypeName=" + SafeTypeName(element) +
                "  描述=" + SafeDescription(element));
            EquipmentLevelLog.Write("  IsComplexComponent=" + SafeBool(delegate { return element.IsComplexComponent; }) +
                "  IsGraphics=" + SafeBool(delegate { return element.IsGraphics; }) +
                "  IsPersistent=" + SafeBool(delegate { return element.IsPersistent; }));
            EquipmentLevelLog.Write("  ParentElement=" + SafeParentId(element));

            // 通道一：ExposeChildren + GetChildren。
            try
            {
                bool exposed = element.ExposeChildren(ExposeChildrenReason.Query);
                EquipmentLevelLog.Write("  ExposeChildren(Query)=" + exposed);
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  ExposeChildren 异常：" + ex.Message);
            }
            LogChildren(element, "GetChildren");

            // 通道二：依赖元素。
            try
            {
                object dependants = element.GetDependants();
                EquipmentLevelLog.Write("  GetDependants()=" + (dependants == null ? "null" : CountOf(dependants).ToString()));
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  GetDependants 异常：" + ex.Message);
            }

            // 通道三：COM 元素。
            try
            {
                var com = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference
                    .GetElementByID64(checked((long)rawId));
                if (com == null)
                {
                    EquipmentLevelLog.Write("  COM 元素：取不到");
                }
                else
                {
                    string typeText;
                    try { typeText = com.Type.ToString(); }
                    catch { typeText = "未知"; }
                    string cellText;
                    try { cellText = com.AsCellElement() == null ? "否" : "是"; }
                    catch { cellText = "异常"; }
                    EquipmentLevelLog.Write("  COM 元素：Type=" + typeText + "  AsCellElement=" + cellText);
                }
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  COM 元素异常：" + ex.Message);
            }

            // 通道四：在所有模型里找"父元素是它"的元素。
            try
            {
                FindAcrossModels(element);
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  跨模型查找异常：" + ex.Message);
            }
        }

        private static void LogChildren(Element element, string label)
        {
            try
            {
                object children = element.GetChildren();
                if (children == null)
                {
                    EquipmentLevelLog.Write("  " + label + "=null");
                    return;
                }
                EquipmentLevelLog.Write("  " + label + " 返回类型=" + children.GetType().FullName);
                int count = 0;
                var enumerable = children as IEnumerable;
                if (enumerable == null)
                {
                    EquipmentLevelLog.Write("  " + label + "：不可枚举（不是 IEnumerable）");
                    return;
                }
                foreach (object item in enumerable)
                {
                    count++;
                    var child = item as Element;
                    if (child == null)
                    {
                        EquipmentLevelLog.Write("    子项 " + count + " 不是 Element：" + (item == null ? "null" : item.GetType().FullName));
                        continue;
                    }
                    EquipmentLevelLog.Write("    子项 " + count + "：" + SafeTypeName(child) + " id=" + SafeId(child) +
                        " 层=" + SafeLevelName(child));
                }
                EquipmentLevelLog.Write("  " + label + " 计数=" + count);
            }
            catch (Exception ex)
            {
                EquipmentLevelLog.Write("  " + label + " 异常：" + ex.Message);
            }
        }

        /// <summary>遍历当前文件的所有模型，找父元素 ID 等于该元素的后代。</summary>
        private static void FindAcrossModels(Element element)
        {
            ulong targetId = SafeId(element);
            DgnModel elementModel = element.DgnModel;
            var file = elementModel == null ? null : elementModel.GetDgnFile();
            if (file == null)
            {
                EquipmentLevelLog.Write("  跨模型查找：拿不到 DgnFile");
                return;
            }
            int models = 0;
            int matches = 0;
            foreach (DgnModel candidate in file.GetLoadedModelsCollection())
            {
                models++;
                int modelMatches = 0;
                foreach (var scan in new object[] { candidate.GetElements(), candidate.GetGraphicElements() })
                {
                    var enumerable = scan as IEnumerable;
                    if (enumerable == null) continue;
                    foreach (object item in enumerable)
                    {
                        var child = item as Element;
                        if (child == null) continue;
                        if (ParentIdOf(child) != targetId) continue;
                        modelMatches++;
                        matches++;
                        EquipmentLevelLog.Write("    命中：" + SafeModelName(candidate) + " / " + SafeTypeName(child) +
                            " id=" + SafeId(child));
                    }
                }
                if (modelMatches > 0)
                    EquipmentLevelLog.Write("  模型 " + SafeModelName(candidate) + "：命中 " + modelMatches + " 个");
            }
            EquipmentLevelLog.Write("  跨模型查找：共 " + models + " 个模型，命中 " + matches + " 个");
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

        private static int CountOf(object collection)
        {
            if (collection == null) return -1;
            var enumerable = collection as IEnumerable;
            if (enumerable == null) return -2;
            int count = 0;
            foreach (object item in enumerable) count++;
            return count;
        }

        private static int SafeCount(DgnModel model, DgnModelSections section)
        {
            try { return checked((int)model.GetElementCount(section)); }
            catch { return -1; }
        }

        private static string SafeModelName(DgnModel model)
        {
            try { return model.GetModelInfo().Name; }
            catch { return "未知模型"; }
        }

        private static string SafeTypeName(Element element)
        {
            try { return element.TypeName; }
            catch { return "未知类型"; }
        }

        private static string SafeDescription(Element element)
        {
            try { return element.Description; }
            catch { return ""; }
        }

        private static string SafeLevelName(Element element)
        {
            try { return ((uint)element.LevelId).ToString(); }
            catch { return "?"; }
        }

        private static ulong SafeId(Element element)
        {
            try { return element.ElementId; }
            catch { return 0; }
        }

        private static string SafeParentId(Element element)
        {
            try
            {
                Element parent = element.ParentElement;
                return parent == null ? "（无）" : parent.ElementId.ToString();
            }
            catch
            {
                return "（读取异常）";
            }
        }

        private static string SafeBool(Func<bool> read)
        {
            try { return read().ToString(); }
            catch { return "读取异常"; }
        }

        private static void SetStatus(string text)
        {
            try { MessageCenter.Instance.StatusMessage = text; }
            catch { }
        }
    }
}
