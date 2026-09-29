using System;

namespace SteelSectionProbe
{
    /// <summary>A24 表 1 相对 A22 新增的孔距 F；其余尺寸行与 A22 相同。</summary>
    internal static class A24ClampCatalog
    {
        internal const string SupportType="A24-[保冷管用4螺栓管夹]";
        internal const string SupportCode="A24_COLD_4BOLT_CLAMP";
        internal const string CellName="A24_COLD_4BOLT_CLAMP";
        private static readonly double[] MaximumA={100,150,200,225,250,350,400,450,550,700,900,1050,1400};
        private static readonly double[] FValues={100,100,100,100,100,100,100,120,145,145,170,195,225};
        internal static double FForA(double a)
        {
            if(double.IsNaN(a)||double.IsInfinity(a)||a<=0)
                throw new InvalidOperationException("A24 的 A 必须是大于 0 的有限尺寸。");
            for(int i=0;i<MaximumA.Length;i++) if(a<=MaximumA[i]) return FValues[i];
            throw new InvalidOperationException("计算内径 A="+a+" mm 超出 A24 表 1 上限 1400 mm。");
        }
    }
}
