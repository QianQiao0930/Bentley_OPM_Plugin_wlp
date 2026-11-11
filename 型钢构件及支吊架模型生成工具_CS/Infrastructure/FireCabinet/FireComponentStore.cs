using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
using Bentley.ECObjects.Schema;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 消防构件库的实例写入及当前 DGN 全模型读取，兼容原带模型 Python 记录。
    /// </summary>
    internal static class FireComponentStore
    {
        internal static void Attach(Element element, string itemTypeName, Dictionary<string, object> values)
        {
            var file = Session.Instance.GetActiveDgnFile();
            ItemTypeLibrary library = ItemTypeLibrary.FindByName(FireCabinetCatalog.LibraryName, file);
            bool changed = library == null;
            if (library == null)
            {
                library = ItemTypeLibrary.Create(FireCabinetCatalog.LibraryName, file, false);
            }
            ItemType type = library.GetItemTypeByName(itemTypeName);
            if (type == null)
            {
                type = library.AddItemType(itemTypeName, false);
                changed = true;
            }

            if (type == null)
            {
                throw new InvalidOperationException("无法创建消防构件附加项。");
            }
            foreach (KeyValuePair<string, object> entry in values)
            {
                if (type.GetPropertyByName(entry.Key) != null)
                {
                    continue;
                }
                CustomProperty property = type.AddProperty(entry.Key, false);
                if (property == null)
                {
                    throw new InvalidOperationException("无法创建消防附加项属性：" + entry.Key);
                }
                property.Type = entry.Value is int ? CustomProperty.TypeKind.Integer :
                    entry.Value is double ? CustomProperty.TypeKind.Double : CustomProperty.TypeKind.String;
                property.DefaultValue = entry.Value is int ? (object)0 : entry.Value is double ? (object)0.0 : "";
                changed = true;
            }

            if (changed)
            {
                if (!library.Write())
                {
                    throw new InvalidOperationException("消防构件库保存失败。");
                }
                library = ItemTypeLibrary.FindByName(FireCabinetCatalog.LibraryName, file);
                type = library.GetItemTypeByName(itemTypeName);
            }

            IDgnECInstance instance = new CustomItemHost(element, false).ApplyCustomItem(type);
            if (instance == null)
            {
                throw new InvalidOperationException("消防附加项写入失败。");
            }
            foreach (KeyValuePair<string, object> entry in values)
            {
                IECPropertyValue property = instance[entry.Key];
                if (entry.Value is int)
                {
                    property.IntValue = (int)entry.Value;
                }
                else if (entry.Value is double)
                {
                    property.DoubleValue = (double)entry.Value;
                }
                else
                {
                    property.StringValue = (string)entry.Value;
                }
            }

            StatusInt status = instance.WriteChanges();
            if (status != StatusInt.Success)
            {
                throw new InvalidOperationException("消防附加项实例保存失败：" + status);
            }
        }

        internal static List<FireCabinetRecord> Read(string prefix, Dictionary<string, object> template, string quantityField)
        {
            var file = Session.Instance.GetActiveDgnFile();
            if (file == null)
            {
                throw new InvalidOperationException("没有活动 DGN 文件。");
            }
            ItemTypeLibrary library = ItemTypeLibrary.FindByName(FireCabinetCatalog.LibraryName, file);
            // 活动文件没有消防库时仍扫描参考文件；参考文件可能自带同名库。
            var schemaNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { FireCabinetCatalog.LibraryName };
            if (library != null)
            {
                schemaNames.Add(library.InternalName);
            }
            var loadedReferenceFiles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var records = new List<FireCabinetRecord>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            var query = CreateQuery();
            string activeFileName = file.GetFileName();
            if (string.IsNullOrEmpty(activeFileName))
            {
                activeFileName = "当前 DGN";
            }
            foreach (var index in file.GetModelIndexCollection())
            {
                StatusInt status;
                var model = file.LoadRootModelById(out status, (ModelId)index.Id);
                if (model == null || status != StatusInt.Success)
                {
                    throw new InvalidOperationException("无法读取模型“" + index.Name + "”：" + status);
                }

                foreach (Element element in model.GetGraphicElements())
                {
                    ReadElement(element, index.Name, activeFileName, prefix, schemaNames, template, query, quantityField, records, seen);
                }

                // 只展开当前模型的一级参考附件；不递归嵌套附件。
                foreach (DgnAttachment attachment in model.GetDgnAttachments())
                {
                    if (attachment.IsMissingFile)
                    {
                        continue;
                    }
                    string sourceFile = string.IsNullOrEmpty(attachment.AttachFileName)
                        ? attachment.LogicalName
                        : attachment.AttachFileName;
                    if (string.IsNullOrEmpty(sourceFile))
                    {
                        sourceFile = "参考文件";
                    }
                    string sourceModel = attachment.AttachModelName;
                    if (string.IsNullOrEmpty(sourceModel))
                    {
                        ModelInfo info = attachment.GetModelInfo();
                        sourceModel = info == null ? "" : info.Name;
                    }
                    LoadReferenceSchema(attachment, schemaNames, loadedReferenceFiles);
                    ReadAttachment(attachment, sourceModel, sourceFile, prefix, schemaNames, template, query, quantityField, records, seen);
                }
            }

            return records;
        }

        private static ECQuery CreateQuery()
        {
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            return query;
        }

        /// <summary>
        /// 参考文件的消防库默认不会进入当前 EC 会话；先从附件文件加载库及类定义，
        /// 否则参考实例能显示却查不到，表现为必须先在本文件画一个消防构件。
        /// </summary>
        private static void LoadReferenceSchema(DgnAttachment attachment, HashSet<string> schemaNames,
            HashSet<string> loadedFiles)
        {
            DgnFile referenceFile = attachment.GetDgnFile();
            if (referenceFile == null)
            {
                return;
            }
            string path = referenceFile.GetFileName();
            if (!string.IsNullOrEmpty(path) && !loadedFiles.Add(path))
            {
                return;
            }

            ItemTypeLibrary referenceLibrary = ItemTypeLibrary.FindByName(FireCabinetCatalog.LibraryName, referenceFile);
            if (referenceLibrary == null)
            {
                return;
            }
            schemaNames.Add(referenceLibrary.InternalName);
            // 访问架构及类定义，确保参考文件的 EC 类进入当前会话。
            IECSchema schema = referenceLibrary.ECSchema;
            if (schema != null)
            {
                schemaNames.Add(schema.Name);
                schema.GetClasses();
            }
        }

        private static void ReadElement(Element element, string modelName, string sourceFile, string prefix,
            HashSet<string> schemaNames, Dictionary<string, object> template, ECQuery query, string quantityField,
            List<FireCabinetRecord> records, HashSet<string> seen)
        {
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                foreach (IDgnECInstance instance in instances)
                {
                    AddRecord(element, modelName, sourceFile, prefix, schemaNames, template, instance, quantityField, records, seen);
                }
            }
        }

        private static void ReadAttachment(DgnAttachment attachment, string modelName, string sourceFile, string prefix,
            HashSet<string> schemaNames, Dictionary<string, object> template, ECQuery query, string quantityField,
            List<FireCabinetRecord> records, HashSet<string> seen)
        {
            var scope = FindInstancesScope.CreateScope(attachment, new FindInstancesScopeOption(DgnECHostType.Element));
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                foreach (IDgnECInstance instance in instances)
                {
                    Element element = instance.Element;
                    if (element != null)
                    {
                        AddRecord(element, modelName, sourceFile, prefix, schemaNames, template, instance, quantityField, records, seen);
                    }
                }
            }
        }

        private static void AddRecord(Element element, string modelName, string sourceFile, string prefix,
            HashSet<string> schemaNames, Dictionary<string, object> template, IDgnECInstance instance, string quantityField,
            List<FireCabinetRecord> records, HashSet<string> seen)
        {
            if (!schemaNames.Contains(instance.ClassDefinition.Schema.Name) ||
                !instance.ClassDefinition.Name.StartsWith(prefix, StringComparison.Ordinal))
            {
                return;
            }

            string elementId = ((ulong)element.ElementId).ToString();
            // 同一参考模型被重复附加或同时出现在多个模型时，按源文件+模型+图元+类型只计一次。
            string key = sourceFile + "\u0001" + modelName + "\u0001" + elementId + "\u0001" + instance.ClassDefinition.Name;
            if (!seen.Add(key))
            {
                return;
            }

            var properties = new Dictionary<string, object>();
            // 统一字段集来自纯元数据工厂；旧记录缺少新增字段时保留缺失状态。
            var available = new HashSet<string>(instance.ClassDefinition.Properties(true).Select(property => property.Name));
            foreach (string name in template.Keys)
            {
                if (!available.Contains(name))
                {
                    continue;
                }
                IECPropertyValue value = instance[name];
                if (value != null && !value.IsNull)
                {
                    properties[name] = value.NativeValue;
                }
            }

            if (FireCabinetStatisticsCalculator.Count(properties, quantityField) <= 0)
            {
                return;
            }
            records.Add(new FireCabinetRecord
            {
                ModelName = modelName,
                SourceFile = sourceFile,
                ElementId = elementId,
                Properties = properties
            });
        }
    }
}
