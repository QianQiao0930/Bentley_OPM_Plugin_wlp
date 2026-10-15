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
    public sealed partial class A1NativeParametricComponent : Supports
    {
        public override List<ElementHolder> Create3DElements()
        {
            var result = new List<ElementHolder>();
            var trace = new StringBuilder(DateTimeOffset.Now.ToString("o") + " A1原生组件几何回调\r\n");
            trace.AppendLine("DLL=" + typeof(A1NativeParametricComponent).Assembly.Location
                + "；MVID=" + typeof(A1NativeParametricComponent).Assembly.ManifestModule.ModuleVersionId);
            try
            {
                trace.AppendLine("阶段=读取A1参数");
                PrepareGraphics();
                var model = Session.Instance.GetActiveDgnModel();
                trace.AppendLine("DN=" + plan.Row.Dn + "；UOR/mm=" + model.GetModelInfo().UorPerMeter / 1000.0);
                trace.AppendLine("阶段=重建A1螺杆及螺母");
                using (var cell = new CellHeaderElement(model, A1ClampCatalog.CellName,
                    DPoint3d.Zero, DMatrix3d.Identity,
                    A1ClampBuilder.Build(plan, DPoint3d.Zero, new DVector3d(1, 0, 0))))
                    result = NativeParametricSupportGraphics.Create(cell, BMECObject);
                trace.AppendLine("外观=保留原Builder分件颜色；原生三维Edge分类已设置");
                trace.AppendLine("阶段=同步ISO点");
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

    }
}
