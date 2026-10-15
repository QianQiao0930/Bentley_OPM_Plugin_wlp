using System;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>
    /// 耳轴确认落 OPM 自带类（单侧/双侧/弯头），参数化挂自定义 Builder 外形以保留滑动/旋转操作柄；
    /// ISO 走工作集已有 SUPP_TRUNNION / SUPP_ELBOW，引注写 ALIAS。
    /// </summary>
    internal static class NativeTrunnionPlacement
    {
        internal static void Create(NativePipeSupportRecipe recipe, IECInstance parent,
            Action<Element> attach, Action complete)
        {
            NativeSupportLog.Run(log =>
            {
                string tag = recipe.Vertical != null ? recipe.Vertical.Number : recipe.Elbow.AssemblyTag;
                var definition = NativePipeSupportDefinition.Create(recipe.Code, recipe.Dn, tag,
                    "L" + recipe.HandleLengthMm.ToString("0.###", CultureInfo.InvariantCulture));
                string json = NativePipeSupportRecipeCodec.Encode(recipe);
                string nativeClass = NativePipeSupportDefinition.StockTrunnionClass(recipe.Code);
                var instance = BMECInstanceManager.Instance.CreateECInstance(nativeClass, true);
                if (instance == null)
                    throw new InvalidOperationException("当前工作集缺少自带耳轴类 " + nativeClass + "。");
                Text(instance, "SSP_RECIPE", json);
                Text(instance, "ALIAS", definition.Label);
                Text(instance, "DESCRIPTION", definition.Description);
                Text(instance, "SPECIFICATION", parent["SPECIFICATION"].StringValue ?? "");
                WriteNominal(instance, parent, definition.Dn);
                WriteStockSizing(instance, recipe);
                double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
                DTransform3d placement, inverse;
                NativePipeSupportSource.PlacementFrame(recipe, scale, out placement, out inverse);
                log("耳轴类别=" + recipe.Code + "；自带类=" + nativeClass + "；参数化操作柄="
                    + (recipe.AllowManualEditHandles ? "开" : "关") + "；父构件="
                    + parent.ClassDefinition.Name + "/" + parent.InstanceId + "；引注=" + tag);
                Action<BMECObject> validate = support =>
                {
                    if (!support.IsParametric || support.Instance.ClassDefinition.Name != nativeClass
                        || support.Instance["ALIAS"].StringValue != definition.Label
                        || support.Instance["SSP_RECIPE"].StringValue != json)
                        throw new InvalidOperationException("耳轴自带类、参数化外形、引注或配方未保存。");
                };
                NativePipeSupportWriter.Create(instance, parent, placement, recipe.CenterMm,
                    null,
                    (support, element) =>
                    {
                        validate(support); attach(element);
                        NativePipeSupportStore.Write(element, new NativePipeSupportRecord {
                            Code = recipe.Code, Dn = recipe.Dn, NativeClass = nativeClass,
                            PipeInstanceId = parent.InstanceId, SupportInstanceId = support.Instance.InstanceId,
                            IsoTag = definition.Label, Description = definition.Description,
                            NativeName = support.Instance["NAME"].StringValue,
                            RecipeVersion = 1, RecipeJson = json,
                            Xmm = recipe.CenterMm[0], Ymm = recipe.CenterMm[1], Zmm = recipe.CenterMm[2] });
                    }, complete, log, validate, parametric: true, parentClassName: parent.ClassDefinition.Name);
            });
        }

        private static void WriteNominal(IECInstance instance, IECInstance parent, int dn)
        {
            NativeSupportData.RequireProperty(instance, "NOMINAL_DIAMETER");
            var nominal = instance.ClassDefinition.Properties(true).First(p => p.Name == "NOMINAL_DIAMETER");
            if (string.Equals(nominal.Type.Name, "string", StringComparison.OrdinalIgnoreCase))
                instance["NOMINAL_DIAMETER"].StringValue = dn.ToString(CultureInfo.InvariantCulture);
            else
            {
                try { instance["NOMINAL_DIAMETER"].DoubleValue = parent["NOMINAL_DIAMETER"].DoubleValue; }
                catch { instance["NOMINAL_DIAMETER"].DoubleValue = dn; }
            }
        }

        private static void WriteStockSizing(IECInstance instance, NativePipeSupportRecipe recipe)
        {
            if (recipe.Vertical != null)
            {
                TrySetDouble(instance, "TOTAL_HEIGHT", recipe.Vertical.LengthMm);
                TrySetDouble(instance, "SUPPORT_HEIGHT", recipe.Vertical.LengthMm);
                TrySetDouble(instance, "SUPPORT_DIAMETER", recipe.Vertical.TrunnionOd);
            }
            else if (recipe.Elbow != null)
            {
                TrySetDouble(instance, "BASE_LENGTH", recipe.Elbow.Parameters.ExtentMm);
                TrySetDouble(instance, "SUPPORT_DIAMETER", recipe.Elbow.TrunnionOdMm);
            }
        }

        private static void TrySetDouble(IECInstance instance, string name, double valueMm)
        {
            if (!instance.ClassDefinition.Properties(true).Any(p => p.Name == name)) return;
            if (double.IsNaN(valueMm) || double.IsInfinity(valueMm) || valueMm <= 0) return;
            var property = instance.ClassDefinition.Properties(true).First(p => p.Name == name);
            if (string.Equals(property.Type.Name, "string", StringComparison.OrdinalIgnoreCase))
                instance[name].StringValue = valueMm.ToString("0.###", CultureInfo.InvariantCulture);
            else instance[name].DoubleValue = valueMm;
        }

        private static void Text(IECInstance instance, string name, string value)
        { NativeSupportData.RequireProperty(instance, name); instance[name].StringValue = value; }
    }
}
