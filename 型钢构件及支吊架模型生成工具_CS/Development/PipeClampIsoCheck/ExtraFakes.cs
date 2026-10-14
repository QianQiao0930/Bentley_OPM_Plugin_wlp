using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal static class NativeSupportLog {internal static void Run(Action<Action<string>> work){work(text=>{});}}
    internal static class Pieces
    {
        internal static List<Element> Build(DPoint3d center)
        {return Enumerable.Range(0,4).Select(i=>new Element{Geometry=new[]{center,new DPoint3d(center.X+30*(i+1),center.Y-17*(i+2),center.Z+11*(i+3))}}).ToList();}
    }
    internal static class U3ClampBuilder {internal static List<Element> Build(U3ClampPlan p,DPoint3d c,DVector3d a){return Pieces.Build(c);}}
    internal static class A2ClampBuilder {internal static List<Element> Build(A2ClampPlan p,DPoint3d c,DVector3d a){return Pieces.Build(c);}}
    internal static class A22ClampBuilder {internal static List<Element> Build(A22ClampPlan p,DPoint3d c,DVector3d a){return Pieces.Build(c);}}
    internal static class K1LimitBuilder {internal static List<Element> Build(K1LimitPlan p,DPoint3d c,DVector3d a){return Pieces.Build(c);}}
    internal static class T4ShoeBuilder {internal static List<Element> Build(T4ShoeLayout p,T4ShoeBooleanLayout b,DPoint3d c,DVector3d a,bool pipe,bool ins){return Pieces.Build(c);}}
    internal static class E1GuideBuilder
    {internal static List<Element> Build(E1GuidePlan p){double scale=Bentley.MstnPlatformNET.Session.Instance.Model.Scale;return Pieces.Build(new DPoint3d(p.CenterXmm*scale,p.CenterYmm*scale,p.CenterZmm*scale));}}
    internal static partial class Statistics
    {
        private static void Attach(Element e,string code){if(World.Fault=="Statistics")throw new InvalidOperationException("统计失败");e.MaterialTag=code;}
        internal static void AttachU3Clamp(Element e,U3ClampPlan p){Attach(e,"U3");}
        internal static void AttachA2Clamp(Element e,A2ClampPlan p){Attach(e,"A2");}
        internal static void AttachA22Clamp(Element e,A22ClampPlan p){Attach(e,"A22");}
        internal static void AttachA24Clamp(Element e,A22ClampPlan p){Attach(e,"A24");}
        internal static void AttachE1Guide(Element e,E1GuidePlan p){Attach(e,"E1");}
        internal static void AttachK1Limit(Element e,K1LimitPlan p){Attach(e,"K1");}
        internal static void AttachT4Shoe(Element e,T4ShoeLayout p,T4ShoeBooleanLayout b,bool pipe,bool ins){Attach(e,"T4:"+pipe+":"+ins);}
        internal static void AttachL2Shoe(Element e,T4ShoeLayout p,T4ShoeBooleanLayout b,bool pipe,bool ins){Attach(e,"L2:"+pipe+":"+ins);}
    }
}
