using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class PortalFrameCatalog
    {
        internal static readonly string[] Kinds={"D8","D13","G5","G6"};
        private static readonly string[] Angles={"L50x50x6","L75x75x7","L100x100x10"};
        private static readonly string[] HBeams={"H100x100x6x8xr8","H150x150x7x10xr8",
            "H200x200x8x12xr13","H250x250x9x14xr13"};
        private static readonly string[] Channels={"5","10","16a","20a"};
        private static readonly double[][] G5Ground={
            new[]{150d,100d,10d,10d,8d,120d,55d,100d},
            new[]{210d,150d,14d,10d,12d,160d,90d,150d},
            new[]{260d,200d,18d,12d,16d,180d,100d,150d},
            new[]{260d,200d,18d,12d,16d,180d,100d,150d},
            new[]{350d,250d,22d,16d,20d,220d,125d,150d},
            new[]{400d,300d,22d,20d,20d,220d,125d,150d},
            new[]{500d,400d,22d,20d,20d,220d,125d,150d}};
        private static readonly double[][] G6Ground={G5Ground[3],G5Ground[4],G5Ground[5],G5Ground[6]};
        // 行格式：子项:H:B或L列=荷载。-1 为标准表的空栏。
        private const string D8Loads="A:500:500=3,1000=-1;A:1000:500=1,1000=-1;"+
            "B:500:500=10,1000=5;B:1000:500=6,1000=3;"+
            "C:500:500=20,1000=10;C:1000:500=10,1000=5;C:1500:500=5,1000=2.5;"+
            "D:500:500=30,1000=20,1500=15,2000=12;D:1000:500=20,1000=15,1500=12,2000=10;D:1500:500=15,1000=12,1500=10,2000=8;"+
            "E:500:500=50,1000=40,1500=30,2000=20;E:1000:500=40,1000=30,1500=20,2000=15;E:1500:500=30,1000=20,1500=15,2000=12;E:2000:500=20,1000=15,1500=12,2000=10";
        private const string D13Loads="A:1000:1000=20,2000=-1,3000=-1;A:2000:1000=10,2000=-1,3000=-1;A:3000:1000=-1,2000=-1,3000=-1;A:4000:1000=-1,2000=-1,3000=-1;"+
            "B:1000:1000=80,2000=60,3000=-1;B:2000:1000=40,2000=40,3000=-1;B:3000:1000=20,2000=20,3000=-1;B:4000:1000=-1,2000=-1,3000=-1;"+
            "C:1000:1000=140,2000=80,3000=60;C:2000:1000=80,2000=80,3000=60;C:3000:1000=40,2000=40,3000=40;C:4000:1000=20,2000=20,3000=20;"+
            "D:1000:1000=200,2000=120,3000=100;D:2000:1000=100,2000=100,3000=100;D:3000:1000=70,2000=70,3000=70;D:4000:1000=40,2000=40,3000=40";
        private const string G5Loads="A:500:500=2,1000=-1;B:500:500=4,1000=2;B:1000:500=2,1000=1;"+
            "C:500:500=8,1000=4;C:1000:500=4,1000=2;D:1000:500=20,1000=10;D:1500:500=8,1000=8;"+
            "E:1000:1000=40,1500=20,2000=20;E:2000:1000=20,1500=20,2000=20;"+
            "F:1000:1000=60,1500=40,2000=40;F:2000:1000=40,1500=30,2000=30;F:3000:1000=20,1500=20,2000=20;"+
            "G:1000:1000=100,1500=80,2000=80;G:2000:1000=60,1500=60,2000=60;G:3000:1000=40,1500=40,2000=40";
        private const string G6Loads="A:1000:500=15,1000=10;A:1500:500=8,1000=8;"+
            "B:1000:1000=40,1500=20;B:2000:1000=20,1500=20;"+
            "C:1000:1000=60,1500=40,2000=40;C:2000:1000=40,1500=30,2000=30;C:3000:1000=20,1500=20,2000=20;"+
            "D:1000:1000=100,1500=80,2000=80;D:2000:1000=60,1500=60,2000=60;D:3000:1000=40,1500=40,2000=40";
        internal static string Variants(string kind)
        {switch(kind){case "D8":return "ABCDE";case "D13":case "G6":return "ABCD";
            case "G5":return "ABCDEFG";default:throw new InvalidOperationException("未知门型架种类。");}}
        internal static string SupportType(string kind)
        {switch(kind){case "D8":return "D8-[门型架_倒门型架（角钢和槽钢）]";
            case "D13":return "D13-[门型架_倒门型架（H型钢）]";
            case "G5":return "G5-[地面上生根的门型架]";
            case "G6":return "G6-[地面上生根的门型架（槽钢和H型钢组合）]";
            default:throw new InvalidOperationException("未知门型架种类。");}}
        internal static string SupportCode(string kind)
        {switch(kind){case "D8":return "PORTAL_FRAME";case "D13":return "PORTAL_FRAME_H";
            case "G5":return "G5_GROUND_PORTAL_FRAME";case "G6":return "G6_GROUND_PORTAL_FRAME";
            default:throw new InvalidOperationException("未知门型架种类。");}}
        internal static string AssemblyItemName(string kind){return "PipeSupportAssembly_"+SupportCode(kind);}
        internal static string ComponentItemName(string kind,string role)
        {return "PipeSupportComponent_"+SupportCode(kind)+"_"+role;}
        internal static PortalFrameVariant Variant(string kind,char key)
        {
            int index=Variants(kind).IndexOf(key);
            if(index<0)throw new InvalidOperationException("门型架子项不适用于当前种类。");
            var v=new PortalFrameVariant();
            if(kind=="D8")
            {
                if(index<3){v.PostFamily=v.ArmFamily="equal_angle";
                    v.PostProfile=v.ArmProfile=Angles[index];}
                else{v.PostFamily=v.ArmFamily="parallel_channel";
                    v.PostProfile=v.ArmProfile=index==3?"14a":"20a";}
            }
            else if(kind=="D13")
            {v.PostFamily=v.ArmFamily="hot_rolled_h";v.PostProfile=v.ArmProfile=HBeams[index];}
            else if(kind=="G5")
            {
                v.PostFamily=v.ArmFamily=index<3?"equal_angle":"hot_rolled_h";
                v.PostProfile=v.ArmProfile=index<3?Angles[index]:HBeams[index-3];
                v.Ground=Ground(G5Ground[index]);
            }
            else
            {
                v.PostFamily="hot_rolled_h";v.PostProfile=HBeams[index];
                v.ArmFamily="parallel_channel";v.ArmProfile=Channels[index];
                v.ChannelGap=new[]{25d,50d,70d,100d}[index];
                v.Ground=Ground(G6Ground[index]);
            }
            v.PostSpecification=Specification(v.PostProfile);
            v.ArmSpecification=Specification(v.ArmProfile);
            return v;
        }
        private static PortalGroundSpec Ground(double[] s)
        {return new PortalGroundSpec{PlateSide=s[0],HoleSpacing=s[1],HoleDiameter=s[2],
            PlateThickness=s[3],BoltDiameter=s[4],BoltLength=s[5],Embedment=s[6],MinPavement=s[7]};}
        private static string Specification(string profile)
        {if(profile.StartsWith("H"))return profile.Substring(0,profile.LastIndexOf("xr",StringComparison.Ordinal)).Replace("x","×");
            if(profile.StartsWith("L")){var a=profile.Split('x');return "∠"+a[0].Substring(1)+"×"+a[2];}
            return "["+profile;}
        internal static ProfileData Profile(string family,string name)
        {var value=ProfileLookup.Profile(RuntimeData.Families,family,name);
            if(value==null)throw new InvalidOperationException("型钢目录缺少 "+name+"。");return value;}
        internal static double Dimension(string family,string name,string key)
        {double value;if(!Profile(family,name).Dimensions.TryGetValue(key,out value))
            throw new InvalidOperationException("型钢规格 "+name+" 缺少尺寸 "+key+"。");return value;}
        private static string LoadText(string kind)
        {switch(kind){case "D8":return D8Loads;case "D13":return D13Loads;
            case "G5":return G5Loads;default:return G6Loads;}}
        private static IEnumerable<Tuple<double,string>> Rows(string kind,char key)
        {foreach(string raw in LoadText(kind).Split(';'))
            {string[] bits=raw.Split(':');if(bits.Length==3&&bits[0]==key.ToString())
                yield return Tuple.Create(double.Parse(bits[1],CultureInfo.InvariantCulture),bits[2]);}}
        internal static double? Load(string kind,char key,double height,double span)
        {
            var ordered=Rows(kind,key).OrderBy(x=>x.Item1).ToArray();
            var row=kind=="D8"||kind=="D13"
                ?ordered.LastOrDefault(x=>x.Item1<=height+1)
                :ordered.FirstOrDefault(x=>x.Item1+1>=height);
            if(row==null)return null;
            foreach(string pair in row.Item2.Split(','))
            {string[] values=pair.Split('=');double col=double.Parse(values[0],CultureInfo.InvariantCulture);
                if(span<=col){double load=double.Parse(values[1],CultureInfo.InvariantCulture);
                    return load<0?(double?)null:load;}}
            return null;
        }
        internal static double MaxHeight(string kind,char key){return Rows(kind,key).Max(x=>x.Item1);}
        internal static double MaxSpan(string kind,char key)
        {return Rows(kind,key).SelectMany(x=>x.Item2.Split(','))
            .Max(x=>double.Parse(x.Split('=')[0],CultureInfo.InvariantCulture));}
    }
}
