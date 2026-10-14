using System;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal sealed class NativePipeSupportDefinition
    {
        internal const string NativeClass = "SUPPORT_LOCATION";
        internal string Code, Label, Description;
        internal int Dn;

        internal static NativePipeSupportDefinition Create(string code, int dn, string detail)
        {
            if (dn <= 0) throw new InvalidOperationException("出图DN无效。");
            string name;
            switch (code)
            {
                case "A1": name = "U-BOLT CLAMP"; break;
                case "U3": name = "BEARING U-BOLT"; break;
                case "A2": name = "STANDARD 2-BOLT CLAMP"; break;
                case "A22": name = "COLD 2-BOLT CLAMP"; break;
                case "A24": name = "COLD 4-BOLT CLAMP"; break;
                case "E1": name = "PIPE GUIDE"; break;
                case "K1": name = "PIPE STOP"; break;
                case "T4": name = "HOT INSULATED SHOE"; break;
                case "L2": name = "COLD PIPE SHOE"; break;
                default: throw new InvalidOperationException("未登记的管夹出图类别。");
            }
            // ASCII avoids the active ISO seed's missing CJK glyphs. Original Chinese records are untouched.
            string normalized=(detail??"").Replace("×","x").Replace("∠","L").Replace("φ","D").Replace("Φ","D").Replace("°","deg");
            string safe = new string(normalized.Where(c => c >= 32 && c <= 126).ToArray())
                .Replace(' ', '-').Replace('/', '-').Replace('"', '-');
            string label = code + "-DN" + dn.ToString(CultureInfo.InvariantCulture) + (safe.Length == 0 ? "" : "-" + safe);
            if (label.Length > 120) label = label.Substring(0, 120);
            return new NativePipeSupportDefinition { Code = code, Dn = dn, Label = label, Description = label + " " + name };
        }
    }

    internal sealed class NativePipeSupportRecord
    {
        public int Version = 1;
        public string Code, NativeClass, PipeInstanceId, SupportInstanceId, IsoTag, Description;
        public int Dn;
        public double Xmm, Ymm, Zmm;
    }
}
