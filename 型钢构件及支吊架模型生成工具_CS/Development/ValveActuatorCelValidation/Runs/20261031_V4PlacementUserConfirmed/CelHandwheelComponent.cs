using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Bentley.Building.Mechanical.ComponentLibrary.ValveOperator;
using Bentley.Building.Mechanical.Components;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;

namespace ActuatorCallbackCheck
{
    /// <summary>Equivalent to the pipe-clamp graphics callback: remain parametric, supply our own 3D.</summary>
    public sealed class CelHandwheelComponent : Handwheel
    {
        // Keep inherited Handwheel.Setup and all inherited native placement behavior.
        // Only the 3D body is overridden; no SetNonParametricElement on this component.
        public override List<ElementHolder> Create3DElements()
        {
            var trace = new StringBuilder();
            trace.AppendLine("Route=parametric Handwheel.Create3DElements override; Version=4; Placement=official Topwork tool");
            trace.AppendLine("Assembly=" + typeof(CelHandwheelComponent).Assembly.Location
                + "; MVID=" + typeof(CelHandwheelComponent).Assembly.ManifestModule.ModuleVersionId);
            try
            {
                if (BMECObject == null || BMECObject.GetIntValue("SSP_CEL_VERSION") != 1)
                    throw new InvalidOperationException("CEL 手轮缺少受支持的资源版本。");
                trace.AppendLine("Instance=" + BMECObject.Instance.InstanceId + "; Transform=" + BMECObject.Transform3d);
                var result = new List<ElementHolder> { CelResource.CloneForActiveModel() };
                trace.AppendLine("CallbackResult=CEL geometry clone; StockHandwheelGeometryCalled=false; ResourceSha256=" + CelResource.Hash);
                return result;
            }
            catch (Exception error) { trace.AppendLine("CallbackFailed=" + error); throw; }
            finally { TraceLog.Save("callback", trace.ToString()); }
        }
    }

    internal static class CelResource
    {
        internal const string CellName = "气动执行-DN800";
        internal const string ClassName = "SSP_CEL_HAND_WHEEL";
        internal const string Hash = "4DD17E6A4F44542380CB82DBCC60A32D1EA836DD99EA1987575F84458275FF6C";
        private sealed class TemplateContext
        {
            internal DgnFile File;
            internal DgnModel Model;
            internal string FileName;
            internal ElementHolder Template;
        }
        // Retain context wrappers: a closed/reopened document must not match merely
        // because the OS reused the old native model pointer.
        private static readonly List<TemplateContext> templates = new List<TemplateContext>();
        private static string resourcePath;

        internal static void RequireContext()
        {
            var model = Session.Instance.GetActiveDgnModel();
            if (!Utilities.IsMicroStationMainThread || model == null || !model.Is3d)
                throw new InvalidOperationException("CEL 几何回调仅支持活动三维模型的宿主主线程。");
            // Source library is 1000 UOR/mm. Restrict the first native-import experiment
            // to the same resolution; never silently guess another scale.
            if (Math.Abs(model.GetModelInfo().UorPerMeter - 1000000.0) > 0.001)
                throw new InvalidOperationException("本轮仅验证 1000000 UOR/m 的三维模型。");
        }

        private static string ExtractResource()
        {
            if (resourcePath != null) return resourcePath;
            string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "SteelSectionProbe", "resources", "ActuatorCallbackCheck", Hash);
            Directory.CreateDirectory(folder);
            string path = Path.Combine(folder, "actuator.cel");
            if (!File.Exists(path))
            {
                using (var source = typeof(CelResource).Assembly.GetManifestResourceStream("ActuatorCel"))
                {
                    if (source == null) throw new InvalidOperationException("验证 DLL 内缺少 CEL 资源。");
                    using (var target = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) source.CopyTo(target);
                }
            }
            using (var stream = File.OpenRead(path))
            using (var hash = SHA256.Create())
                if (BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "") != Hash)
                    throw new InvalidOperationException("固定版本 CEL 资源哈希不一致，未覆盖现有文件。");
            resourcePath = path;
            return path;
        }

        internal static unsafe ElementHolder CloneForActiveModel()
        {
            RequireContext();
            var model = Session.Instance.GetActiveDgnModel();
            var file = Session.Instance.GetActiveDgnFile();
            ElementHolder template = null;
            foreach (var context in templates)
                if (ReferenceEquals(context.File, file) && ReferenceEquals(context.Model, model) && context.FileName == file.GetFileName())
                {template = context.Template; break;}
            if (template == null)
            {
                if (templates.Count >= 8) throw new InvalidOperationException("验证模板已达到 8 个文档上下文，请退出 OPM 释放后重开。");
                using (var app = new BMApplication())
                {
                    var descriptor = app.GetCellElement(ExtractResource(), CellName);
                    if (descriptor == null) throw new InvalidOperationException("原生 GetCellElement 未返回 CEL 几何。");
                    template = new ElementHolder(descriptor);
                    template.SetGraphicsType(BMdGraphicsType.bmdGraphicsTypeEdge, false);
                    templates.Add(new TemplateContext {File=file, Model=model, FileName=file.GetFileName(), Template=template});
                }
            }
            var clone = template.Clone() as ElementHolder;
            if (clone == null) throw new InvalidOperationException("CEL 原生模板克隆失败。");
            return clone;
        }
    }

    internal static class TraceLog
    {
        internal static string LastFile;
        internal static void Save(string stage, string text)
        {
            try
            {
                string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "logs", "ActuatorCallbackCheck");
                Directory.CreateDirectory(folder);
                LastFile = Path.Combine(folder, DateTime.Now.ToString("yyyyMMdd_HHmmss_fff") + "_" + stage + "_" + Guid.NewGuid().ToString("N").Substring(0,8) + ".log");
                File.WriteAllText(LastFile, DateTimeOffset.Now.ToString("o") + "\r\n" + text, new UTF8Encoding(false));
            }
            catch (Exception error) {NotificationManager.OutputPrompt("执行机构验证日志保存失败：" + error.Message);}
        }
    }
}
