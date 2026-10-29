using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal enum EquipmentColorMode { ByLevel, CustomRgb, KeepOriginal }

    internal sealed class EquipmentAppearanceOptions
    {
        internal uint TargetLevelId;
        internal string TargetLevelName;
        internal EquipmentColorMode ColorMode;
        // 0xRRGGBB，使用 COM 时转换成 OLE RGB，再由宿主生成内部颜色值。
        internal uint Rgb = 0x7FA37C;

        internal static uint ParseRgb(string text)
        {
            string value = (text ?? "").Trim();
            if (value.StartsWith("#", StringComparison.Ordinal)) value = value.Substring(1);
            uint rgb;
            if (value.Length != 6 || !uint.TryParse(value, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out rgb))
                throw new InvalidOperationException("颜色请填写六位色值，例如 #7FA37C。");
            return rgb;
        }

        internal string ColorDescription
        {
            get { return ColorMode == EquipmentColorMode.ByLevel ? "颜色随层" :
                ColorMode == EquipmentColorMode.KeepOriginal ? "保持原色" : "颜色 #" + Rgb.ToString("X6"); }
        }
    }

    internal sealed class EquipmentLevelChoice
    {
        public uint Id { get; set; }
        public string Name { get; set; }
        public bool IsWritable { get; set; }
        public string Availability { get; set; }
        public string ColorHex { get; set; }
        public string DisplayName { get { return Name + (IsWritable ? "" : " · " + Availability); } }
        public override string ToString() { return DisplayName; }
    }

    internal sealed class EquipmentLevelProgress
    {
        internal string Stage;
        internal string Detail;
        internal int Completed;
        internal int Total;
        internal long ElapsedMilliseconds;
    }
}
