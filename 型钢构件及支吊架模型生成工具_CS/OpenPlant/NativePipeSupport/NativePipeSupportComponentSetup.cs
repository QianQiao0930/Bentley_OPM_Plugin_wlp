using System;

namespace SteelSectionProbe
{
    public sealed partial class NativePipeSupportComponent
    {
        private NativePipeSupportRecipe recipe;

        // BMECObject.Init 在构造期就会调用 Setup；自带耳轴类上可能尚无 SSP_RECIPE
        //（旧件、宿主自带放置、或属性尚未可读）。此处不得抛错，否则会一直弹 FATAL ERROR。
        public override void Setup()
        {
            recipe = null;
            try
            {
                string json = ReadRecipeJson();
                if (string.IsNullOrWhiteSpace(json)) return;
                recipe = NativePipeSupportRecipeCodec.Decode(json);
            }
            catch (Exception error)
            {
                recipe = null;
                SaveTrace(DateTimeOffset.Now.ToString("o") + " 正式支吊架Setup跳过无效配方\r\n" + error);
            }
        }

        internal void PrepareGraphics()
        {
            Setup();
            if (recipe == null)
                throw new InvalidOperationException("原生支吊架缺少建模配方，请用本插件重新放置该耳轴/管夹。");
            // 父构件/端口必须初始化，随动依赖此关联；弯头耳轴不再设置操作长度以免出现移动柄。
            if (!SetPipeDiameter()) throw new InvalidOperationException("正式支吊架生成几何时无法初始化父构件及端口。");
            if (recipe.AllowManualEditHandles) SetSupportLength(recipe.HandleLengthMm);
        }

        private string ReadRecipeJson()
        {
            try
            {
                string value = BMECObject.GetStringValue("SSP_RECIPE");
                if (!string.IsNullOrWhiteSpace(value)) return value;
            }
            catch { }
            return null;
        }
    }
}
