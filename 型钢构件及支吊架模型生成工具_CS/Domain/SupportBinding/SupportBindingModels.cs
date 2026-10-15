using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>组合只保存引用与引注；不复制钢构材料，也不改变几何父子关系。</summary>
    internal sealed class SupportBindingMember
    {
        public ulong ElementId;
        public string ModelId, ItemType, Tag, SupportType;
        public override string ToString() { return Tag + "  ·  元素 " + ElementId; }
    }

    internal sealed class SupportBindingRecord
    {
        public int Version = 1;
        public string SupportInstanceId, BaseTag, OriginalDescription;
        public List<SupportBindingMember> Members = new List<SupportBindingMember>();
    }

    /// <summary>短期只读快照；写入前复核。模型指针仅用于当前会话，不进入持久记录。</summary>
    internal sealed class SupportBindingTarget
    {
        internal long ModelToken;
        internal ulong ElementId;
        internal string FileName, InstanceId, ClassName, BaseTag, Alias, NativePayload, BindingPayload;
        internal string ParentInstanceId;
        internal int Dn;
        internal SupportBindingRecord Binding;
    }

    internal sealed class SupportBindingMaterialRecord
    {
        public int Version = 1;
        public string ModelId, ItemType, Tag, OwnerSupportInstanceId, ParentInstanceId, NoteInstanceId;
        public ulong CarrierElementId;
        public double OwnerDn;
    }

    internal sealed class SupportBindingMaterialCandidate
    {
        internal SupportBindingTarget Target;
        internal double Dn;
        internal static SupportBindingMaterialCandidate Create(SupportBindingTarget target, double dn)
        { return new SupportBindingMaterialCandidate { Target = target, Dn = dn }; }
    }
}
