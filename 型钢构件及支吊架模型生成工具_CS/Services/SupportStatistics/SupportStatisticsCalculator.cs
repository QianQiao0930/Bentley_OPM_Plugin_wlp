using System;
using System.Collections.Generic;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class SupportStatisticsCalculator
    {
        internal static SupportStatisticsSnapshot Summarize(IEnumerable<SupportRecord> source)
        {
            var result=new SupportStatisticsSnapshot();
            if (source==null) return result;
            result.Records.AddRange(source.OrderBy(r=>r.SupportType).ThenBy(r=>r.ElementId));
            var types=new Dictionary<string,SupportTypeSummary>(StringComparer.Ordinal);
            var materials=new Dictionary<string,MaterialSummary>(StringComparer.Ordinal);
            foreach(var record in result.Records)
            {
                string type=string.IsNullOrWhiteSpace(record.SupportType)?"未知":record.SupportType;
                int quantity=record.Quantity==0?1:record.Quantity;
                if (string.Equals(record.RecordKind,"Assembly",StringComparison.OrdinalIgnoreCase))
                {
                    SupportTypeSummary group;
                    if (!types.TryGetValue(type,out group))
                    {
                        group=new SupportTypeSummary { SupportType=type };
                        types.Add(type,group);
                    }
                    group.AssemblyCount+=quantity;
                    if (!string.IsNullOrEmpty(record.AssemblyTag))
                        group.AssemblyTags.Add(record.AssemblyTag);
                    result.AssemblyCount+=quantity;
                }
                else
                {
                    result.ComponentRecordCount++;
                    string key=type+"\u001f"+record.ComponentName+"\u001f"+
                        record.Specification+"\u001f"+record.Unit;
                    MaterialSummary group;
                    if (!materials.TryGetValue(key,out group))
                    {
                        group=new MaterialSummary { SupportType=type,
                            ComponentName=record.ComponentName,Specification=record.Specification,
                            Unit=record.Unit };
                        materials.Add(key,group);
                    }
                    group.Quantity+=quantity;
                    group.TotalDesignLengthMm+=record.DesignLengthMm*quantity;
                }
            }
            result.SupportsByType.AddRange(types.Values.OrderBy(t=>t.SupportType));
            foreach(var type in result.SupportsByType) type.AssemblyTags.Sort(StringComparer.Ordinal);
            result.Materials.AddRange(materials.Values
                .OrderBy(m=>m.SupportType).ThenBy(m=>m.ComponentName).ThenBy(m=>m.Specification));
            foreach(var material in result.Materials)
                material.TotalDesignLengthMm=Math.Round(material.TotalDesignLengthMm,3);
            return result;
        }
    }
}
