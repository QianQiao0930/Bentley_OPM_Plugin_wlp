using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class TFrameCatalog
    {
        internal static readonly string[] Kinds={"D12","G4","D15"};
        private const string D12="A:500:250=1;A:1000:250=.5;"+
            "B:500:250=2.8,500=1.8;B:1000:250=1.8,500=1.2;"+
            "C:500:250=6,500=4,750=3,1000=2.4;C:1000:250=2.4,500=1.6,750=1.2,1000=.9;C:1500:250=1.8,500=1.2,750=.9,1000=.6;"+
            "D:1000:500=20,1000=10;D:2000:500=5,1000=5;"+
            "E:1000:500=40,1000=30,1500=20,2000=15;E:2000:500=20,1000=20,1500=20,2000=15;E:3000:500=10,1000=10,1500=10,2000=10;"+
            "F:1000:500=70,1000=40,1500=30,2000=25;F:2000:500=40,1000=40,1500=30,2000=25;F:3000:500=20,1000=20,1500=20,2000=20;F:4000:500=10,1000=10,1500=10,2000=10;"+
            "G:1000:500=100,1000=60,1500=50,2000=40;G:2000:500=50,1000=50,1500=50,2000=40;G:3000:500=35,1000=35,1500=35,2000=35;G:4000:500=20,1000=20,1500=20,2000=20";
        private const string G4="A:500:250=1;"+
            "B:500:250=2,500=1;B:1000:250=1,500=.5;"+
            "C:500:250=4,500=2;C:1000:250=2,500=1;"+
            "D:1000:250=10,500=5;D:1500:250=4,500=4;"+
            "E:1000:250=20,500=20,750=10,1000=10;E:2000:250=10,500=10,750=10,1000=10;"+
            "F:1000:250=-1,500=30,750=30,1000=30;F:2000:250=-1,500=20,750=20,1000=20;F:3000:250=-1,500=10,750=10,1000=10;"+
            "G:1000:250=-1,500=50,750=50,1000=50;G:2000:250=-1,500=30,750=30,1000=30;G:3000:250=-1,500=20,750=20,1000=20";
        private const string D15="A:250=.3,500=.15;B:250=1,500=.5;C:250=2,500=1;"+
            "D:250=8,500=4,750=2.5;E:250=12,500=8,750=6,1000=4";
        internal static string Variants(string kind)
        {if(kind=="D12"||kind=="G4")return "ABCDEFG";
            if(kind=="D15")return "ABCDE";
            throw new InvalidOperationException("未知 T 型架类别。");}
        internal static string SupportType(string kind)
        {return kind=="D15"?"D15-[水平T形架]":"D12_G4-[T形_倒T形架]";}
        internal static string SupportCode(string kind)
        {switch(kind){case "D12":return "T_FRAME_D12";case "G4":return "T_FRAME_G4";
            case "D15":return "H_T_FRAME";default:throw new InvalidOperationException("未知 T 型架类别。");}}
        internal static string AssemblyItemName(string kind)
        {return "PipeSupportAssembly_"+SupportCode(kind);}
        internal static string ComponentItemName(string kind,string role)
        {return "PipeSupportComponent_"+SupportCode(kind)+"_"+role;}
        internal static TFrameVariant Variant(string kind,char key)
        {
            int i=Variants(kind).IndexOf(key);
            if(i<0)throw new InvalidOperationException("当前类别不支持该子项。");
            var v=new TFrameVariant();
            if(kind=="D12"||kind=="G4")
            {
                var p=PortalFrameCatalog.Variant("G5",key);
                v.FamilyA=v.FamilyB=p.PostFamily;v.ProfileA=v.ProfileB=p.PostProfile;
                v.SpecA=v.SpecB=p.PostSpecification;
                if(kind=="G4")v.Ground=p.Ground;
            }
            else
            {
                string[] a={"L50x50x6","L75x75x7","10","H100x100x6x8xr8",
                    "H150x150x7x10xr8"};
                string[] b={"L50x50x6","L75x75x7","14a","14a","20a"};
                string[] fa={"equal_angle","equal_angle","parallel_channel",
                    "hot_rolled_h","hot_rolled_h"};
                string[] fb={"equal_angle","equal_angle","parallel_channel",
                    "parallel_channel","parallel_channel"};
                v.FamilyA=fa[i];v.FamilyB=fb[i];v.ProfileA=a[i];v.ProfileB=b[i];
                v.SpecA=Spec(v.FamilyA,v.ProfileA);v.SpecB=Spec(v.FamilyB,v.ProfileB);
            }
            return v;
        }
        private static string Spec(string family,string profile)
        {if(family=="equal_angle"){var s=profile.Split('x');return "∠"+s[0].Substring(1)+"×"+s[2];}
            if(family=="parallel_channel")return "["+profile;
            return profile.Substring(0,profile.LastIndexOf("xr",StringComparison.Ordinal)).Replace("x","×");}
        private static string Table(string kind)
        {return kind=="D12"?D12:kind=="G4"?G4:D15;}
        private static IEnumerable<Tuple<double,string>> Rows(string kind,char key)
        {foreach(string raw in Table(kind).Split(';'))
            {string[] parts=raw.Split(':');
                if(kind=="D15")
                {if(parts.Length==2&&parts[0]==key.ToString())yield return Tuple.Create(0d,parts[1]);}
                else if(parts.Length==3&&parts[0]==key.ToString())
                    yield return Tuple.Create(double.Parse(parts[1],CultureInfo.InvariantCulture),parts[2]);}}
        private static IEnumerable<Tuple<double,double>> Columns(string data)
        {foreach(string pair in data.Split(','))
            {string[] values=pair.Split('=');yield return Tuple.Create(
                double.Parse(values[0],CultureInfo.InvariantCulture),
                double.Parse(values[1],CultureInfo.InvariantCulture));}}
        internal static double MaxHeight(string kind,char key)
        {if(kind=="D15")return 0;
            return Rows(kind,key).Where(x=>Columns(x.Item2).Any(y=>y.Item2>=0)).Max(x=>x.Item1);}
        internal static double MaxLength(string kind,char key)
        {return Rows(kind,key).SelectMany(x=>Columns(x.Item2)).Where(x=>x.Item2>=0).Max(x=>x.Item1);}
        internal static double MaxL2(char key,int type)
        {return key=='E'?(type==1?500:1000):(type==1?250:500);}
        internal static double? Load(string kind,char key,double height,double length)
        {
            var rows=Rows(kind,key).OrderBy(x=>x.Item1).ToArray();
            var row=kind=="D15"?rows.FirstOrDefault():rows.LastOrDefault(x=>x.Item1<=height+1);
            if(row==null)return null;
            foreach(var col in Columns(row.Item2).OrderBy(x=>x.Item1))
                if(length<=col.Item1+(kind=="D15"?1:0))return col.Item2<0?(double?)null:col.Item2;
            return null;
        }
    }
}
