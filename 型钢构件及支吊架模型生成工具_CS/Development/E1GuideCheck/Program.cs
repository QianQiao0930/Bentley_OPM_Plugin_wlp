using System;
using SteelSectionProbe;
namespace SteelSectionProbe
{
    internal static class RuntimeData
    {
        internal static FamilyData[] Families { get { return new FamilyData[0]; } }
    }
}
internal static class Program
{
    private static void Check(bool ok,string message)
    {if(!ok)throw new Exception(message);}
    private static void Main()
    {
        Check(E1GuideCatalog.Dns.Length==26,"DN count");
        Check(E1GuideCatalog.MatchDn(88.9)==80,"OD to DN");
        Check(E1GuideCatalog.MatchDn(900)==900,"nominal to DN");
        Check(E1GuideCatalog.MatchDn(1)==null,"unknown DN");
        int[] examples={50,100,250,400,700};
        string[] keys={"A","B","C","D","E"};
        for(int i=0;i<examples.Length;i++)
        {
            var p=E1GuideCalculator.Calculate(examples[i],null,false,"Q235B",
                0,0,1000,1000,0,1000,400,20,1000,"P-1",1,false);
            Check(p.Item.Key==keys[i],"automatic subitem "+examples[i]);
            Check(Math.Abs(p.CenterXmm-400)<1e-9 && Math.Abs(p.CenterYmm)<1e-9,"axis projection");
            Check(Math.Abs(p.FaceMm-p.OutsideMm/2-3)<1e-9,"clearance");
            Check(p.PipeX==1 && p.AwayY==1,"local axes");
        }
        var small=E1GuideCalculator.Calculate(65,null,false,null,0,0,0,1000,0,0,0,0,0,"",1,false);
        Check(small.HeightMm==50 && small.Number=="E1-A-50","small pipe height");
        var stainless=E1GuideCalculator.Calculate(80,null,true,null,0,0,0,1000,0,0,300,0,0,"",1,false);
        Check(stainless.HeightMm==94 && stainless.Number=="E1-B-94-S","stainless numbering");
        Check(Math.Abs(stainless.FaceMm-49.45)<1e-9,"liner spacing");
        var reversed=E1GuideCalculator.Calculate(100,"C",false,null,1000,0,0,0,0,0,500,0,0,"",1,true);
        Check(reversed.CenterXmm==500 && reversed.PipeX==-1 && reversed.AwayY==-1,"reverse axis");
        Check(reversed.IsAuxiliaryLine && !stainless.IsAuxiliaryLine,"source kind is preserved");
        bool invalid=false;
        try{E1GuideCalculator.Calculate(100,null,false,null,0,0,0,1000,0,1000,0,0,0,"",1,false);}
        catch(InvalidOperationException){invalid=true;}
        Check(invalid,"non horizontal");
        var segments=new[]{
            new E1GuideSegment(0,0,0,1000,0,0),
            new E1GuideSegment(1000,0,0,1000,1000,500),
            new E1GuideSegment(0,0,0,0,0,0)
        };
        var nearSecond=E1GuideSegmentSelector.Nearest(segments,1005,600,300);
        Check(Object.ReferenceEquals(nearSecond,segments[1]),"nearest 3D polyline segment");
        var nearFirst=E1GuideSegmentSelector.Nearest(segments,200,5,0);
        Check(Object.ReferenceEquals(nearFirst,segments[0]),"first polyline segment");
        double rise29=1000*Math.Tan(29*Math.PI/180);
        var sloped=E1GuideCalculator.Calculate(100,null,false,null,
            0,0,0,1000,0,rise29,500,0,rise29/2,"",1,false);
        Check(Math.Abs(sloped.CenterZmm-rise29/2)<1e-8,"sloped placement height");
        double rise30=1000*Math.Tan(30*Math.PI/180);
        var boundary=E1GuideCalculator.Calculate(100,null,false,null,
            0,0,0,1000,0,rise30,500,0,rise30/2,"",1,false);
        Check(Math.Abs(boundary.CenterZmm-rise30/2)<1e-8,"30 degree boundary");
        var endpoint=E1GuideCalculator.Calculate(100,null,false,null,
            0,0,0,1000,0,rise30,1500,0,rise30*1.5,"",1,false);
        Check(Math.Abs(endpoint.CenterXmm-1000)<1e-8 &&
            Math.Abs(endpoint.CenterZmm-rise30)<1e-8,"projection clamps to segment end");        double rise31=1000*Math.Tan(31*Math.PI/180);
        bool tooSteep=false;
        try{E1GuideCalculator.Calculate(100,null,false,null,
            0,0,0,1000,0,rise31,500,0,rise31/2,"",1,false);}
        catch(InvalidOperationException){tooSteep=true;}
        Check(tooSteep,"slope over 30 degrees");
        // 清单属性契约：SupportCode 为 ASCII 代号（只用于 ItemType 命名），
        // SupportType 为中文类型名，须与 Python 的 SUPPORT_CODE / SUPPORT_TYPE 一致。
        Check(E1GuideCatalog.SupportCode=="E1_RACK","E1 support code");
        Check(E1GuideCatalog.SupportType=="E1-[不保温管导向架]","E1 support type");
        Console.WriteLine("E1 guide calculation checks passed.");
    }
}
