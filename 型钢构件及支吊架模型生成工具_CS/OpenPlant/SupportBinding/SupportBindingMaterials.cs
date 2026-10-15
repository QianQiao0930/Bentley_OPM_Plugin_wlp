using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    /// <summary>
    /// 承重编号写在管夹引注和材料描述上，不再创建 ADDITIONAL_MATERIAL 符号。
    /// 保存或同步时删除已经存在的本插件材料附注，避免大红拱参与模型和碰撞。
    /// </summary>
    internal sealed class SupportBindingMaterials
    {
        private readonly List<BMECObject> changed = new List<BMECObject>();

        internal void SynchronizeAll()
        {
            var model = Session.Instance.GetActiveDgnModel();
            var all = new SupportBindingRecord { SupportInstanceId = "SYNC", BaseTag = "SYNC" };
            foreach (var element in model.GetGraphicElements())
            {
                if (!element.IsValid || element.IsDeleted || element.IsComplexComponent || element.ParentElement != null) continue;
                var material = SupportBindingStore.ReadMaterial(element);
                if (material != null) all.Members.Add(new SupportBindingMember { ModelId = material.ModelId,
                    ElementId = material.CarrierElementId, ItemType = material.ItemType, Tag = material.Tag });
                string json = SupportBindingReader.ReadBindingPayload(element);
                if (!string.IsNullOrEmpty(json)) all.Members.AddRange(SupportBindingStore.Decode(json).Members);
            }
            // 仅作为受影响ID集合，不序列化为单个绑定记录，不受单管夹19项上限限制。
            Synchronize(all, new SupportBindingRecord());
        }

        internal void Synchronize(SupportBindingRecord before, SupportBindingRecord after)
        {
            var model = Session.Instance.GetActiveDgnModel();
            string modelId = model.GetModelId().ToString();
            var affected = new HashSet<ulong>(before.Members.Concat(after.Members)
                .Where(m => m.ModelId == modelId).Select(m => m.ElementId));
            if (affected.Count == 0) return;
            var notes = new List<SupportBindingMaterialRecord>();
            // 完成读取后才删除，不在图形枚举中修改模型。承重编号写在管夹上，不再创建 ADDITIONAL_MATERIAL。
            foreach (var element in model.GetGraphicElements())
            {
                if (!element.IsValid || element.IsDeleted || element.IsComplexComponent || element.ParentElement != null) continue;
                var material = SupportBindingStore.ReadMaterial(element);
                if (material != null && material.ModelId == modelId && affected.Contains(material.CarrierElementId))
                {
                    ValidateNote(material, (ulong)element.ElementId, false);
                    notes.Add(material);
                }
            }
            foreach (ulong id in affected)
            {
                var existing = notes.Where(n => n.CarrierElementId == id).ToArray();
                if (existing.Length > 1) throw new InvalidOperationException("同一钢构存在重复附加材料身份，请先核查：元素 " + id);
                if (existing.Length == 1) Delete(existing[0]);
            }
        }

        private static IECInstance ResolveNote(SupportBindingMaterialRecord record)
        {
            var note = DgnUtilities.GetInstanceByInstanceId(record.NoteInstanceId);
            if (note == null || note.ClassDefinition.Name != "ADDITIONAL_MATERIAL")
                throw new InvalidOperationException("附加材料原生身份丢失或类型改变，不能猜测替代对象。");
            return note;
        }
        private static void ValidateNote(SupportBindingMaterialRecord record, ulong? elementId, bool verifyData = true)
        {
            var note = ResolveNote(record);
            using (var element = NativeSupportElements.Get(note, true))
            {
                if (elementId.HasValue && (ulong)element.ElementId != elementId.Value)
                    throw new InvalidOperationException("附加材料身份记录与图形不一致。");
                var saved = SupportBindingStore.ReadMaterial(element);
                if (saved == null || saved.CarrierElementId != record.CarrierElementId || saved.ModelId != record.ModelId ||
                    saved.NoteInstanceId != record.NoteInstanceId || saved.OwnerSupportInstanceId != record.OwnerSupportInstanceId ||
                    saved.ParentInstanceId != record.ParentInstanceId || saved.Tag != record.Tag || saved.ItemType != record.ItemType ||
                    Math.Abs(saved.OwnerDn - record.OwnerDn) > .001)
                    throw new InvalidOperationException("附加材料归属记录未完整保存。");
            }
            if (!verifyData) return;
            if (!HasParent(note, record.ParentInstanceId) ||
                SupportBindingReader.Text(note, "TEXT") != Description(record.Tag))
                throw new InvalidOperationException("附加材料父管或材料描述不一致。");
        }
        private void Delete(SupportBindingMaterialRecord record)
        {
            ValidateNote(record, null, false);
            var instance = ResolveNote(record);
            using (var acquired = PipeAlignment.OpenPlantObjectFactory.Acquire(instance.InstanceId, instance))
            {
                if (acquired.Object == null || acquired.OwnsObject) throw new InvalidOperationException("无法取得附加材料的文档对象。");
                changed.Add(acquired.Object);
                if (BMECApi.Instance.DeleteFromModel(acquired.Object) != 0 || DgnUtilities.GetInstanceByInstanceId(record.NoteInstanceId) != null)
                    throw new InvalidOperationException("旧计材归属删除失败，已停止转移。");
            }
        }
        private static bool HasParent(IECInstance note, string parentId)
        {
            var parents = BMECApi.Instance.GetRelatedInstances(note, "PIPING_COMPONENT_HAS_NOTE", false, true);
            return parents != null && parents.Count == 1 && parents[0].InstanceId == parentId;
        }
        internal void Rollback()
        {
            foreach (var item in changed) { item.Refresh(); item.Resync(); }
        }
        internal void Retain() { }
        private static void Text(IECInstance instance, string name, string value)
        { NativeSupportData.RequireProperty(instance, name); instance[name].StringValue = value; }
        internal static string Description(string tag)
        {
            SupportBindingComposer.ValidateTag(tag);
            var result = new StringBuilder();
            foreach (char c in tag.Replace("×", "x").Replace("∠", "L").Replace("°", "deg"))
                if (c >= 32 && c <= 126) result.Append(c);
                else result.Append("\\u").Append(((int)c).ToString("X4", CultureInfo.InvariantCulture));
            return result.ToString();
        }
    }
}
