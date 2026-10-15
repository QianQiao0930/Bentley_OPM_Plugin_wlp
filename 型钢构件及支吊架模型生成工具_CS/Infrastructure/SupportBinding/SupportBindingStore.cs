using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class SupportBindingStore
    {
        internal const string LibraryName = "SteelSectionProbeSupportBindings", TypeName = "SupportBinding";
        internal const string MaterialTypeName = "BomMaterial";
        internal static string Encode(SupportBindingRecord record)
        {
            SupportBindingComposer.Validate(record);
            // 不依赖运行时反射的字段枚举顺序，否则精确回读可能将同一记录误判为写入丢失。
            var fields = new Dictionary<string, object> {
                { "Version", record.Version }, { "SupportInstanceId", record.SupportInstanceId }, { "BaseTag", record.BaseTag },
                { "OriginalDescription", record.OriginalDescription },
                { "Members", record.Members.Select(member => new Dictionary<string, object> {
                    { "ElementId", member.ElementId }, { "ModelId", member.ModelId }, { "ItemType", member.ItemType },
                    { "Tag", member.Tag }, { "SupportType", member.SupportType } }).ToArray() } };
            string payload = new JavaScriptSerializer().Serialize(fields);
            if (payload.Length > 32768) throw new InvalidOperationException("组合绑定信息过长。");
            return payload;
        }
        internal static SupportBindingRecord Decode(string payload)
        {
            if (string.IsNullOrEmpty(payload) || payload.Length > 32768)
                throw new InvalidOperationException("组合绑定记录为空或过长。");
            var serializer = new JavaScriptSerializer();
            var fields = serializer.DeserializeObject(payload) as System.Collections.Generic.Dictionary<string, object>;
            if (fields == null || !fields.ContainsKey("Version") || !fields.ContainsKey("Members"))
                throw new InvalidOperationException("组合绑定记录缺少版本或关联列表。");
            var result = serializer.Deserialize<SupportBindingRecord>(payload);
            SupportBindingComposer.Validate(result);
            return result;
        }
        internal static void Write(Element element, SupportBindingRecord record)
        {
            WriteFields(element, TypeName, new System.Collections.Generic.Dictionary<string, string> {
                { "Payload", Encode(record) }, { "BaseTag", record.BaseTag },
                { "CombinedTag", SupportBindingComposer.Compose(record, false) } });
        }
        internal static void WriteMaterial(Element element, SupportBindingMaterialRecord record)
        {
            ValidateMaterial(record);
            WriteFields(element, MaterialTypeName, new System.Collections.Generic.Dictionary<string, string> {
                { "Payload", new JavaScriptSerializer().Serialize(record) } });
        }
        internal static SupportBindingMaterialRecord ReadMaterial(Element element)
        {
            var item = new CustomItemHost(element, false).GetCustomItem(LibraryName, MaterialTypeName);
            if (item == null) return null;
            string json = SupportBindingReader.Text(item, "Payload");
            if (string.IsNullOrEmpty(json) || json.Length > 8192) throw new InvalidOperationException("附加材料身份记录无效。");
            var raw = new JavaScriptSerializer().Deserialize<SupportBindingMaterialRecord>(json);
            var record = new SupportBindingMaterialRecord {
                Version = raw.Version, ModelId = raw.ModelId, ItemType = raw.ItemType, Tag = raw.Tag,
                OwnerSupportInstanceId = raw.OwnerSupportInstanceId, ParentInstanceId = raw.ParentInstanceId,
                NoteInstanceId = raw.NoteInstanceId, CarrierElementId = raw.CarrierElementId, OwnerDn = raw.OwnerDn };
            ValidateMaterial(record);
            return record;
        }
        private static void ValidateMaterial(SupportBindingMaterialRecord record)
        {
            if (record == null || record.Version != 1 || record.CarrierElementId == 0 ||
                string.IsNullOrEmpty(record.ModelId) || !SupportBindingComposer.IsCarrier(record.ItemType) ||
                string.IsNullOrEmpty(record.OwnerSupportInstanceId) || string.IsNullOrEmpty(record.ParentInstanceId) ||
                string.IsNullOrEmpty(record.NoteInstanceId) || double.IsNaN(record.OwnerDn) || double.IsInfinity(record.OwnerDn) || record.OwnerDn <= 0)
                throw new InvalidOperationException("附加材料身份或计材归属记录无效。");
            SupportBindingComposer.ValidateTag(record.Tag);
        }
        private static void WriteFields(Element element, string typeName, System.Collections.Generic.IDictionary<string, string> fields)
        {
            var file = Session.Instance.GetActiveDgnFile();
            var library = ItemTypeLibrary.FindByName(LibraryName, file) ?? ItemTypeLibrary.Create(LibraryName, file, false);
            if (library == null) throw new InvalidOperationException("无法创建组合绑定附加项库。");
            var type = library.GetItemTypeByName(typeName);
            bool changed = false;
            if (type == null) { type = library.AddItemType(typeName, false); changed = true; }
            if (type == null) throw new InvalidOperationException("无法创建组合绑定附加项。");
            foreach (string name in fields.Keys)
            {
                var property = type.GetPropertyByName(name);
                if (property == null)
                {
                    property = type.AddProperty(name, false);
                    if (property == null) throw new InvalidOperationException("无法创建组合绑定字段：" + name);
                    property.Type = CustomProperty.TypeKind.String; changed = true;
                }
                if (property.Type != CustomProperty.TypeKind.String)
                    throw new InvalidOperationException("组合绑定字段类型冲突：" + name);
            }
            if (changed)
            {
                if (!library.Write()) throw new InvalidOperationException("组合绑定附加项定义保存失败。");
                type = ItemTypeLibrary.FindByName(LibraryName, file)?.GetItemTypeByName(typeName);
            }
            if (type == null) throw new InvalidOperationException("组合绑定附加项不可用。");
            var host = new CustomItemHost(element, false);
            // 同一元素上已有该附加项时，ApplyCustomItem 会返回空；更新和解除绑定必须改原记录。
            var item = host.GetCustomItem(LibraryName, typeName) ?? host.ApplyCustomItem(type);
            if (item == null) throw new InvalidOperationException("无法附加组合绑定信息。");
            foreach (var field in fields) item[field.Key].StringValue = field.Value;
            if (item.WriteChanges() != StatusInt.Success) throw new InvalidOperationException("组合绑定信息保存失败。");
        }
    }
}
