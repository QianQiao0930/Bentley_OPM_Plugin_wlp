using System;

namespace SteelSectionProbe
{
    /// <summary>花篮螺栓总成参数；坐标约定与 AutoCAD 版一致：Y 为拉杆轴、X 为销轴、Z 为厚度。</summary>
    internal sealed class TurnbuckleParameters
    {
        /// <summary>公称规格（M10～M110）。</summary>
        internal int Size = 20;

        /// <summary>花篮螺母端面到卸扣外端头的间隙（mm）。</summary>
        internal double EndGapMm = 10.0;

        /// <summary>拉杆伸入 U 形叉口的长度（mm）。</summary>
        internal double StudProtrusionMm = 5.0;

        /// <summary>放置后绕竖轴旋转角（°）。</summary>
        internal double HeadingDegrees;
    }

    /// <summary>按 nominal 公式算出的实际尺寸（mm），字段含义见 AutoCAD 版 TurnbuckleSpec。</summary>
    internal sealed class TurnbuckleSpec
    {
        internal int Size;
        internal double D;
        internal double H;
        internal double h;
        internal double L;
        internal double B;
        internal double Thickness;
        internal double Rail;
        internal double BossWidth;
        internal double HexAcrossFlats;
        internal double Corner;
        internal double OpeningRadius;
        internal double Bore;
        internal bool RoundedStyle;

        internal double PinDiameter;
        internal double ClevisH;
        internal double Clevish;
        internal double ClevisB;
        internal double Leg;
        internal double ClevisThickness;
        internal double HeadHeight;
        internal double TopWidth;
        internal double InsideRadius;
        internal double PinClearance;
        internal double WasherThickness;
        internal double WasherOd;
        internal double PinOverhang;
        internal bool ClevisFullShoulder;

        internal double EndGap;
        internal double StudProtrusion;
        internal double StudExtension;

        internal double BodyLength
        {
            get { return H + 2.0 * Rail; }
        }

        internal double BossLength
        {
            get { return (L - H) / 2.0; }
        }

        internal double StudLength
        {
            get { return (L - h) / 2.0 + StudExtension; }
        }
    }
}
