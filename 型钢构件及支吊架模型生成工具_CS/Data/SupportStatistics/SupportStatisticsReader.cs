using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;

namespace SteelSectionProbe
{
    /// <summary>Reads ItemTypes from every graphic element in the active DGN file.</summary>
    internal static class SupportStatisticsReader
    {
        internal static SupportStatisticsSnapshot Read()
        {
            var file=Session.Instance.GetActiveDgnFile();
            if (file==null) throw new InvalidOperationException("没有活动 DGN 文件。");
            var library=ItemTypeLibrary.FindByName(SupportStatisticsSnapshot.LibraryName,file);
            if (library==null) return new SupportStatisticsSnapshot();
            var records=new List<SupportRecord>();
            var query=new ECQuery();
            query.SelectClause.SelectAllProperties=true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter,
                ECQueryProcessFlags.SearchAllClasses);
            foreach(var index in file.GetModelIndexCollection())
            {
                StatusInt status;
                var model=file.LoadRootModelById(out status,(ModelId)index.Id);
                if (model==null || status!=StatusInt.Success)
                    throw new InvalidOperationException("无法读取模型“"+index.Name+"”："+status);
                foreach(Element element in model.GetGraphicElements())
                    ReadElement(element,library.InternalName,query,records);
            }
            return SupportStatisticsCalculator.Summarize(records);
        }
        private static void ReadElement(Element element,string schema,ECQuery query,List<SupportRecord> records)
        {
            var scope=FindInstancesScope.CreateScope(element,
                new FindInstancesScopeOption(DgnECHostType.Element));
            using(var instances=DgnECManager.Manager.FindInstances(scope,query))
            {
                foreach(IDgnECInstance instance in instances)
                {
                    if (!string.Equals(instance.ClassDefinition.Schema.Name,
                        schema,StringComparison.OrdinalIgnoreCase)) continue;
                    string type=instance.ClassDefinition.Name;
                    bool assembly=type.StartsWith("PipeSupportAssembly_",StringComparison.Ordinal);
                    bool component=type.StartsWith("PipeSupportComponent_",StringComparison.Ordinal);
                    if (!assembly && !component) continue;
                    var record=new SupportRecord {
                        ElementId=(ulong)element.ElementId,
                        ItemType=type,
                        RecordKind=Text(instance,"RecordKind"),
                        SupportType=Text(instance,"SupportType"),
                        AssemblyTag=Text(instance,"AssemblyTag"),
                        ComponentName=Text(instance,"ComponentName"),
                        Specification=Text(instance,"Specification"),
                        DesignLengthMm=Number(instance,"DesignLengthMm"),
                        Quantity=(int)Number(instance,"Quantity"),
                        Unit=Text(instance,"Unit"),
                        PipeNumber=Text(instance,"PipeNumber")
                    };
                    if (string.IsNullOrEmpty(record.RecordKind))
                        record.RecordKind=assembly?"Assembly":"Component";
                    records.Add(record);
                }
            }
        }
        private static string Text(IDgnECInstance item,string name)
        {
            try
            {
                var value=item[name];
                if (value==null || value.IsNull) return "";
                var native=value.NativeValue;
                return native==null ? "" : Convert.ToString(native,CultureInfo.InvariantCulture);
            }
            catch { return ""; }
        }
        private static double Number(IDgnECInstance item,string name)
        {
            double parsed;
            return double.TryParse(Text(item,name),NumberStyles.Any,
                CultureInfo.InvariantCulture,out parsed) ? parsed : 0;
        }
    }
}
