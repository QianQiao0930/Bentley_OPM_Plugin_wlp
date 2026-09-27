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
    /// <summary>Reads Bentley objects only while the query collection is being enumerated.</summary>
    internal static class ComponentPropertyReader
    {
        internal static ComponentSnapshot Read(ulong id)
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null) throw new InvalidOperationException("没有活动模型。");
            var elementId = new ElementId(ref id);
            Element element = model.FindElementById(elementId);
            if (element == null) throw new InvalidOperationException("所选元素已不存在。");
            var snapshot = new ComponentSnapshot { ElementId = id };
            try { ReadGeometry(element, snapshot); }
            catch (Exception ex) { snapshot.ReadWarning = "几何读取失败：" + ex.Message; }
            try { ReadEc(element, snapshot); }
            catch (Exception ex) { snapshot.ReadWarning += " EC 读取失败：" + ex.Message; }
            return snapshot;
        }

        private static void ReadGeometry(Element element, ComponentSnapshot snapshot)
        {
            var modelInfo = Session.Instance.GetActiveDgnModel().GetModelInfo();
            double uorPerMm = modelInfo.UorPerMeter / 1000.0;
            if (uorPerMm <= 0) return;
            var com = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.GetElementByID64(checked((long)snapshot.ElementId));
            if (com == null) return;
            var range = com.Range;
            if (range.High.X >= range.Low.X)
            {
                snapshot.RangeXmm = (range.High.X - range.Low.X) * modelInfo.UorPerMaster / uorPerMm;
                snapshot.RangeYmm = (range.High.Y - range.Low.Y) * modelInfo.UorPerMaster / uorPerMm;
                snapshot.RangeZmm = (range.High.Z - range.Low.Z) * modelInfo.UorPerMaster / uorPerMm;
                snapshot.CenterZMm = (range.Low.Z + range.High.Z) * modelInfo.UorPerMaster / 2 / uorPerMm;
                snapshot.LengthMm = Math.Max(snapshot.RangeXmm.Value, Math.Max(snapshot.RangeYmm.Value, snapshot.RangeZmm.Value));
                snapshot.GeometrySource = "元素范围近似";
            }
            // Native curve geometry is used only for an open path. A closed profile is not a pipe axis.
            try
            {
                var chain = com.AsChainableElement();
                if (chain == null || chain.Length <= 0) return;
                var start = chain.StartPoint;
                var end = chain.EndPoint;
                double dx = start.X - end.X, dy = start.Y - end.Y, dz = start.Z - end.Z;
                if (Math.Sqrt(dx * dx + dy * dy + dz * dz) <= 1e-9) return;
                snapshot.StartX = start.X * modelInfo.UorPerMaster / uorPerMm;
                snapshot.StartY = start.Y * modelInfo.UorPerMaster / uorPerMm;
                snapshot.StartZ = start.Z * modelInfo.UorPerMaster / uorPerMm;
                snapshot.EndX = end.X * modelInfo.UorPerMaster / uorPerMm;
                snapshot.EndY = end.Y * modelInfo.UorPerMaster / uorPerMm;
                snapshot.EndZ = end.Z * modelInfo.UorPerMaster / uorPerMm;
                snapshot.LengthMm = chain.Length * modelInfo.UorPerMaster / uorPerMm;
                snapshot.CenterZMm = (snapshot.StartZ + snapshot.EndZ) / 2;
                snapshot.GeometrySource = "开放曲线";
            }
            catch { /* Cells and non-chain elements retain their range. */ }
        }

        private static void ReadEc(Element element, ComponentSnapshot snapshot)
        {
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                int bestScore = -1;
                foreach (IDgnECInstance instance in instances)
                {
                    // Copy every value here. Bentley instances must not outlive this enumeration.
                    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                    foreach (var property in instance.ClassDefinition.Properties(true))
                    {
                        string name = property.Name;
                        try
                        {
                            CaptureValue(instance[name], name, values);
                        }
                        catch { /* An inaccessible property does not hide the remaining values. */ }
                    }
                    string schema = instance.ClassDefinition.Schema.Name;
                    string className = instance.ClassDefinition.Name;
                    foreach (var pair in values)
                        snapshot.AllProperties.Add(new KeyValuePair<string, string>(schema + "." + className + "." + pair.Key, pair.Value));
                    int score = schema.StartsWith("OpenPlant", StringComparison.OrdinalIgnoreCase) ? 10 : 0;
                    if (className.StartsWith("PIPE", StringComparison.OrdinalIgnoreCase)) score += 3;
                    if (values.ContainsKey("OUTSIDE_DIAMETER")) score += 2;
                    if (score <= bestScore) continue;
                    bestScore = score;
                    snapshot.Schema = schema;
                    snapshot.ClassName = className;
                    snapshot.InstanceId = instance.InstanceId;
                    snapshot.Properties.Clear();
                    foreach (var pair in values) snapshot.Properties.Add(pair.Key, pair.Value);
                }
            }
        }
        private static void CaptureValue(IECPropertyValue value, string name, IDictionary<string, string> values)
        {
            if (value == null || value.IsNull) return;
            if (value.IsArray || value.IsStruct)
            {
                if (value.ContainedValues == null) return;
                foreach (IECPropertyValue child in value.ContainedValues)
                    CaptureValue(child, string.IsNullOrEmpty(child.AccessString) ? name : child.AccessString, values);
                return;
            }
            object native = value.NativeValue;
            string text = native == null ? value.XmlStringValue : Convert.ToString(native, CultureInfo.InvariantCulture);
            if (!string.IsNullOrWhiteSpace(text)) values[name] = text;
        }
    }
}
