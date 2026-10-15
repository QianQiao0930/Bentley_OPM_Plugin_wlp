using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    /// <summary>仅接受当前活动模型的完整根元素；枚举内立即复制清单值。</summary>
    internal static class SupportBindingReader
    {
        internal static Element Find(LocatedElement located, bool writable)
        {
            var active = Session.Instance.GetActiveDgnModel();
            if (active == null || !active.Is3d) throw new InvalidOperationException("请先打开三维活动模型。");
            if (located == null || located.ModelRef == null || located.ModelRef.IsDgnAttachment ||
                !ReferenceEquals(located.ModelRef.GetDgnModel(), active))
                throw new InvalidOperationException("请选择当前活动模型中的支架，暂不支持参考文件。");
            if (writable && (active.IsReadOnly || active.GetDgnFile().IsReadOnly))
                throw new InvalidOperationException("活动模型或文件只读，不能保存绑定。");
            ulong id = located.ElementId;
            var element = active.FindElementById(new ElementId(ref id));
            try
            {
                if (element == null || !element.IsValid || element.IsDeleted)
                    throw new InvalidOperationException("所选支架已删除或失效，请重新点取。");
                if (element.IsComplexComponent || element.ParentElement != null)
                    throw new InvalidOperationException("请选择支架整组，不能选择块内子构件。");
                if (writable && element.IsEffectivelyLocked(true, true))
                    throw new InvalidOperationException("管夹或所在图层已锁定，不能保存绑定。");
                return element;
            }
            catch { element?.Dispose(); throw; }
        }

        internal static SupportBindingTarget ReadTarget(LocatedElement located)
        {
            using (var element = Find(located, true))
            {
                var host = new CustomItemHost(element, false);
                var native = host.GetCustomItem("SteelSectionProbeNativeSupports", "PlacedPipeSupport");
                if (native == null) throw new InvalidOperationException("请选择本插件正式放置的原生管夹、立管耳轴或弯头耳轴。");
                string nativePayload = Text(native, "Payload");
                if (nativePayload.Length == 0 || nativePayload.Length > 2 * 1024 * 1024)
                    throw new InvalidOperationException("原生支架身份记录无效。");
                var record = new JavaScriptSerializer().Deserialize<NativePipeSupportRecord>(nativePayload);
                if (record == null || record.Version != 1 || string.IsNullOrWhiteSpace(record.SupportInstanceId))
                    throw new InvalidOperationException("原生支架身份记录缺失或版本不支持。");
                bool clamp = record.NativeClass == NativePipeSupportDefinition.NativeClass;
                bool legacy = record.NativeClass == "SUPPORT_LOCATION" || record.NativeClass == NativePipeSupportDefinition.TrunnionClass;
                bool stock = NativePipeSupportDefinition.IsStockTrunnionClass(record.NativeClass);
                if (!clamp && !legacy && !stock) throw new InvalidOperationException("不支持此原生支架类别。");
                var instance = DgnUtilities.GetInstanceByInstanceId(record.SupportInstanceId);
                if (instance == null || instance.ClassDefinition.Name != record.NativeClass)
                    throw new InvalidOperationException("原生支架身份已改变，请重新点取。");
                using (var nativeElement = NativeSupportElements.Get(instance, true))
                    if ((ulong)nativeElement.ElementId != located.ElementId)
                        throw new InvalidOperationException("原生记录与实际元素不一致，不能编辑复制的旧身份记录。");
                NativeSupportData.RequireProperty(instance, "ALIAS");
                string marker = Text(instance, "DEVICE_TYPE_CODE");
                if (marker != NativePipeSupportDefinition.DeviceTypeCode && marker != NativePipeSupportDefinition.TrunnionDeviceTypeCode)
                    throw new InvalidOperationException("所选对象没有本插件的原生支架标记。");
                SupportBindingComposer.ValidateTag(record.IsoTag);
                var assemblies = ReadAssemblies(element);
                if (assemblies.Count != 1 || assemblies[0].Tag != record.IsoTag)
                    throw new InvalidOperationException("管夹的原始编号与材料记录不一致，请先修复原始记录。");
                string bindingPayload = ReadBindingPayload(element);
                var binding = string.IsNullOrEmpty(bindingPayload)
                    ? new SupportBindingRecord { SupportInstanceId = record.SupportInstanceId, BaseTag = record.IsoTag }
                    : SupportBindingStore.Decode(bindingPayload);
                if (binding.SupportInstanceId != record.SupportInstanceId || binding.BaseTag != record.IsoTag)
                    throw new InvalidOperationException("组合绑定身份或原始编号与管夹不一致。");
                return new SupportBindingTarget { ModelToken = NativeSupportElements.ActiveModelToken(),
                    FileName = Session.Instance.GetActiveDgnFile().GetFileName(),
                    ParentInstanceId = record.PipeInstanceId, Dn = record.Dn,
                    ElementId = located.ElementId, InstanceId = record.SupportInstanceId, ClassName = record.NativeClass,
                    BaseTag = record.IsoTag, Alias = Text(instance, "ALIAS"), NativePayload = nativePayload,
                    BindingPayload = bindingPayload, Binding = binding };
            }
        }

        internal static SupportBindingMember ReadMember(LocatedElement located)
        {
            using (var element = Find(located, false))
            {
                var values = ReadAssemblies(element);
                if (values.Count != 1 || !SupportBindingComposer.IsCarrier(values[0].ItemType))
                    throw new InvalidOperationException("请选择已确认的承重钢构整组，例如T型架、门型架或三角架。");
                SupportBindingComposer.ValidateTag(values[0].Tag);
                values[0].ElementId = located.ElementId;
                // 活动文件内的持久模型ID；不把会话指针写入关联记录。
                values[0].ModelId = Session.Instance.GetActiveDgnModel().GetModelId().ToString();
                return values[0];
            }
        }
        internal static string ReadBindingPayload(Element element)
        {
            var item = new CustomItemHost(element, false).GetCustomItem(SupportBindingStore.LibraryName, SupportBindingStore.TypeName);
            if (item == null) return "";
            string payload = Text(item, "Payload");
            if (string.IsNullOrEmpty(payload)) throw new InvalidOperationException("组合附加项已存在，但关联记录为空。");
            return payload;
        }
        private static List<SupportBindingMember> ReadAssemblies(Element element)
        {
            var values = new List<SupportBindingMember>();
            var library = ItemTypeLibrary.FindByName("PipeSupportComponents", Session.Instance.GetActiveDgnFile());
            if (library == null) return values;
            var query = new ECQuery(); query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
                foreach (IDgnECInstance instance in instances)
                    if (string.Equals(instance.ClassDefinition.Schema.Name, library.InternalName, StringComparison.OrdinalIgnoreCase) &&
                        instance.ClassDefinition.Name.StartsWith("PipeSupportAssembly_", StringComparison.Ordinal) &&
                        Text(instance, "RecordKind") == "Assembly")
                        values.Add(new SupportBindingMember { ItemType = instance.ClassDefinition.Name,
                            Tag = Text(instance, "AssemblyTag"), SupportType = Text(instance, "SupportType") });
            return values;
        }
        internal static string Text(IECInstance instance, string name)
        {
            if (!instance.ClassDefinition.Properties(true).Any(p => p.Name == name)) return "";
            return instance[name] == null || instance[name].IsNull ? "" : instance[name].StringValue ?? "";
        }
    }
}
