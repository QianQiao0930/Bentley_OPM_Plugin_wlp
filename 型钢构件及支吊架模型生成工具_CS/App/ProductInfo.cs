using System.Reflection;

namespace SteelSectionProbe
{
    /// <summary>
    /// 首页与作者页共享的公开产品信息，版本读取程序集唯一来源。
    /// </summary>
    internal static class ProductInfo
    {
        internal const string AuthorName = "魏";
        internal const string AuthorEmail = "yo196544wobi@163.com";

        internal static string DisplayVersion
        {
            get
            {
                Assembly assembly = typeof(ProductInfo).Assembly;
                var version = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>();
                return "V" + (version == null ? assembly.GetName().Version.ToString(3) : version.InformationalVersion);
            }
        }
    }
}
