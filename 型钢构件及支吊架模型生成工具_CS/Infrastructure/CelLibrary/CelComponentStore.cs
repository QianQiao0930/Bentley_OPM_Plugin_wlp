using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>仅在新放置根 Cell 上保存独立附加项；不改源库或源单元的既有附加项。</summary>
    internal static class CelComponentStore
    {
        internal const string LibraryName = "SSP_CelLibraryComponents";
        internal const string ItemTypeName = "CelComponent";
        private static readonly string[] TextFields = { "SourceLibrary", "CellName", "Category", "Specification" };

        internal static void Attach(Element element, CelPlacementMetadata source)
        {
            var metadata = source.Copy();
            var file = Session.Instance.GetActiveDgnFile();
            if (file == null || file.IsReadOnly) throw new InvalidOperationException("没有可写的活动 DGN 文件。");
            ItemTypeLibrary library = ItemTypeLibrary.FindByName(LibraryName, file);
            bool changed = library == null;
            if (library == null) library = ItemTypeLibrary.Create(LibraryName, file, false);
            if (library == null) throw new InvalidOperationException("无法创建 CEL 构件附加项库。");
            ItemType type = library.GetItemTypeByName(ItemTypeName);
            if (type == null) { type = library.AddItemType(ItemTypeName, false); changed = true; }
            if (type == null) throw new InvalidOperationException("无法创建 CEL 构件附加项。");
            foreach (string name in TextFields) changed |= EnsureProperty(type, name, CustomProperty.TypeKind.String, "");
            changed |= EnsureProperty(type, "Quantity", CustomProperty.TypeKind.Integer, 1);
            changed |= EnsureProperty(type, "Version", CustomProperty.TypeKind.Integer, 1);
            changed |= EnsureProperty(type, "RotationDegrees", CustomProperty.TypeKind.Double, 0.0);
            if (changed)
            {
                if (!library.Write()) throw new InvalidOperationException("CEL 构件附加项库保存失败。");
                library = ItemTypeLibrary.FindByName(LibraryName, file);
                if (library == null) throw new InvalidOperationException("保存后无法重读 CEL 构件附加项库。");
                type = library.GetItemTypeByName(ItemTypeName);
            }
            if (type == null) throw new InvalidOperationException("保存后无法读取 CEL 构件附加项类型。");
            IDgnECInstance instance = new CustomItemHost(element, false).ApplyCustomItem(type);
            if (instance == null) throw new InvalidOperationException("CEL 构件附加项写入失败。");
            instance["SourceLibrary"].StringValue = metadata.LibraryFileName;
            instance["CellName"].StringValue = metadata.CellName;
            instance["Category"].StringValue = metadata.Category;
            instance["Specification"].StringValue = metadata.Specification;
            instance["Quantity"].IntValue = 1;
            instance["Version"].IntValue = 1;
            instance["RotationDegrees"].DoubleValue = metadata.RotationDegrees;
            var status = instance.WriteChanges();
            if (status != StatusInt.Success) throw new InvalidOperationException("CEL 构件附加项保存失败：" + status);
        }

        private static bool EnsureProperty(ItemType type, string name, CustomProperty.TypeKind kind, object defaultValue)
        {
            CustomProperty property = type.GetPropertyByName(name);
            if (property != null)
            {
                if (property.Type != kind) throw new InvalidOperationException("CEL 附加项属性类型不兼容：" + name);
                return false;
            }
            property = type.AddProperty(name, false);
            if (property == null) throw new InvalidOperationException("无法添加 CEL 附加项属性：" + name);
            property.Type = kind; property.DefaultValue = defaultValue;
            return true;
        }

        internal static CelStatisticsSnapshot Read(bool allModels = false)
        {
            var file = Session.Instance.GetActiveDgnFile();
            var activeModel = Session.Instance.GetActiveDgnModel();
            if (file == null || activeModel == null) throw new InvalidOperationException("请先打开 DGN 模型。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销或重做，请稍后统计。");
            string fileName = file.GetFileName();
            var rows = new List<CelComponentRecord>();
            ItemTypeLibrary library = ItemTypeLibrary.FindByName(LibraryName, file);
            if (library == null) return CelStatisticsCalculator.Summarize(rows, fileName, allModels);
            if (allModels)
            {
                // Root models only: do not traverse reference attachments or children inside a Cell.
                foreach (var index in file.GetModelIndexCollection())
                {
                    StatusInt status;
                    var model = file.LoadRootModelById(out status, (ModelId)index.Id);
                    if (model == null || status != StatusInt.Success)
                        throw new InvalidOperationException("无法读取模型“" + index.Name + "”：" + status);
                    ReadModel(model, index.Name, library.InternalName, rows);
                }
            }
            else ReadModel(activeModel, activeModel.GetModelInfo().Name, library.InternalName, rows);
            if (!ReferenceEquals(file, Session.Instance.GetActiveDgnFile()) || !ReferenceEquals(activeModel, Session.Instance.GetActiveDgnModel()))
                throw new InvalidOperationException("统计期间活动文档发生改变，请重新统计。");
            return CelStatisticsCalculator.Summarize(rows, fileName, allModels);
        }

        private static void ReadModel(DgnModel model, string modelName, string schemaName, List<CelComponentRecord> rows)
        {
            foreach (Element element in model.GetGraphicElements())
            using (element)
            {
                if (!IsRootCell(element)) continue;
                CelComponentRecord record = ReadRecord(element, modelName, schemaName);
                if (record != null) rows.Add(record);
            }
        }

        internal static void ValidatePersisted(Element element, string modelName, CelPlacementMetadata expected)
        {
            var file = Session.Instance.GetActiveDgnFile();
            var library = file == null ? null : ItemTypeLibrary.FindByName(LibraryName, file);
            if (library == null) throw new InvalidOperationException("无法重读 CEL 附加项库。");
            CelComponentRecord actual = ReadRecord(element, modelName, library.InternalName);
            if (actual == null || actual.LibraryFileName != expected.LibraryFileName || actual.CellName != expected.CellName ||
                actual.Category != expected.Category || actual.Specification != expected.Specification ||
                actual.Quantity != 1 || actual.Version != 1 || actual.RotationDegrees != expected.RotationDegrees)
                throw new InvalidOperationException("CEL 构件附加项未完整保存，本次放置将回滚。");
        }

        internal static bool IsRootCell(Element element)
        {
            return element != null && element.IsValid && !element.IsDeleted && element is CellHeaderElement &&
                element.ElementType == MSElementType.CellHeader && !element.IsComplexComponent && element.ParentElement == null;
        }

        private static CelComponentRecord ReadRecord(Element element, string modelName, string schemaName)
        {
            if (!IsRootCell(element)) return null;
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            CelComponentRecord result = null;
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                foreach (IDgnECInstance instance in instances)
                {
                    if (!string.Equals(instance.ClassDefinition.Schema.Name, schemaName, StringComparison.Ordinal) ||
                        instance.ClassDefinition.Name != ItemTypeName) continue;
                    if (result != null) throw new InvalidOperationException("同一根单元存在重复 CEL 附加项，请检查元素：" + element.ElementId);
                    var available = new HashSet<string>(instance.ClassDefinition.Properties(true).Select(property => property.Name));
                    foreach (string name in TextFields.Concat(new[] { "Quantity", "Version", "RotationDegrees" }))
                        if (!available.Contains(name) || instance[name] == null || instance[name].IsNull)
                            throw new InvalidOperationException("CEL 附加项缺少字段“" + name + "”，元素：" + element.ElementId);
                    result = new CelComponentRecord
                    {
                        ModelName = modelName, ElementId = ((ulong)element.ElementId).ToString(CultureInfo.InvariantCulture),
                        LibraryFileName = instance["SourceLibrary"].StringValue, CellName = instance["CellName"].StringValue,
                        Category = instance["Category"].StringValue, Specification = instance["Specification"].StringValue,
                        Quantity = instance["Quantity"].IntValue, Version = instance["Version"].IntValue,
                        RotationDegrees = instance["RotationDegrees"].DoubleValue
                    };
                    if (result.Quantity != 1 || result.Version != 1 || string.IsNullOrWhiteSpace(result.CellName) ||
                        string.IsNullOrWhiteSpace(result.LibraryFileName) || double.IsNaN(result.RotationDegrees) || double.IsInfinity(result.RotationDegrees))
                        throw new InvalidOperationException("CEL 附加项值无效，元素：" + element.ElementId);
                }
            }
            return result;
        }
    }
}
