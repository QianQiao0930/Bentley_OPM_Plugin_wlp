using System;

namespace SteelSectionProbe
{
    /// <summary>D7 表 1～3；截面实体仍从 profiles.bin 读取。</summary>
    internal static class LBracketCatalog
    {
        internal const string SupportType="D7-[L形_倒L形架]";
        internal const string SupportCode="L_PIPE_RACK";
        internal const string CellName="L_PIPE_RACK";
        internal const string AssemblyItemName="PipeSupportAssembly_L_PIPE_RACK";
        internal static string ComponentItemName(string role)
        {return "PipeSupportComponent_L_PIPE_RACK_"+role;}
        internal static readonly char[] Keys={'A','B','C','D','E','F'};
        private static readonly LBracketVariant[] Items={
            V('A',"equal_angle","L50x50x6","∠50×6",50,6,14.6,
                new[]{500.0,1000},new[]{250.0,500},
                new double?[][]{new double?[]{0.3,null},new double?[]{0.15,null}}),
            V('B',"equal_angle","L75x75x7","∠75×7",75,7,21.1,
                new[]{500.0,1000,1500},new[]{250.0,500},
                new double?[][]{new double?[]{1,null},new double?[]{0.7,null},new double?[]{0.5,null}}),
            V('C',"equal_angle","L100x100x10","∠100×10",100,10,28.4,
                new[]{500.0,1000,1500,2000},new[]{250.0,500},
                new double?[][]{new double?[]{3,2},new double?[]{1.6,1},
                    new double?[]{1.2,0.8},new double?[]{0.8,0.6}}),
            V('D',"parallel_channel","16a","[16a",160,10,0,
                new[]{500.0,1000,1500,2000,2500,3000},new[]{250.0,500},
                new double?[][]{new double?[]{8,6},new double?[]{5,4},
                    new double?[]{3.5,3},new double?[]{2.5,2},
                    new double?[]{1.5,1.2},new double?[]{1,0.5}}),
            V('E',"hot_rolled_h","H125x125x6.5x9xr8","H125×125×6.5×9",125,9,0,
                new[]{500.0,1000,1500,2000,2500,3000},new[]{250.0,500,750},
                new double?[][]{new double?[]{15,8,5},new double?[]{10,5,3},
                    new double?[]{6,3.5,2},new double?[]{4,2.5,1.5},
                    new double?[]{3,2,1},new double?[]{2,1,0.7}}),
            V('F',"hot_rolled_h","H150x150x7x10xr8","H150×150×7×10",150,10,0,
                new[]{500.0,1000,1500,2000,2500,3000},new[]{250.0,500,750},
                new double?[][]{new double?[]{25,15,8},new double?[]{15,10,6},
                    new double?[]{12,6,4},new double?[]{8,5,3},
                    new double?[]{6,4,2},new double?[]{4,3,1}})
        };
        private static LBracketVariant V(char key,string family,string profile,string specification,
            double height,double thickness,double centroid,double[] heights,double[] widths,double?[][] loads)
        {return new LBracketVariant {Key=key,Family=family,Profile=profile,
            Specification=specification,HeightMm=height,ThicknessMm=thickness,
            CentroidMm=centroid,HeightColumns=heights,WidthColumns=widths,Loads=loads,
            MaxHeightMm=heights[heights.Length-1],MaxWidthMm=widths[widths.Length-1]};}
        internal static LBracketVariant Require(char key)
        {foreach(var item in Items)if(item.Key==key)return item;
            throw new InvalidOperationException("未知 D7 子项。");}
    }
}
