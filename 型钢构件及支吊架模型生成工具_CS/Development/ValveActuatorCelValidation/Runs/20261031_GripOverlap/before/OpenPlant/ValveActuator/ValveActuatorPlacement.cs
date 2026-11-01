using System;
using System.Collections.Generic;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>Offers one immutable component to the official Topworks tool; never creates native relationships itself.</summary>
    internal static class ValveActuatorPlacement
    {
        // Match the earlier validation lifetime: the native tool can retain the supplied wrappers.
        private static readonly List<BMECObject> retained = new List<BMECObject>();
        private static BMECObject request;
        private static IPlacementTool ownedTool;
        private static string token;
        private static DgnModel model;
        private static DgnFile file;
        private static bool hostShuttingDown;
        internal static bool HasNativeObjects { get { return retained.Count > 0 || ActuatorCelGraphics.HasNativeTemplates; } }
        internal static bool IsActive { get { Refresh(); return request != null; } }

        internal static string Start(CelLibraryEntry selected)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            ActuatorCelGraphics.RequireContext();
            End();
            var activeModel = Session.Instance.GetActiveDgnModel();
            var activeFile = Session.Instance.GetActiveDgnFile();
            if (activeModel.IsReadOnly || activeFile.IsReadOnly || TransactionManager.IsUndoInProgress || BMECApi.Instance.DeferCommits)
                throw new InvalidOperationException("请使用可写三维模型，并结束当前撤销/重做或延迟提交。");
            if (retained.Count >= 16) throw new InvalidOperationException("本轮验证每进程最多启动 16 次，请正常退出 OPM 后重开。");

            var trace = new StringBuilder();
            try
            {
                var instance = BMECInstanceManager.Instance.CreateECInstance(ActuatorCelInstanceData.ClassName, true);
                if (instance == null) throw new InvalidOperationException("当前工作集缺少 SSP_CEL_VALVE_ACTUATOR，请更新本轮两份测试 Schema 后重启 OPM。");
                var asset = ActuatorCelAssetReader.Read(selected);
                string newToken = Guid.NewGuid().ToString("N");
                ActuatorCelInstanceData.Write(instance, asset, newToken);
                // Native import is checked before starting a tool; no model element is written.
                using (var check = ActuatorCelGraphics.Clone(asset)) { }
                var component = new BMECObject(instance, false);
                if (!component.IsParametric || !(component.Component is CelValveActuatorComponent)
                    || component.PlacementTool != "TopworksPlacementTool")
                {
                    component.Dispose();
                    throw new InvalidOperationException("工作集没有解析为 CEL 齿轮箱处理器及官方 TopworksPlacementTool。");
                }
                retained.Add(component);
                SelectionSetManager.EmptyAll();
                if (SelectionSetManager.NumSelected() != 0) throw new InvalidOperationException("无法清空旧选择集，请取消选择后重试。");
                request = component; token = newToken; model = activeModel; file = activeFile;
                trace.AppendLine("Class=" + instance.ClassDefinition.Name + "; Cell=" + asset.CellName + "; Source=" + asset.SourcePath);
                trace.AppendLine("ResourceSha256=" + asset.Hash + "; Bytes=" + asset.ByteCount + "; ResourceStoredInInstance=true");
                trace.AppendLine("DGN=" + file.GetFileName() + "; Model=" + model.GetModelInfo().Name + "; Token=" + token);
                trace.AppendLine("RelatedInstanceAssignedByPlugin=false; CreateCalledByPlugin=false; SerializeCalledByPlugin=false; FixedCelGeometry=true");
                string elapsed = WriteDuration.Measure(() => BMECApi.Instance.StartPlacement(component));
                Refresh();
                trace.AppendLine("PlacementRequestReturned=true; ToolStartDuration=" + elapsed + "; CompletedPlacementVerified=false");
                NotificationManager.OutputPrompt("请按官方工具提示点选阀门，调整方向并确认；右键结束。");
                return "已启动官方放置，请点选阀门；所选单元：" + asset.CellName + "。";
            }
            catch (Exception error)
            {
                trace.AppendLine("StartFailed=" + error);
                // Retain ownership if the native start threw after installing its tool.
                Refresh();
                throw;
            }
            finally { ValveActuatorLog.Write("place", trace.ToString()); }
        }

        internal static void Refresh()
        {
            if (hostShuttingDown || request == null) return;
            var current = BMECApi.Instance.CurrentPlacementTool;
            if (current != null && Owns(current))
            {
                if (!ReferenceEquals(ownedTool, current))
                {
                    Detach(); ownedTool = current;
                    ownedTool.OnEndPlacementEvent += PlacementEvent;
                }
                return;
            }
            // Before the first tool is observed, null can mean a queued installation.
            if (ownedTool == null && current == null) return;
            Clear(); // Another tool has taken over, or our observed tool has exited.
        }

        private static bool Owns(IPlacementTool candidate)
        {
            var obj = candidate.ECObject;
            return obj != null && obj.Instance != null && obj.Instance.ClassDefinition.Name == ActuatorCelInstanceData.ClassName
                && obj.GetStringValue("SSP_CEL_TOKEN") == token;
        }

        internal static void CheckContext()
        {
            Refresh();
            if (request != null && (!ReferenceEquals(model, Session.Instance.GetActiveDgnModel())
                || !ReferenceEquals(file, Session.Instance.GetActiveDgnFile()))) End();
        }

        internal static void End()
        {
            if (hostShuttingDown) return;
            Refresh();
            if (request == null) return;
            var current = BMECApi.Instance.CurrentPlacementTool;
            if (current == null || !Owns(current))
                throw new InvalidOperationException("官方放置工具尚未确认就绪，请在模型中右键结束后重试。");
            // Exit only the native tool carrying our unique request token; leave other tools alone.
            current.Exit();
            Clear();
        }

        private static void PlacementEvent(object sender, PlacementEventArgs args)
        {
            // This event reports an instance; it is not proof that the entire tool has ended.
            ValveActuatorLog.Write("native-placement-event", "Instance=" + (args == null || args.Instance == null ? "null" : args.Instance.InstanceId)
                + "; Token=" + token + "; NativeRelationsAndPersistenceRequireVerification=true");
        }
        private static void Detach()
        {
            if (ownedTool == null) return;
            ownedTool.OnEndPlacementEvent -= PlacementEvent;
            ownedTool = null;
        }
        private static void Clear() { Detach(); request = null; token = null; model = null; file = null; }
        internal static void OnHostShutdown()
        {
            // The host releases its tools during shutdown. Do not call a partially torn-down API.
            hostShuttingDown = true; request = null; ownedTool = null; token = null; model = null; file = null;
        }
    }
}
