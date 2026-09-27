using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal sealed class ComponentSnapshot
    {
        internal ulong ElementId;
        internal string Schema;
        internal string ClassName;
        internal string InstanceId;
        internal readonly Dictionary<string, string> Properties = new Dictionary<string, string>();
        internal readonly List<KeyValuePair<string, string>> AllProperties = new List<KeyValuePair<string, string>>();
        internal double? StartX, StartY, StartZ, EndX, EndY, EndZ;
        internal double? LengthMm, CenterXmm, CenterYmm, CenterZMm;
        internal double? RangeXmm, RangeYmm, RangeZmm;
        internal string GeometrySource;
        internal string ReadWarning;
    }
}
