using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class L7GuideBuilder
    {
        internal static List<Element> Build(L7GuidePlan plan,DPoint3d center,DVector3d pipeAxis)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)
                throw new InvalidOperationException("保冷立管导向架需要三维 DGN 模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var parts=new List<Element>();
            var transform=DTransform3d.FromRotationAroundLine(center,pipeAxis,
                Angle.FromRadians(plan.AngleDeg*Math.PI/180));
            // T4 现成的承重板 + 耳板 + 紧固件，不带管托底座。
            foreach(var part in T4ShoeBuilder.BuildBearingClamp(plan.Bearing,
                plan.BearingBoolean,center,pipeAxis))
            {part.ApplyTransform(new TransformInfo(transform));parts.Add(part);}
            var clamp=A22ClampBuilder.Build(plan.Clamp,center,pipeAxis);
            foreach(var part in clamp) {part.ApplyTransform(new TransformInfo(transform));parts.Add(part);}
            if(!plan.HasMember)return parts;
            double[] zero,turn,along;
            A1ClampCalculator.RadialFrame(new[]{pipeAxis.X,pipeAxis.Y,pipeAxis.Z},
                out zero,out turn,out along);
            double radians=plan.AngleDeg*Math.PI/180;
            double c=Math.Cos(radians),s=Math.Sin(radians);
            var radial=new DVector3d(c*zero[0]+s*turn[0],c*zero[1]+s*turn[1],
                c*zero[2]+s*turn[2]);
            var tangent=new DVector3d(-s*zero[0]+c*turn[0],-s*zero[1]+c*turn[1],
                -s*zero[2]+c*turn[2]);
            var axial=new DVector3d(along[0],along[1],along[2]);
            var memberStart=new DPoint3d(center.X+plan.MemberStartMm*scale*radial.X,
                center.Y+plan.MemberStartMm*scale*radial.Y,
                center.Z+plan.MemberStartMm*scale*radial.Z);
            var mode=ProfileLookup.Mode(RuntimeData.Families,plan.MemberFamily,
                plan.MemberProfile,"geometric_center");
            parts.Add(SteelMemberFactory.AlongAxis(mode,memberStart,scale,tangent,axial,
                radial,plan.MemberLengthMm,4));
            if(plan.Connection!=null) {
                // 板背贴合构件末端，N8 +X 朝设备；预焊件位于板正面，由设备模型提供。
                double plateBack=plan.LengthMm-plan.Connection.T;
                var end=new DPoint3d(center.X+plateBack*scale*radial.X,
                    center.Y+plateBack*scale*radial.Y,center.Z+plateBack*scale*radial.Z);
                var frame=new G2AnchorFrame(end,scale,radial,tangent,axial);
                parts.AddRange(N8Builder.Build(plan.Connection,frame));
            }
            return parts;
        }
    }
}
