using System;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class NativePipeSupportStore
    {
        private const string Library = "SteelSectionProbeNativeSupports", Type = "PlacedPipeSupport";
        internal static void Write(Element element, NativePipeSupportRecord record)
        {
            var file = Session.Instance.GetActiveDgnFile();
            var library = ItemTypeLibrary.FindByName(Library, file) ?? ItemTypeLibrary.Create(Library, file, false);
            if (library == null) throw new InvalidOperationException("无法创建原生支吊架记录库。");
            var type = library.GetItemTypeByName(Type);
            if (type == null)
            {
                type = library.AddItemType(Type, false);
                if (type == null) throw new InvalidOperationException("无法创建原生支吊架记录类型。");
                var payload = type.AddProperty("Payload", false);
                if (payload == null) throw new InvalidOperationException("无法创建原生支吊架记录字段。");
                payload.Type = CustomProperty.TypeKind.String;
                if (!library.Write()) throw new InvalidOperationException("原生支吊架记录定义保存失败。");
                type = ItemTypeLibrary.FindByName(Library, file)?.GetItemTypeByName(Type);
            }
            if (type == null) throw new InvalidOperationException("原生支吊架记录类型不可用。");
            var item = new CustomItemHost(element, false).ApplyCustomItem(type);
            if (item == null) throw new InvalidOperationException("无法附加原生支吊架记录。");
            item["Payload"].StringValue = new JavaScriptSerializer().Serialize(record);
            if (item.WriteChanges() != StatusInt.Success) throw new InvalidOperationException("原生支吊架记录保存失败。");
        }
    }
}
