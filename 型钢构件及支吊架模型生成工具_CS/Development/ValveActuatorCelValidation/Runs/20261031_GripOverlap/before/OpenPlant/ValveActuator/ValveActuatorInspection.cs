extern alias NativeOPM;
using System;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>Reads persisted instance data and valve relationships after the user completes the official operation.</summary>
    internal static class ValveActuatorInspection
    {
        internal static unsafe void Run()
        {
            var trace = new StringBuilder();
            try
            {
                if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
                ActuatorCelGraphics.RequireContext();
                if (ValveActuatorPlacement.IsActive) throw new InvalidOperationException("请先结束官方放置，再选择阀门或执行机构进行校核。");
                uint count = SelectionSetManager.NumSelected();
                if (count == 0 || count > 2) throw new InvalidOperationException("请选择活动模型内的阀门或执行机构（1～2 件）。");
                var model = Session.Instance.GetActiveDgnModel();
                for (uint index = 0; index < count; index++)
                {
                    Element element = null; DgnModelRef reference = null;
                    if (SelectionSetManager.GetElement(index, ref element, ref reference) != StatusInt.Success || element == null
                        || element.GetNativeDgnModelRef() != (IntPtr)DgnModelRef.GetNativeDgnModelRefP(model, false))
                        throw new InvalidOperationException("仅校核活动模型内的元素。");
                    var instance = BMECApi.Instance.LoadInstanceWithAllRelationships(
                        (NativeOPM::Bentley.DgnPlatform.ElementRefBase*)element.GetNativeElementRef(),
                        (NativeOPM::Bentley.DgnPlatform.DgnModelRef*)element.GetNativeDgnModelRef());
                    trace.AppendLine("Element=" + (ulong)element.ElementId);
                    if (instance == null) { trace.AppendLine("NativeInstance=none"); continue; }
                    Describe(instance, trace);
                    Relations(instance, true, trace); Relations(instance, false, trace);
                }
                NotificationManager.OutputPrompt("校核完成，日志位于 %LOCALAPPDATA%\\SteelSectionProbe\\logs\\ValveActuator。");
            }
            catch (Exception error)
            {
                trace.AppendLine("InspectionFailed=" + error);
                NotificationManager.OutputPrompt("执行机构校核失败：" + error.Message);
            }
            finally { ValveActuatorLog.Write("inspect", trace.ToString()); }
        }
        private static void Describe(IECInstance instance, StringBuilder trace)
        {
            trace.AppendLine("Class=" + instance.ClassDefinition.Name + "; Instance=" + instance.InstanceId);
            using (var component = new BMECObject(instance))
                trace.AppendLine("IsParametric=" + component.IsParametric + "; Transform=" + component.Transform3d
                    + "; Component=" + (component.Component == null ? "null" : component.Component.GetType().FullName));
            if (instance.ClassDefinition.Name != ActuatorCelInstanceData.ClassName) return;
            var asset = ActuatorCelInstanceData.Read(instance);
            trace.AppendLine("PersistedCelDataVerified=true; Cell=" + asset.CellName + "; ResourceSha256=" + asset.Hash
                + "; Bytes=" + asset.ByteCount + "; SourceForInformationOnly=" + asset.SourcePath);
            foreach (string name in ActuatorCelInstanceData.SizeFields)
                trace.AppendLine("NativeParameter=" + name + "; XmlValue=" + instance[name].XmlStringValue);
            trace.AppendLine("NativeParameter=ANGLE; XmlValue=" + instance["ANGLE"].XmlStringValue);
            trace.AppendLine("NativeParameter=HANDLE_OFFSET; XmlValue=" + instance["HANDLE_OFFSET"].XmlStringValue);
        }
        private static void Relations(IECInstance instance, bool forward, StringBuilder trace)
        {
            var related = BMECApi.Instance.GetRelatedInstances(instance, "VALVE_HAS_VALVE_OPERATING_DEVICE",
                forward ? "VALVE_OPERATING_DEVICE" : "PIPING_COMPONENT", forward, true, true);
            string label = forward ? "ForwardOperatorCount" : "ReverseParentCount";
            trace.AppendLine(label + "=" + (related == null ? "unavailable" : related.Count.ToString()));
            if (related == null) return;
            foreach (IECInstance item in related) Describe(item, trace);
        }
    }
}
