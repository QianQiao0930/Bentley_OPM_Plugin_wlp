using System;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class A1NativeTrialStore
    {
        private const string Library = "SteelSectionProbeTrials", Type = "A1NativeSupport";
        internal static void Write(Element element, A1NativeTrialRecord record)
        {
            var file = Session.Instance.GetActiveDgnFile();
            var library = ItemTypeLibrary.FindByName(Library, file) ?? ItemTypeLibrary.Create(Library, file, false);
            if (library == null) throw new InvalidOperationException("无法创建A1试验数据定义库。");
            var type = library.GetItemTypeByName(Type);
            if (type == null)
            {
                type = library.AddItemType(Type, false);
                if (type == null) throw new InvalidOperationException("无法创建A1试验数据类型。");
                var property = type.AddProperty("Payload", false);
                if (property == null) throw new InvalidOperationException("无法创建A1试验参数字段。");
                property.Type = CustomProperty.TypeKind.String;
                if (!library.Write()) throw new InvalidOperationException("无法保存A1试验数据定义。");
                type = ItemTypeLibrary.FindByName(Library, file)?.GetItemTypeByName(Type);
            }
            if (type == null) throw new InvalidOperationException("无法重新读取A1试验数据类型。");
            var instance = new CustomItemHost(element, false).ApplyCustomItem(type);
            if (instance == null) throw new InvalidOperationException("无法附加A1试验数据。");
            instance["Payload"].StringValue = new JavaScriptSerializer().Serialize(record);
            if (instance.WriteChanges() != StatusInt.Success) throw new InvalidOperationException("A1试验参数写入失败。");
        }

        internal static A1NativeTrialRecord Read(Element element)
        {
            var instance = new CustomItemHost(element, false).GetCustomItem(Library, Type);
            if (instance == null) throw new InvalidOperationException("请选择本次试验命令生成的A1管夹。");
            var record = new JavaScriptSerializer().Deserialize<A1NativeTrialRecord>(instance["Payload"].StringValue);
            if (record == null || record.Version != 1
                || record.NativeClass != (record.NativeEditing ? "SSP_A1_NATIVE_TEST" : "UBOLT_GUIDE")
                || string.IsNullOrWhiteSpace(record.PipeInstanceId) || string.IsNullOrWhiteSpace(record.SupportInstanceId))
                throw new InvalidOperationException("试验记录缺失或版本不支持。");
            A1NativeTrialCalculator.RequireFinite(record.StationMm);
            A1NativeTrialCalculator.RequireFinite(record.AngleDeg);
            A1NativeTrialCalculator.RequireFinite(record.OriginalLengthMm);
            if (record.StationMm < 0 || record.OriginalLengthMm < 1 || record.StationMm > record.OriginalLengthMm)
                throw new InvalidOperationException("试验站位记录无效。");
            return record;
        }
    }
}
