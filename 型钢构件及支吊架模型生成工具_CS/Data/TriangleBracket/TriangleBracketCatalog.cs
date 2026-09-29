using System;

namespace SteelSectionProbe
{
    internal static class TriangleBracketCatalog
    {
        internal static readonly string[] Kinds={"D5","D6","G12","D19"};
        internal static readonly double[] LoadColumns={500,750,1000,1250};
        internal static readonly double[] D19LoadColumns={500,750,1000,1250,1500};
        private static readonly string[] D5A={"H125x125x6.5x9","H150x150x7x10",
            "H200x200x8x12","H250x250x9x14"};
        private static readonly string[] D5B={"L100x100x10","L125x125x10",
            "L160x160x12","L200x200x14"};
        private static readonly double[][] D5Sizes={
            new double[]{125,125,6.5,9,100,100,10},
            new double[]{150,150,7,10,125,125,10},
            new double[]{200,200,8,12,160,160,12},
            new double[]{250,250,9,14,200,200,14}};
        private static readonly string[] ChannelA={"12.6","16a","20a","25a"};
        private static readonly string[] ChannelB={"10","12.6","14a","20a"};
        private static readonly double[][] ChannelSizes={
            new double[]{126,53,5.5,9,100,48,5.3,8.5},
            new double[]{160,63,6.5,10,126,53,5.5,9},
            new double[]{200,73,7,11,140,58,6,9.5},
            new double[]{250,78,7,12,200,73,7,11}};
        private static readonly double?[][] D6Loads={
            new double?[]{8.9,6,4.5,null},new double?[]{14,9.8,7.4,null},
            new double?[]{21,14,10,8.6},new double?[]{26,18,13,11}};
        private static readonly double?[][] G12Loads={
            new double?[]{6,4,3,null},new double?[]{10,6,6,null},
            new double?[]{null,10,7,5},new double?[]{null,20,10,8}};
        private static readonly double?[][] D19Loads={
            new double?[]{60,40,30,null,null},new double?[]{100,70,50,null,null},
            new double?[]{150,100,70,50,null},new double?[]{220,160,120,100,80}};
        internal static double MaxLength(string kind)
        {
            switch(kind) {case "D5":return 2500;case "D6":case "G12":return 1500;
                case "D19":return 2000;default:throw new InvalidOperationException("未知三角架架型。");}
        }
        internal static string SupportType(string kind)
        {
            switch(kind) {case "D5":return "D5-端焊三角架";case "D6":return "D6-侧焊三角架";
                case "G12":return "G12-混凝土锚固三角架";case "D19":return "D19-双槽钢三角架";
                default:throw new InvalidOperationException("未知三角架架型。");}
        }
        internal static string SupportCode(string kind)
        {
            switch(kind) {case "D5":return "D5_END_WELDED_TRIANGLE_BRACKET";
                case "D6":return "D6_SIDE_WELDED_TRIANGLE_BRACKET";
                case "G12":return "G12_CONCRETE_ANCHORED_BRACKET";
                case "D19":return "D19_DOUBLE_CHANNEL_TRIANGLE_BRACKET";
                default:throw new InvalidOperationException("未知三角架架型。");}
        }
        internal static string AssemblyItemName(string kind)
        {return "PipeSupportAssembly_"+SupportCode(kind);}
        internal static string ComponentItemName(string kind,string role)
        {
            if(string.IsNullOrWhiteSpace(role))throw new InvalidOperationException("三角架构件角色不能为空。");
            return "PipeSupportComponent_"+SupportCode(kind)+"_"+role;
        }
        internal static string CellName(string kind)
        {
            switch(kind) {case "D5":return "END_WELDED_TRIANGLE_BRACKET_PATH";
                case "D6":return "SIDE_WELDED_TRIANGLE_BRACKET_PATH";
                case "G12":return "CONCRETE_ANCHORED_TRIANGLE_BRACKET";
                case "D19":return "DOUBLE_CHANNEL_TRIANGLE_BRACKET";
                default:throw new InvalidOperationException("未知三角架架型。");}
        }
        internal static TriangleBracketVariant Variant(string kind,char key)
        {
            MaxLength(kind);
            int i=key-'A';
            if(i<0||i>=4)throw new InvalidOperationException("子项只支持 A～D。");
            var v=new TriangleBracketVariant();
            if(kind=="D5")
            {
                double[] s=D5Sizes[i];
                v.SectionA=D5A[i];v.SectionB=D5B[i];
                v.HeightA=s[0];v.WidthA=s[1];v.WebA=s[2];v.FlangeA=s[3];
                v.HeightB=s[4];v.WidthB=s[5];v.WebB=s[6];
                return v;
            }
            double[] c=ChannelSizes[i];
            v.SectionA="["+ChannelA[i];v.SectionB="["+ChannelB[i];
            v.HeightA=c[0];v.WidthA=c[1];v.WebA=c[2];v.FlangeA=c[3];
            v.HeightB=c[4];v.WidthB=c[5];v.WebB=c[6];v.FlangeB=c[7];
            if(kind=="D6")v.Loads=D6Loads[i];
            if(kind=="G12")
            {
                v.Loads=G12Loads[i];v.BoltSubtype=new[]{"B","C","D","D"}[i];
                v.BoltSpacing=new double[]{100,125,150,150}[i];
                v.BoltEdge=new double[]{100,100,200,200}[i];
            }
            if(kind=="D19")
            {
                v.Loads=D19Loads[i];v.WebGap=new double[]{60,70,80,90}[i];
                v.ConnectorLength=new double[]{100,120,150,150}[i];
                v.ConnectorHeight=new double[]{60,80,100,120}[i];
                v.ConnectorThickness=10;
            }
            return v;
        }
    }
}
