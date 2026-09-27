using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal sealed class SupportRecord
    {
        internal ulong ElementId;
        internal string ItemType="", RecordKind="", SupportType="", AssemblyTag="";
        internal string ComponentName="", Specification="", Unit="", PipeNumber="";
        internal double DesignLengthMm;
        internal int Quantity=1;
    }
    internal sealed class SupportTypeSummary
    {
        internal string SupportType="";
        internal int AssemblyCount;
        internal readonly List<string> AssemblyTags=new List<string>();
    }
    internal sealed class MaterialSummary
    {
        internal string SupportType="", ComponentName="", Specification="", Unit="";
        internal int Quantity;
        internal double TotalDesignLengthMm;
    }
    internal sealed class SupportStatisticsSnapshot
    {
        internal const string LibraryName="PipeSupportComponents";
        internal readonly List<SupportRecord> Records=new List<SupportRecord>();
        internal readonly List<SupportTypeSummary> SupportsByType=new List<SupportTypeSummary>();
        internal readonly List<MaterialSummary> Materials=new List<MaterialSummary>();
        internal int AssemblyCount,ComponentRecordCount;
        internal DateTime ReadAt=DateTime.Now;
    }
}
