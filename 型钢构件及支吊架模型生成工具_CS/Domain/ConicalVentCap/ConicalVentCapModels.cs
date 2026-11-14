using System;

namespace SteelSectionProbe
{
    /// <summary>
    /// 锥形风帽（14K117-3 第 3 页构造图、第 5 页尺寸表）参数。
    /// 纯 C# 数值容器，单位 mm；局部原点在底部接口平面中心，+Z 向上。
    /// </summary>
    internal sealed class ConicalVentCapParameters
    {
        /// <summary>连接短管外径 D（mm），可取值 200～2500。</summary>
        internal double DiameterMm = 1250.0;

        /// <summary>壳板厚度 t（mm），大于 0 且不大于 3；板厚向内生成，内径 = D − 2t。</summary>
        internal double WallThicknessMm = 2.0;

        /// <summary>件⑦外焊折弯筋与件⑧内外锥折弯支架的组数，3～8。</summary>
        internal int SupportCount = 4;

        /// <summary>放置后绕竖轴旋转角（°）。</summary>
        internal double HeadingDegrees;
    }

    /// <summary>
    /// 按连接短管外径 D 求出的锥形风帽全部尺寸（mm）。
    /// 字段与 AutoCAD 版 ConicalVentCapDimensions 一一对应，便于逐项核对 IGES 尺寸。
    /// </summary>
    internal sealed class ConicalVentCapDimensions
    {
        /// <summary>连接短管外径 D；板厚向内，内径 = D − 2×板厚。</summary>
        internal double Diameter;

        /// <summary>外下锥下端直径（= D + 20）。</summary>
        internal double D1;

        /// <summary>外锥最大直径，也是模型总宽（= 1.9·D1）。</summary>
        internal double D2;

        /// <summary>内锥上端直径（= 1.2·D1）。</summary>
        internal double D3;

        /// <summary>外下锥下端的竖直段高度。</summary>
        internal double H;

        /// <summary>外上锥高度（= 0.7·D1）。</summary>
        internal double H1;

        /// <summary>外下锥高度（= 0.9·D1）。</summary>
        internal double H2;

        /// <summary>内上锥（雨帽）高度。</summary>
        internal double H3;

        /// <summary>内下锥（雨水锥）高度。</summary>
        internal double H4;

        /// <summary>连接短管高度。</summary>
        internal double H5;

        /// <summary>件⑧安装站位（图集值；非标规格为 null）。</summary>
        internal double? E;

        /// <summary>件⑧外侧站位（图集值；非标规格为 null）。</summary>
        internal double? F;

        /// <summary>件⑧中间跨长（图集值；非标规格为 null）。</summary>
        internal double? A;

        /// <summary>件⑧内侧腿夹角（图集值；非标规格为 null）。</summary>
        internal double? Phi;

        /// <summary>是否为图集表列规格。</summary>
        internal bool IsCatalog;

        /// <summary>是否为超出图集范围、按外推规则生成的规格。</summary>
        internal bool IsExtended;

        /// <summary>内、外锥的交汇高度 H + H2。</summary>
        internal double Eq
        {
            get { return H + H2; }
        }

        /// <summary>模型总高 H + H2 + H1。</summary>
        internal double Top
        {
            get { return H + H2 + H1; }
        }

        /// <summary>件⑧中间跨长 A；非标规格按末档比例外推。</summary>
        internal double SupportA
        {
            get { return A.HasValue ? A.Value : Math.Round(449.0 * (Diameter + 20.0) / 1270.0); }
        }

        /// <summary>件⑧内侧腿夹角；非标规格沿用末档 100.3°。</summary>
        internal double SupportPhi
        {
            get { return Phi.HasValue ? Phi.Value : 100.3; }
        }

        /// <summary>件⑧外侧站位 F；非标规格按末档比例外推。</summary>
        internal double SupportF
        {
            get { return F.HasValue ? F.Value : 540.0 * (Diameter + 20.0) / 1270.0; }
        }
    }
}
