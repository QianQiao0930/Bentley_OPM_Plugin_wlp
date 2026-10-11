using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>
    /// 水龙柜尺寸均为毫米；基点为底部前侧中心，正面朝局部 −Y。
    /// </summary>
    internal sealed class HoseCabinetParameters
    {
        internal double WidthMm { get; set; } = 550;
        internal double DepthMm { get; set; } = 160;
        internal double HeightMm { get; set; } = 1200;
        internal double LowerHeightMm { get; set; } = 550;
        internal double HeadingDegrees
        {
            get; set;
        }
        internal string ExtinguisherModel { get; set; } = "MFZ/ABC4";
        internal int ExtinguisherQuantity { get; set; } = 2;
        internal bool WithEquipment { get; set; } = true;
    }

    internal sealed class HoseCabinetPlan
    {
        internal HoseCabinetParameters Parameters
        {
            get; set;
        }
        internal FireExtinguisherRecipe Interior
        {
            get; set;
        }
        internal List<double> BottleCentersMm { get; set; } = new List<double>();
        internal double ReelCenterXmm
        {
            get; set;
        }
        internal double ReelCenterZmm
        {
            get; set;
        }
        internal double ReelFrontYmm
        {
            get; set;
        }
    }

    /// <summary>
    /// 与原 Python BomJson 的字段名保持兼容。
    /// </summary>
    internal sealed class HoseBomRow
    {
        public int Number
        {
            get; set;
        }
        public string Code
        {
            get; set;
        }
        public string Name
        {
            get; set;
        }
        public string Material
        {
            get; set;
        }
        public string Specification
        {
            get; set;
        }
        public string Unit
        {
            get; set;
        }
        public int Quantity
        {
            get; set;
        }
    }

    internal sealed class HoseCabinetSummary
    {
        public string Specification
        {
            get; set;
        }
        public string ExtinguisherModel
        {
            get; set;
        }
        public int CabinetCount
        {
            get; set;
        }
        public int ExtinguisherCount
        {
            get; set;
        }
        public int ActualExtinguisherCount
        {
            get; set;
        }
    }

    internal sealed class HoseCabinetSnapshot
    {
        internal List<FireCabinetRecord> Records { get; set; } = new List<FireCabinetRecord>();
        internal List<HoseCabinetSummary> Summary { get; set; } = new List<HoseCabinetSummary>();
        internal List<HoseBomRow> Materials { get; set; } = new List<HoseBomRow>();
        internal int TotalCabinetCount
        {
            get; set;
        }
        internal int TotalExtinguisherCount
        {
            get; set;
        }
        internal int TotalActualExtinguisherCount
        {
            get; set;
        }
    }
    internal sealed class HoseHelixPath
    {
        internal List<double[]> Poles { get; } = new List<double[]>();
        internal List<double> Knots { get; } = new List<double> { 0, 0, 0, 0 };
        internal double[] StartTangent
        {
            get; set;
        }
    }

}
