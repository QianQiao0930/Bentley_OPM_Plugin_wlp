extern alias NativeOPM;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Bentley.Building.Mechanical.Components;
using Bentley.Building.Mechanical.ComponentLibrary.Supports;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>仅SSP_A1_NATIVE_TEST使用；OPM创建及编辑时重新调用原A1建模器。</summary>
    public sealed class A1NativeParametricComponent : Supports
    {
        private A1ClampPlan plan;
        public override void Setup()
        {
            try
            {
                int dn = BMECObject.GetIntValue("SSP_A1_DN");
                double angle = BMECObject.GetUnitlessDoubleValue("SSP_A1_OPENING");
                plan = A1ClampCalculator.Calculate(dn, false, null, angle, "");
                // Stock SupportLocation.Setup also initializes its host pipe and port data this way.
                if (!SetPipeDiameter()) throw new InvalidOperationException("A1原生组件无法初始化父管及端口数据。");
                SetSupportLength(plan.Row.D);
            }
            catch (Exception error)
            {
                SaveTrace(DateTimeOffset.Now.ToString("o") + " A1组件Setup失败\r\n" + error);
                throw;
            }
        }

        public override List<ElementHolder> Create3DElements()
        {
            var result = new List<ElementHolder>();
            var trace = new StringBuilder(DateTimeOffset.Now.ToString("o") + " A1原生组件几何回调\r\n");
            trace.AppendLine("DLL=" + typeof(A1NativeParametricComponent).Assembly.Location
                + "；MVID=" + typeof(A1NativeParametricComponent).Assembly.ManifestModule.ModuleVersionId);
            try
            {
                trace.AppendLine("阶段=读取A1参数");
                Setup();
                var model = Session.Instance.GetActiveDgnModel();
                trace.AppendLine("DN=" + plan.Row.Dn + "；UOR/mm=" + model.GetModelInfo().UorPerMeter / 1000.0);
                trace.AppendLine("阶段=重建A1螺杆及螺母");
                using (var cell = new CellHeaderElement(model, A1ClampCatalog.CellName,
                    DPoint3d.Zero, DMatrix3d.Identity,
                    A1ClampBuilder.Build(plan, DPoint3d.Zero, new DVector3d(1, 0, 0))))
                    result.Add(Extract(cell));
                // Same local origin/direction marker as the stock SupportLocation implementation.
                using (var app = new BMApplication())
                {
                    var marker = app.CreatePointStringElement(DPoint3d.Zero,
                        new DVector3d(-1, 0, 0), new DVector3d(0, 0, 1));
                    if (marker == null) throw new InvalidOperationException("无法创建A1原生方向标记。");
                    result.Add(marker);
                }
                SetTypeAndSymbology(ref result);
                trace.AppendLine("阶段=同步ISO点");
                var origin = BMECObject.Transform3d.Translation;
                NativeSupportData.Finite(origin.X); NativeSupportData.Finite(origin.Y); NativeSupportData.Finite(origin.Z);
                if (!BMECObject.SetDoubleValueFromUors("SUPPORT_POINT_X", origin.X)
                    || !BMECObject.SetDoubleValueFromUors("SUPPORT_POINT_Y", origin.Y)
                    || !BMECObject.SetDoubleValueFromUors("SUPPORT_POINT_Z", origin.Z))
                    throw new InvalidOperationException("A1原生组件无法更新ISO支撑点。");
                trace.AppendLine("成功；图形持有者=" + result.Count + "；变换=" + BMECObject.Transform3d);
                return result;
            }
            catch (Exception error)
            {
                trace.AppendLine(error.ToString());
                foreach (var element in result) element?.Dispose();
                throw;
            }
            finally
            {
                SaveTrace(trace.ToString());
            }
        }

        private static void SaveTrace(string trace)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(A1NativeTrialCommands.LogPath));
                File.WriteAllText(A1NativeTrialCommands.ComponentLogPath, trace, new UTF8Encoding(false));
            }
            catch (Exception error) { Bentley.DgnPlatformNET.NotificationManager.OutputPrompt("A1组件日志保存失败：" + error.Message); }
        }

        private static unsafe ElementHolder Extract(Element element)
        {
            // Reuse the SDK's descriptor bridge, then clone the holder into component ownership.
            // This temporary object is never created/serialized and has no DGN or EC relationships.
            using (var temporary = new BMECObject())
            fixed (byte* handle = element.ElementHandle)
            {
                temporary.SetNonParametricElement((NativeOPM::Bentley.DgnPlatform.EditElementHandle*)handle);
                var cache = BMECApi.Instance.GraphicsCache;
                uint id = temporary.LegacyGraphicsId;
                try
                {
                    var holder = cache.GetById(id);
                    if (holder == null) throw new InvalidOperationException("无法取得A1离线图形。");
                    var clone = holder.Clone() as ElementHolder;
                    if (clone == null) throw new InvalidOperationException("无法克隆A1离线图形。");
                    return clone;
                }
                finally { cache.Remove(id); }
            }
        }
    }
}
