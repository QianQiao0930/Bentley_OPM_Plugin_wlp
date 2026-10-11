using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
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
            if (library == null)
            {
                return new List<FireCabinetRecord>();
            }
            var records = new List<FireCabinetRecord>();
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
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
                    var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
                    using (var instances = DgnECManager.Manager.FindInstances(scope, query))
                    {
                        foreach (IDgnECInstance instance in instances)
                        {
                            if (!string.Equals(instance.ClassDefinition.Schema.Name, library.InternalName, StringComparison.OrdinalIgnoreCase) ||
                                !instance.ClassDefinition.Name.StartsWith(prefix, StringComparison.Ordinal))
                            {
                                continue;
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
                                continue;
                            }
                            records.Add(new FireCabinetRecord
                            {
                                ModelName = index.Name,
                                ElementId = ((ulong)element.ElementId).ToString(),
                                Properties = properties
                            });
                        }
                    }
                }
            }

            return records;
        }
    }
}
