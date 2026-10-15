using System;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal sealed class NativePipeSupportDefinition
    {
        internal const string NativeClass = "SSP_PIPE_CLAMP";
        // Native NAME remains a business identity. Only marked objects export ALIAS as IE_TAG.
        internal const string DeviceTypeCode = "SSPPC";
        /// <summary>历史自定义耳轴类；新放置改为下方自带类，旧件不迁移。</summary>
        internal const string TrunnionClass = "SSP_TRUNNION", TrunnionDeviceTypeCode = "SSPTR";
        internal const string StockSingleTrunnionClass = "SINGLE_PIPE_TRUNNION";
        internal const string StockDoubleTrunnionClass = "DOUBLE_PIPE_TRUNNION";
        internal const string StockElbowTrunnionClass = "SIMPLE_ELBOW_SUPPORT";
        internal string Code, Label, Description;
        internal int Dn;

        /// <summary>立管/弯头耳轴落 OPM 自带类，以复用 SUPP_TRUNNION / SUPP_ELBOW 图例。</summary>
        internal static string StockTrunnionClass(string code)
        {
            switch (code)
            {
                case "F6": case "F10": return StockSingleTrunnionClass;
                case "F7": return StockDoubleTrunnionClass;
                case "F2": case "F2-HE": case "F4": case "F5": return StockElbowTrunnionClass;
                default: throw new InvalidOperationException("未登记的耳轴自带类映射。");
            }
        }

        internal static bool IsStockTrunnionClass(string className)
        {
            return className == StockSingleTrunnionClass || className == StockDoubleTrunnionClass
                || className == StockElbowTrunnionClass;
        }

        internal static bool IsStockElbowTrunnionClass(string className)
        { return className == StockElbowTrunnionClass; }

        internal static NativePipeSupportDefinition Create(string code, int dn, string assemblyTag, string detail)
        {
            if (dn <= 0) throw new InvalidOperationException("出图DN无效。");
            if (string.IsNullOrWhiteSpace(assemblyTag)) throw new InvalidOperationException("管架编号为空，不能生成ISO引注。");
            if (assemblyTag.Any(c => char.IsControl(c) || c == '$'))
                throw new InvalidOperationException("单件管架编号不能包含控制字符或ISO换行符$。");
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
                case "F6": case "F7": name = "RISER TRUNNION"; break;
                case "F10": name = "RISER EAR PLATE"; break;
                case "F2": case "F2-HE": case "F4": case "F5": name = "ELBOW TRUNNION"; break;
                default: throw new InvalidOperationException("未登记的管夹出图类别。");
            }
            // Only the BOM description is normalized. The visible tag is exactly the material AssemblyTag.
            string normalized=(detail??"").Replace("×","x").Replace("∠","L").Replace("φ","D").Replace("Φ","D").Replace("°","deg");
            string safe = new string(normalized.Where(c => c >= 32 && c <= 126).ToArray())
                .Replace(' ', '-').Replace('/', '-').Replace('"', '-');
            string label = code + "-DN" + dn.ToString(CultureInfo.InvariantCulture) + (safe.Length == 0 ? "" : "-" + safe);
            if (label.Length > 120) label = label.Substring(0, 120);
            return new NativePipeSupportDefinition { Code = code, Dn = dn, Label = assemblyTag, Description = label + " " + name };
        }
    }

    internal sealed class NativePipeSupportRecord
    {
        public int Version = 1;
        public string Code, NativeClass, PipeInstanceId, SupportInstanceId, IsoTag, Description, NativeName;
        public int Dn;
        public int RecipeVersion;
        /// <summary>自带类无 SSP_RECIPE 属性时，完整配方改存根元素记录；旧记录可空。</summary>
        public string RecipeJson;
        public double Xmm, Ymm, Zmm;
    }
}
