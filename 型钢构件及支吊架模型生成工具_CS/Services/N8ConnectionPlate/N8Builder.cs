using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class N8Builder
    {
        internal static List<Element> Build(N8Plan plan,DPoint3d origin)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("N8 需要三维活动模型。");
            var frame=new G2AnchorFrame(origin,model.GetModelInfo().UorPerMeter/1000,
                plan.HeadingDegrees,plan.MountFace);
            return Build(plan,frame);
        }
        internal static List<Element> Build(N8Plan plan,G2AnchorFrame frame)
        {
            var parts=new List<Element>();
            parts.Add(BuildPlate(plan,frame));
            var holes=N8Catalog.HolePositions(plan);
            for(int i=0;i<plan.BoltCount;i++)
            {
                double y=holes[i,0],z=holes[i,1];
                // Python N8: washer A [-w,0], washer B [2T,2T+w].
                double washerA=-plan.WasherThickness;
                double washerB=2*plan.T;
                double nutBack=washerB+plan.WasherThickness;
                double tip=Math.Max(plan.BoltLength,nutBack+plan.NutHeight+5);
                parts.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                    frame.Point(washerA,y,z),frame.Point(tip,y,z),
                    plan.BoltDiameter/2*frame.Scale),5));
                parts.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                    frame.Point(washerA,y,z),frame.Point(0,y,z),
                    plan.WasherOutside/2*frame.Scale),5));
                parts.Add(SolidPrimitiveFactory.Element(Hex(frame,washerA-plan.HeadHeight,
                    plan.HeadHeight,y,z,plan.HeadAcross),5));
                parts.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                    frame.Point(washerB,y,z),frame.Point(nutBack,y,z),
                    plan.WasherOutside/2*frame.Scale),5));
                parts.Add(SolidPrimitiveFactory.Element(Hex(frame,
                    nutBack,plan.NutHeight,y,z,plan.NutAcross),5));
            }
            return parts;
        }
        internal static Element BuildPlate(N8Plan plan,G2AnchorFrame frame)
        {
            double half=plan.E/2;
            var body=SolidPrimitiveFactory.PolygonPrism(new[]{
                frame.Point(0,-half,-half),frame.Point(0,half,-half),
                frame.Point(0,half,half),frame.Point(0,-half,half)},frame.Direction(plan.T,0,0));
            var holes=N8Catalog.HolePositions(plan);
            var cutters=new List<SolidKernelEntity>();
            for(int i=0;i<plan.BoltCount;i++)cutters.Add(SolidPrimitiveFactory.Cylinder(
                frame.Point(-2,holes[i,0],holes[i,1]),
                frame.Point(plan.T+2,holes[i,0],holes[i,1]),plan.G/2*frame.Scale));
            SolidPrimitiveFactory.Subtract(ref body,cutters,"N8 连接板开孔");
            return SolidPrimitiveFactory.Element(body,3);
        }
        private static SolidKernelEntity Hex(G2AnchorFrame f,double x,double length,
            double y,double z,double across)
        {
            var points=new DPoint3d[6];double radius=across/Math.Sqrt(3);
            for(int i=0;i<6;i++)
            {
                double angle=i*Math.PI/3;
                points[i]=f.Point(x,y+radius*Math.Cos(angle),z+radius*Math.Sin(angle));
            }
            return SolidPrimitiveFactory.PolygonPrism(points,f.Direction(length,0,0));
        }
    }
}
