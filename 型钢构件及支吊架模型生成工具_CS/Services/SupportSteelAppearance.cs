using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    /// <summary>仅支吊架结构钢件使用；紧固件、保温、设备和普通建模模块不使用。</summary>
    internal static class SupportSteelAppearance
    {
        // 修改这三个值并重新编译，即可统一调整新生成支吊架钢件的颜色。
        internal const byte Red=127,Green=163,Blue=124;
        internal static uint Color
        {
            get { return DgnColorMap.CreateElementColor(new RgbColorDef(Red,Green,Blue),
                null,null,Session.Instance.GetActiveDgnFile()); }
        }
        internal static Element Apply(Element element)
        {
            var setter=new ElementPropertiesSetter();setter.SetColor(Color);
            if(!setter.Apply(element))throw new InvalidOperationException("支吊架钢构件颜色设置失败。");
            return element;
        }
    }
}
