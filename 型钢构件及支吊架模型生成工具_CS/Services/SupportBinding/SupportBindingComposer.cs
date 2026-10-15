using System;
using System.Collections.Generic;
using System.Linq;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class SupportBindingComposer
    {
        internal const int MaxMembers = 19, MaxTagLength = 256;
        internal static void ValidateTag(string tag)
        {
            if (string.IsNullOrWhiteSpace(tag) || tag.Length > MaxTagLength ||
                tag.Any(c => char.IsControl(c) || c == '$' || c == '\u2028' || c == '\u2029'))
                throw new InvalidOperationException("编号须为非空单行文字，最多256字符，不能包含ISO分行符$。");
        }
        internal static void Validate(SupportBindingRecord record)
        {
            if (record == null || record.Version != 1 || string.IsNullOrWhiteSpace(record.SupportInstanceId) || record.SupportInstanceId.Length > 512)
                throw new InvalidOperationException("组合绑定记录版本或管夹身份无效。");
            ValidateTag(record.BaseTag);
            if (record.Members == null || record.Members.Count > MaxMembers)
                throw new InvalidOperationException("每个管夹最多关联19个承重支架。");
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var member in record.Members)
            {
                if (member == null || member.ElementId == 0 || string.IsNullOrWhiteSpace(member.ModelId) || member.ModelId.Length > 128 ||
                    (member.SupportType != null && member.SupportType.Length > 512) ||
                    !IsCarrier(member.ItemType)) throw new InvalidOperationException("承重支架身份或类型无效。");
                ValidateTag(member.Tag);
                if (!seen.Add(member.ModelId + "\n" + member.ElementId))
                    throw new InvalidOperationException("同一个承重支架不能重复关联；同编号的不同支架可以分别关联。");
            }
        }
        internal static bool IsCarrier(string itemType)
        {
            const string prefix = "PipeSupportAssembly_";
            if (itemType == null || !itemType.StartsWith(prefix, StringComparison.Ordinal)) return false;
            string code = itemType.Substring(prefix.Length);
            return new[] { "T_FRAME_D12", "T_FRAME_G4", "H_T_FRAME", "PORTAL_FRAME", "PORTAL_FRAME_H",
                "G5_GROUND_PORTAL_FRAME", "G6_GROUND_PORTAL_FRAME", "D16_HORIZONTAL_PORTAL_FRAME", "D20_PORTAL_FRAME",
                "N1_CANTILEVER", "N2_DOUBLE_CANTILEVER", "N3_SINGLE_BRACKET", "N4_DOUBLE_BRACKET",
                "D2_CANTILEVER", "D3_CANTILEVER", "G11_CANTILEVER", "L_PIPE_RACK",
                "D5_END_WELDED_TRIANGLE_BRACKET", "D6_SIDE_WELDED_TRIANGLE_BRACKET",
                "G12_CONCRETE_ANCHORED_BRACKET", "D19_DOUBLE_CHANNEL_TRIANGLE_BRACKET", "G2", "N8", "Q1", "Q2" }
                .Contains(code, StringComparer.Ordinal);
        }
        internal static string Compose(SupportBindingRecord record, bool forIso)
        {
            Validate(record);
            if (record.Members.Count == 0) return record.BaseTag;
            return string.Join(forIso ? "$ " : Environment.NewLine, Numbered(record));
        }
        /// <summary>材料表单行：(1)编号 (2)编号。引注换行不能用 $(2) 或 $$(2)，轴测会把 (2) 当成属性删掉。</summary>
        internal static string ComposeMaterial(SupportBindingRecord record)
        {
            Validate(record);
            if (record.Members.Count == 0) return record.BaseTag;
            return string.Join(" ", Numbered(record));
        }
        private static List<string> Numbered(SupportBindingRecord record)
        {
            var tags = new List<string> { record.BaseTag };
            tags.AddRange(record.Members.Select(m => m.Tag));
            return tags.Select((tag, i) => Prefix(i + 1) + tag).ToList();
        }
        internal static string Prefix(int index) { return "(" + index.ToString(CultureInfo.InvariantCulture) + ")"; }
        internal static SupportBindingRecord Copy(SupportBindingRecord record)
        {
            Validate(record);
            return new SupportBindingRecord { SupportInstanceId = record.SupportInstanceId, BaseTag = record.BaseTag,
                OriginalDescription = record.OriginalDescription,
                Members = record.Members.Select(m => new SupportBindingMember { ElementId = m.ElementId,
                    ModelId = m.ModelId, ItemType = m.ItemType, Tag = m.Tag, SupportType = m.SupportType }).ToList() };
        }
        internal static bool SameMember(SupportBindingMember a, SupportBindingMember b)
        {
            return a != null && b != null && a.ElementId == b.ElementId && a.ModelId == b.ModelId &&
                a.ItemType == b.ItemType && a.Tag == b.Tag && a.SupportType == b.SupportType;
        }
        internal static void ValidateUnchanged(SupportBindingTarget before, SupportBindingTarget current)
        {
            if (before == null || current == null || before.ModelToken != current.ModelToken ||
                before.FileName != current.FileName || before.ElementId != current.ElementId || before.InstanceId != current.InstanceId ||
                before.ClassName != current.ClassName || before.BaseTag != current.BaseTag || before.Alias != current.Alias ||
                before.NativePayload != current.NativePayload || before.BindingPayload != current.BindingPayload)
                throw new InvalidOperationException("管夹或绑定信息已改变，请重新读取后再保存。");
        }
        internal static SupportBindingMaterialCandidate MaterialOwner(IEnumerable<SupportBindingMaterialCandidate> candidates, string previousOwner)
        {
            var values = candidates.ToList();
            if (values.Count == 0) return null;
            if (values.Any(v => v.Target == null || string.IsNullOrEmpty(v.Target.InstanceId) ||
                double.IsNaN(v.Dn) || double.IsInfinity(v.Dn) || v.Dn <= 0))
                throw new InvalidOperationException("无法确定关联管道的公称直径，不能分配材料归属。");
            double max = values.Max(v => v.Dn);
            // 最大管径并列时保留原归属；首次按持久原生ID确定，避免每次保存来回转移。
            return values.Where(v => Math.Abs(v.Dn - max) < .001)
                .OrderByDescending(v => v.Target.InstanceId == previousOwner)
                .ThenBy(v => v.Target.InstanceId, StringComparer.Ordinal).First();
        }
    }
}
