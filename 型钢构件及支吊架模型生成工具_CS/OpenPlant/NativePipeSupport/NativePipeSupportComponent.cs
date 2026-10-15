using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Bentley.Building.Mechanical.Components;
using Bentley.Building.Mechanical.ComponentLibrary.Supports;

namespace SteelSectionProbe
{
    /// <summary>管夹及耳轴共用原生Support处理器；保留建模配方以供宿主编辑/重生成。</summary>
    public sealed partial class NativePipeSupportComponent : Supports
    {
        public override List<ElementHolder> Create3DElements()
        {
            var trace = new StringBuilder(DateTimeOffset.Now.ToString("o") + " 正式支吊架原生几何回调\r\n");
            trace.AppendLine("DLL=" + typeof(NativePipeSupportComponent).Assembly.Location + "；MVID="
                + typeof(NativePipeSupportComponent).Assembly.ManifestModule.ModuleVersionId);
            List<ElementHolder> result = null;
            try
            {
                PrepareGraphics();
                trace.AppendLine("类别=" + recipe.Code + "；DN=" + recipe.Dn + "；配方版本=" + recipe.Version
                    + "；手动操作柄=" + (recipe.AllowManualEditHandles ? "开" : "关（弯头耳轴固定位）"));
                using (var local = NativePipeSupportRecipeGraphics.BuildLocal(recipe))
                    result = NativeParametricSupportGraphics.Create(local, BMECObject, recipe.AllowManualEditHandles);
                trace.AppendLine("外观=保留原Builder分件颜色；原生三维Edge分类已设置");
                if (!recipe.AllowManualEditHandles) trace.AppendLine("弯头耳轴：未设操作长度、无方向标记；父弯头随动保留");
                trace.AppendLine("成功；ISO点已同步；图形持有者=" + result.Count + "；变换=" + BMECObject.Transform3d);
                return result;
            }
            catch (Exception error)
            {
                trace.AppendLine(error.ToString());
                if (result != null) foreach (var holder in result) holder?.Dispose();
                throw;
            }
            finally { SaveTrace(trace.ToString()); }
        }

        private static void SaveTrace(string trace)
        {
            try
            {
                string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SteelSectionProbe", "logs", "NativePipeSupport");
                Directory.CreateDirectory(folder);
                File.WriteAllText(Path.Combine(folder, "component-latest.log"), trace, new UTF8Encoding(false));
            }
            catch (Exception error) { Bentley.DgnPlatformNET.NotificationManager.OutputPrompt("管夹组件日志保存失败：" + error.Message); }
        }
    }
}
