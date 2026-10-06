using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
namespace SteelSectionProbe
{
    internal sealed class SpiralStairBuildResult
    {
        internal readonly List<Element> Elements=new List<Element>();
        internal readonly List<KeyValuePair<Element,HandrailPlan>> Railings=new List<KeyValuePair<Element,HandrailPlan>>();
    }
}
