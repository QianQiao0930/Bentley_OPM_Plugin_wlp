using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>A1/A2业务编号；材料代码用于编号，不推断材质或创建隔离层。</summary>
    internal static class PipeClampNumbering
    {
        internal const string DefaultMaterialCode = "C1";

        internal static string NormalizeMaterialCode(string value)
        {
            string code = (value ?? "").Trim().ToUpperInvariant();
            if (code.Length == 0) throw new InvalidOperationException("材料代码不能为空。");
            foreach (char ch in code)
                if (!(ch >= 'A' && ch <= 'Z') && !(ch >= '0' && ch <= '9'))
                    throw new InvalidOperationException("材料代码只能包含英文字母和数字，例如C1、S。");
            return code;
        }

        internal static string Build(string type, int dn, string materialCode)
        {
            return type + "-DN" + dn.ToString(CultureInfo.InvariantCulture) + "-" + NormalizeMaterialCode(materialCode);
        }
    }
}
