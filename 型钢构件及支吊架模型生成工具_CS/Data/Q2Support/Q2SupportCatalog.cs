using System;
namespace SteelSectionProbe
{
    internal static class Q2SupportCatalog
    {
        internal const string SupportType="Q2-[大管用角钢支撑小管]";
        internal static readonly int[] SmallDns={15,20,25,32,40,50,65,80,90,100,125,150};
        internal const string CellName="Q2_ANGLE_SMALL_PIPE_SUPPORT";
        internal static double Load(string item,double length)
        {
            if(double.IsNaN(length)||double.IsInfinity(length)||length<=0||length>1000)
                throw new InvalidOperationException("Q2 中心间距 L 须大于0且不超过1000 mm。");
            int index=length<=250?0:length<=500?1:length<=750?2:3;
            double[] row=item=="A"?new[]{.5,.2,0,0}:item=="B"?new[]{2.0,1,.5,.2}:item=="C"?new[]{4.0,2,1,.6}:null;
            if(row==null)throw new InvalidOperationException("Q2 子项须为 A、B 或 C。");
            if(row[index]<=0)throw new InvalidOperationException("Q2 子项A不适用于 L 大于500 mm，请选择B或C。");
            return row[index];
        }
        /// <summary>用户提供的承重块表：沿立管焊接长边 × 径向伸出短边 × 切向厚度，mm。</summary>
        internal static double[] Block(int dn)
        {
            A1ClampCatalog.Require(dn);
            if(dn>=15&&dn<=65)return new[]{50.0,30,10};
            if(dn>=80&&dn<=150)return new[]{100.0,50,10};
            throw new InvalidOperationException("承重块尺寸表只提供 DN15～150，当前立管 DN"+dn+" 超出范围。");
        }
    }
}
