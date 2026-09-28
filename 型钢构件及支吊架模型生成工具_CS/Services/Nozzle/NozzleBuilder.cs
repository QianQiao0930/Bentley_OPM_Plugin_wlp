using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class NozzleBuilder
    {
        internal static Element Build(NozzlePlan plan,DPoint3d origin)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d) throw new InvalidOperationException("请在三维 DGN 模型中放置管口。");
            var f=new NozzleFrame(origin,model.GetModelInfo().UorPerMeter/1000.0,plan.Parameters.Axis);
            double pipeLength=plan.PipeLengthMm,total=plan.Parameters.TotalLengthMm;
            double overlap=1,size=plan.Size.PipeOutsideMm/2;
            SolidKernelEntity body=Cylinder(f,0,pipeLength+overlap,0,0,size);
            var additions=new List<SolidKernelEntity> {
                Cylinder(f,pipeLength,total,0,0,plan.Size.FlangeOutsideMm/2) };
            if(plan.Size.RaisedFaceOutsideMm>0 && plan.Size.RaisedFaceHeightMm>0)
                additions.Add(Cylinder(f,total-overlap,total+plan.Size.RaisedFaceHeightMm,
                    0,0,plan.Size.RaisedFaceOutsideMm/2));
            SolidPrimitiveFactory.Union(ref body,additions,"管段、法兰与密封面");
            SolidPrimitiveFactory.Subtract(ref body,new[]{Cylinder(f,-overlap,
                total+plan.Size.RaisedFaceHeightMm+2*overlap,0,0,plan.BoreRadiusMm)},"中心通孔");
            if(plan.Parameters.DrawBoltHoles && plan.Size.BoltCount>0)
            {
                var holes=new List<SolidKernelEntity>();
                for(int i=0;i<plan.Size.BoltCount;i++)
                {
                    var uv=NozzleCalculator.BoltOffset(i,plan.Size.BoltCount,plan.Size.BoltCircleMm/2);
                    holes.Add(Cylinder(f,pipeLength-overlap,total+overlap,
                        uv[0],uv[1],plan.Size.BoltHoleMm/2));
                }
                SolidPrimitiveFactory.Subtract(ref body,holes,"法兰螺栓孔");
            }
            return SolidPrimitiveFactory.Element(body,6);
        }
        private static SolidKernelEntity Cylinder(NozzleFrame f,double start,double end,
            double u,double v,double radius)
        { return SolidPrimitiveFactory.Cylinder(f.Point(start,u,v),f.Point(end,u,v),radius*f.Scale); }
    }
}
