using System;

namespace SteelSectionProbe
{
    internal static class BracketCatalog
    {
        internal static readonly string[] A={"[14a","[20a","H148x100x6x9",
            "H194x150x6x9","H244x175x7x11","H294x200x8x12"};
        internal static readonly string[] B={"[10","[12.6","H100x100x6x8",
            "H125x125x6.5x9","H150x150x7x10","H200x200x8x12"};
        internal static readonly string[] C={"[14a","[20a","H125x125x6.5x9",
            "H175x175x7.5x11","H200x200x8x12","H250x250x9x14"};
        internal static readonly int[] PlateType={2,3,2,3,4,5};
        internal static readonly double[] MinH={390,480,390,480,500,590};
        internal static readonly double[] MinL2={390,480,390,480,500,590};
        internal static readonly double[] MaxL1={1000,1250,1750,2000,2500,2500};
        internal static readonly double[] AHeight={140,200,148,194,244,294};
        internal static readonly double[] AWidth={58,73,100,150,175,200};
        internal static readonly double[] AWeb={6,7,6,6,7,8};
        internal static readonly double[] AFlange={9.5,11,9,9,11,12};
        internal static readonly double[] CHeight={140,200,125,175,200,250};
        internal static readonly double[] CWidth={58,73,125,175,200,250};
        internal static string SupportType(bool isDouble)
        {return isDouble?"N4-[设备上生根双三角架]":"N3-[设备上生根单三角架]";}
        internal static string SupportCode(bool isDouble)
        {return isDouble?"N4_DOUBLE_BRACKET":"N3_SINGLE_BRACKET";}
        internal static double VerticalLoad(int index,double span,bool isDouble)
        {
            // The tables use the first column at or above the requested span.
            double[][] spans={new[]{500.0,750,1000},new[]{750.0,1000,1250},
                new[]{750.0,1000,1250,1500,1750},
                new[]{750.0,1000,1250,1500,1750,2000},
                new[]{750.0,1000,1250,1500,1750,2000,2250,2500},
                new[]{750.0,1000,1250,1500,1750,2000,2250,2500}};
            double[][] single={new[]{38.0,28,18},new[]{40.0,35,30},
                new[]{70.0,65,60,50,40},new[]{120.0,110,100,90,75,60},
                new[]{180.0,150,150,120,120,100,100,100},
                new[]{250.0,250,225,225,225,200,200,200}};
            double[][] dual={new[]{76.0,56,36},new[]{80.0,70,60},
                new[]{140.0,130,120,100,80},new[]{240.0,220,200,180,150,120},
                new[]{360.0,300,300,240,240,200,200,200},
                new[]{500.0,500,450,450,450,400,400,400}};
            for(int j=0;j<spans[index].Length;j++)
                if(span<=spans[index][j])return (isDouble?dual:single)[index][j];
            return 0;
        }
        internal static double HorizontalLoad(int index,double span)
        {
            double[][] spans={new[]{500.0,750},new[]{500.0,750,1000},
                new[]{500.0,750,1000,1250},new[]{500.0,750,1000,1250,1500},
                new[]{500.0,750,1000,1250,1500},new[]{500.0,750,1000,1250,1500}};
            double[][] loads={new[]{6.0,3},new[]{12.0,6,4},new[]{16.0,7,5,4},
                new[]{40.0,18,12,10,5},new[]{70.0,40,25,16,12},
                new[]{90.0,60,45,30,20}};
            for(int j=0;j<spans[index].Length;j++)if(span<=spans[index][j])return loads[index][j];
            return 0;
        }
    }
}
