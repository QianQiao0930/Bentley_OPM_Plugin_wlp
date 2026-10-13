using System;
using System.Globalization;
using System.Windows.Data;

namespace SteelSectionProbe
{
    /// <summary>仅将共用N3/N4页的现有标题转换为窄窗口标题与展示代号。</summary>
    internal sealed class SupportPageTitleConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            string title = value as string ?? "";
            bool doubleBracket = title.StartsWith("N4", StringComparison.Ordinal);
            if (Equals(parameter, "Code")) return doubleBracket ? "N4" : "N3";
            return doubleBracket ? "N4 双三角架" : "N3 单三角架";
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotSupportedException();
        }
    }
}
