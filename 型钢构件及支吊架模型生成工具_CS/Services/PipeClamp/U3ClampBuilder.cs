using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class U3ClampBuilder
    {
        internal static List<Element> Build(U3ClampPlan p, DPoint3d center, DVector3d axis)
        {
            U3ClampCalculator.ValidateAxis(axis.X, axis.Y, axis.Z);
            var parts = A1ClampBuilder.Build(p.Clamp, center, axis);
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000;
            double[] x, y, z;
            A1ClampCalculator.RadialFrame(new[] { axis.X, axis.Y, axis.Z }, out x, out y, out z);
            double theta = p.Clamp.AngleDeg * Math.PI / 180;
            var open = new[] { Math.Cos(theta)*x[0] + Math.Sin(theta)*y[0], Math.Cos(theta)*x[1] + Math.Sin(theta)*y[1], Math.Cos(theta)*x[2] + Math.Sin(theta)*y[2] };
            // 世界竖直方向确保管轴反向时承重块依然在钢构上方。
            var across = new[] { -open[1], open[0], 0.0 };
            Func<double,double,double,DPoint3d> point = (a,b,c) => new DPoint3d(center.X + scale*(a*across[0]+b*open[0]), center.Y + scale*(a*across[1]+b*open[1]), center.Z + scale*c);
            double radius = p.Clamp.Row.OutsideMm / 2, half = p.BlockThicknessMm / 2;
            double inner = Math.Sqrt(radius*radius - half*half), outer = inner + p.BlockProjectionMm;
            var outline = new[] { point(-half,inner,p.SupportTopMm), point(half,inner,p.SupportTopMm), point(half,outer,p.SupportTopMm), point(-half,outer,p.SupportTopMm) };
            var block = SolidPrimitiveFactory.PolygonPrism(outline, new DVector3d(0,0,p.BlockHeightMm*scale));
            SolidPrimitiveFactory.Subtract(ref block, new[] { SolidPrimitiveFactory.Cylinder(point(0,0,p.SupportTopMm-2),point(0,0,p.SupportTopMm+p.BlockHeightMm+2),radius*scale) }, "U3 承重块贴管弧面");
            parts.Add(SolidPrimitiveFactory.Element(block, SupportSteelAppearance.Color));
            if (p.RubberMm > 0)
            {
                double width = p.Clamp.Row.Bolt + 4;
                var liner = SolidPrimitiveFactory.Cylinder(point(0,0,-width/2),point(0,0,width/2),(radius+p.RubberMm)*scale);
                SolidPrimitiveFactory.Subtract(ref liner,new[] { SolidPrimitiveFactory.Cylinder(point(0,0,-width/2-2),point(0,0,width/2+2),radius*scale) }, "U3 EPDM 衬垫");
                parts.Add(SolidPrimitiveFactory.Element(liner, 0));
            }
            return parts;
        }
    }
}
