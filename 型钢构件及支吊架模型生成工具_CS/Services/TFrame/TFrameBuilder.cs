using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class TFrameBuilder
    {
        private sealed class Frame
        {
            internal double X,Y,Z,Ux,Uy,Uz,Vx,Vy,Vz,Scale;
            internal DPoint3d P(double u,double v,double w)
            {return new DPoint3d((X+u*Ux+v*Vx)*Scale,(Y+u*Uy+v*Vy)*Scale,
                (Z+u*Uz+v*Vz+w)*Scale);}
            internal DVector3d V(double u,double v,double w)
            {return new DVector3d(u*Ux+v*Vx,u*Uy+v*Vy,u*Uz+v*Vz+w);}
        }
        internal static IList<Element> Build(TFramePlan plan,PipeClampSelection line)
        {
            if(plan==null||line==null)throw new InvalidOperationException("请先点取辅助线。");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("T 型架需要三维活动模型。");
            var f=plan.Parameters.Kind=="D15"?Horizontal(plan,line):Vertical(plan,line);
            var result=new List<Element>();
            if(plan.Parameters.Kind=="D15")BuildHorizontal(result,plan,f);
            else BuildVertical(result,plan,f);
            return result;
        }
        private static Frame Vertical(TFramePlan plan,PipeClampSelection line)
        {
            double angle=plan.Parameters.HeadingDegrees*Math.PI/180;
            bool first=line.StartZ<=line.EndZ;
            return new Frame{X=first?line.StartX:line.EndX,Y=first?line.StartY:line.EndY,
                Z=first?line.StartZ:line.EndZ,Ux=Math.Cos(angle),Uy=Math.Sin(angle),Uz=0,
                Vx=-Math.Sin(angle),Vy=Math.Cos(angle),Vz=0,
                Scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0};
        }
        private static Frame Horizontal(TFramePlan plan,PipeClampSelection line)
        {
            double dx=line.AxisX,dy=line.AxisY,dz=line.AxisZ;
            double length=Math.Sqrt(dx*dx+dy*dy+dz*dz);
            double horizontal=Math.Sqrt(dx*dx+dy*dy);
            if(length<=0||horizontal<=0)throw new InvalidOperationException("水平辅助线方向无效。");
            return new Frame{X=line.StartX,Y=line.StartY,Z=line.StartZ,
                Ux=dx/length,Uy=dy/length,Uz=dz/length,
                Vx=-dy/horizontal,Vy=dx/horizontal,Vz=0,
                Scale=Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter/1000.0};
        }
        private static void BuildVertical(List<Element> result,TFramePlan plan,Frame f)
        {
            var v=plan.Variant;
            bool angle=v.FamilyA=="equal_angle";
            double bottom=plan.GroundLiftMm;
            if(plan.Parameters.Kind=="D12"&&plan.Parameters.Type==2)
                bottom=angle?-(v.DepthA-v.FlangeA-10):0;
            var postMode=ProfileLookup.Mode(RuntimeData.Families,v.FamilyA,v.ProfileA,"geometric_center");
            result.Add(SteelMemberFactory.AlongAxis(postMode,
                f.P(0,plan.PostVOffsetMm,bottom),f.Scale,
                angle?f.V(0,1,0):f.V(0,-1,0),
                angle?f.V(-1,0,0):f.V(1,0,0),f.V(0,0,1),plan.PostLengthMm,7));
            double top=plan.Parameters.Type==2?0:plan.HeightMm;
            var armMode=ProfileLookup.Mode(RuntimeData.Families,v.FamilyB,v.ProfileB,"geometric_center");
            result.Add(SteelMemberFactory.AlongAxis(armMode,
                f.P(-plan.L2Mm/2,0,top-v.DepthA/2),f.Scale,
                angle?f.V(0,-1,0):f.V(0,1,0),
                angle?f.V(0,0,-1):f.V(0,0,1),f.V(1,0,0),plan.L2Mm,7));
            if(v.Ground!=null)
                result.AddRange(PortalFrameBuilder.BuildGround(v.Ground,f.X,f.Y,f.Z,f.Scale));
        }
        private static void BuildHorizontal(List<Element> result,TFramePlan plan,Frame f)
        {
            var v=plan.Variant;
            var modeA=ProfileLookup.Mode(RuntimeData.Families,v.FamilyA,v.ProfileA,"geometric_center");
            var axesA=TFrameSectionAxes.Post(v.FamilyA);
            result.Add(SteelMemberFactory.AlongAxis(modeA,f.P(0,0,0),f.Scale,
                f.V(axesA.Xu,axesA.Xv,axesA.Xw),
                f.V(axesA.Yu,axesA.Yv,axesA.Yw),f.V(1,0,0),plan.L1Mm,7));
            var modeB=ProfileLookup.Mode(RuntimeData.Families,v.FamilyB,v.ProfileB,"geometric_center");
            var axesB=TFrameSectionAxes.Arm(v.FamilyB);
            result.Add(SteelMemberFactory.AlongAxis(modeB,
                f.P(plan.L1Mm+v.FitU,plan.ArmStartVMm,plan.ArmStartWMm),f.Scale,
                f.V(axesB.Xu,axesB.Xv,axesB.Xw),
                f.V(axesB.Yu,axesB.Yv,axesB.Yw),f.V(0,1,0),plan.L2Mm,7));
        }
    }
}
