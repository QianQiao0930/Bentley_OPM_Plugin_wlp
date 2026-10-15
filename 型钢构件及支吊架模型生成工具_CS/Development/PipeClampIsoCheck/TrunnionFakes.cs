using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal static class VerticalPipeSupportBuilder
    { internal static List<Element> Build(VerticalPipeSupportPlan p, DPoint3d c, DVector3d a) { return Pieces.Build(c); } }
    internal static class ElbowTrunnionBuilder
    {
        internal static List<Element> Build(ElbowTrunnionPlan p)
        {
            double s = Bentley.MstnPlatformNET.Session.Instance.Model.Scale;
            return new List<Element> { new Element { Geometry = new[] {
                new DPoint3d(p.TubeStartMm.X*s,p.TubeStartMm.Y*s,p.TubeStartMm.Z*s),
                new DPoint3d(p.TubeEndMm.X*s,p.TubeEndMm.Y*s,p.TubeEndMm.Z*s),
                new DPoint3d(p.PlateEndMm.X*s,p.PlateEndMm.Y*s,p.PlateEndMm.Z*s) } } };
        }
    }
    internal static class ElbowTrunnionReader
    {
        internal static ElbowTrunnionSelection Current;
        internal static ElbowTrunnionSelection Read(ulong id, ElbowOrientation elbow, TrunnionOrientation trunnion) { return Current; }
    }
    internal static partial class Statistics
    {
        internal static int TrunnionAttachments;
        internal static void AttachVerticalPipeSupport(Element e, VerticalPipeSupportPlan p) { Attach(e, p.Number); TrunnionAttachments++; }
        internal static void AttachElbowTrunnion(Element e, ElbowTrunnionPlan p, string role, string name, string spec, double length, bool assembly)
        { Attach(e, p.AssemblyTag); TrunnionAttachments++; }
    }
}
