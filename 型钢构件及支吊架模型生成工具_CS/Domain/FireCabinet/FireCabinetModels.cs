using System.Collections.Generic;
using System.Runtime.Serialization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 灭火器箱选型及绕世界竖轴的放置角度。
    /// </summary>
    internal sealed class FireCabinetParameters
    {
        internal string ExtinguisherType { get; set; } = "干粉灭火器";
        internal int Capacity { get; set; } = 2;
        internal string BoxKey { get; set; } = "XMDDG12";
        internal double HeadingDegrees
        {
            get; set;
        }
    }

    /// <summary>
    /// XMDDG 翻盖式箱体规格，尺寸单位为毫米。
    /// </summary>
    internal sealed class FireCabinetPreset
    {
        internal string Key
        {
            get; set;
        }
        internal double WidthMm
        {
            get; set;
        }
        internal double DepthMm
        {
            get; set;
        }
        internal double HeightMm
        {
            get; set;
        }
        internal double BodyHeightMm
        {
            get; set;
        }
        internal double MidHeightMm
        {
            get; set;
        }
        internal double LidHeightMm
        {
            get; set;
        }
        internal double LoadN
        {
            get; set;
        }
        internal double TestCylinderDiameterMm
        {
            get; set;
        }
        public override string ToString()
        {
            return Key;
        }
    }

    /// <summary>
    /// 纯计算结果；外观模型与实际选型分别记录，避免替代规格进入采购数量。
    /// </summary>
    internal sealed class FireCabinetPlan
    {
        internal FireCabinetParameters Parameters
        {
            get; set;
        }
        internal FireCabinetPreset Box
        {
            get; set;
        }
        internal FireExtinguisherRecipe Interior
        {
            get; set;
        }
        internal string CapacityUnit
        {
            get; set;
        }
        internal string ExtinguisherLabel
        {
            get; set;
        }
        internal double HalfSeparationMm
        {
            get; set;
        }
    }

    /// <summary>
    /// 嵌入的灭火器毫米几何配方，由迁移时的 Python 纯函数导出。
    /// </summary>
    [DataContract]
    internal sealed class FireExtinguisherRecipe
    {
        [DataMember]
        public int Capacity
        {
            get; set;
        }
        [DataMember]
        public string Model
        {
            get; set;
        }
        [DataMember]
        public string CellName
        {
            get; set;
        }
        [DataMember]
        public double BodyDiameterMm
        {
            get; set;
        }
        [DataMember]
        public double TotalHeightMm
        {
            get; set;
        }
        [DataMember]
        public double HoseLengthMm
        {
            get; set;
        }
        [DataMember]
        public FireGeometryPart[] Parts
        {
            get; set;
        }
    }

    /// <summary>
    /// 圆锥、斜盒、圆环、圆角瓶身或软管的毫米尺寸。
    /// </summary>
    [DataContract]
    internal sealed class FireGeometryPart
    {
        [DataMember]
        public string Kind
        {
            get; set;
        }
        [DataMember]
        public string Name
        {
            get; set;
        }
        [DataMember]
        public double[] Start
        {
            get; set;
        }
        [DataMember]
        public double[] End
        {
            get; set;
        }
        [DataMember]
        public double StartRadiusMm
        {
            get; set;
        }
        [DataMember]
        public double EndRadiusMm
        {
            get; set;
        }
        [DataMember]
        public double[] Center
        {
            get; set;
        }
        [DataMember]
        public double[] Size
        {
            get; set;
        }
        [DataMember]
        public double TiltDegrees
        {
            get; set;
        }
        [DataMember]
        public double RadiusMm
        {
            get; set;
        }
        [DataMember]
        public double FilletMm
        {
            get; set;
        }
        [DataMember]
        public double BottomMm
        {
            get; set;
        }
        [DataMember]
        public double TopMm
        {
            get; set;
        }
        [DataMember]
        public double MajorRadiusMm
        {
            get; set;
        }
        [DataMember]
        public double MinorRadiusMm
        {
            get; set;
        }
        [DataMember]
        public int[] Color
        {
            get; set;
        }
        [DataMember]
        public double[][] Points
        {
            get; set;
        }
    }

    internal sealed class FireCabinetRecord
    {
        public string ModelName
        {
            get; set;
        }
        public string ElementId
        {
            get; set;
        }
        public Dictionary<string, object> Properties
        {
            get; set;
        }
    }

    internal sealed class FireCabinetSummary
    {
        public string BoxModel
        {
            get; set;
        }
        public string ExtinguisherModel
        {
            get; set;
        }
        public int BoxCount
        {
            get; set;
        }
        public int ExtinguisherCount
        {
            get; set;
        }
        public int InteriorModelCount
        {
            get; set;
        }
    }

    internal sealed class FireCabinetSnapshot
    {
        public List<FireCabinetRecord> Records { get; set; } = new List<FireCabinetRecord>();
        public List<FireCabinetSummary> Summary { get; set; } = new List<FireCabinetSummary>();
        public int TotalBoxCount
        {
            get; set;
        }
        public int TotalExtinguisherCount
        {
            get; set;
        }
        public int TotalInteriorModelCount
        {
            get; set;
        }
    }
}
