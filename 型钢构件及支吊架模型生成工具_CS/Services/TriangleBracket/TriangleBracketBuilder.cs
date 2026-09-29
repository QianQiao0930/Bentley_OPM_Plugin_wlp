using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class TriangleBracketBuilder
    {
        private sealed class Frame
        {
            internal double Ox,Oy,Oz,Rx,Ry,Tx,Ty,Scale;
            internal DPoint3d P(double x,double y,double z)
            {return new DPoint3d((Ox+x*Rx+y*Tx)*Scale,(Oy+x*Ry+y*Ty)*Scale,(Oz+z)*Scale);}
            internal DVector3d R {get{return new DVector3d(Rx,Ry,0);}}
            internal DVector3d T {get{return new DVector3d(Tx,Ty,0);}}
            internal DVector3d Z {get{return new DVector3d(0,0,1);}}
            internal DVector3d V(double x,double y,double z)
            {return new DVector3d((x*Rx+y*Tx)*Scale,(x*Ry+y*Ty)*Scale,z*Scale);}
        }
        internal static IList<Element> Build(TriangleBracketPlan plan,PipeClampSelection line)
        {
            if(plan==null||line==null)throw new InvalidOperationException("请先点取水平辅助线。");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("三角架需要三维活动模型。");
            double dx=line.AxisX,dy=line.AxisY,length=Math.Sqrt(dx*dx+dy*dy);
            if(length<=1e-9)throw new InvalidOperationException("辅助线方向无效。");
            double rx=dx/length,ry=dy/length;
            double ox=plan.Parameters.Reverse?line.EndX:line.StartX;
            double oy=plan.Parameters.Reverse?line.EndY:line.StartY;
            double oz=plan.Parameters.Reverse?line.EndZ:line.StartZ;
            if(plan.Parameters.Reverse){rx=-rx;ry=-ry;}
            var f=new Frame {Ox=ox,Oy=oy,Oz=oz,Rx=rx,Ry=ry,
                Tx=-ry,Ty=rx,Scale=model.GetModelInfo().UorPerMeter/1000.0};
            var parts=new List<Element>();
            int sides=plan.Parameters.Kind=="D19"?2:1;
            for(int side=0;side<sides;side++)
            {
                double sign=sides==1?1:(side==0?-1:1);
                double outer=sides==1?0:sign*plan.Variant.WebGap/2;
                parts.Add(SolidPrimitiveFactory.Element(Brace(f,plan,outer,sign),7));
                parts.Add(SolidPrimitiveFactory.Element(Beam(f,plan,outer,sign),7));
            }
            if(plan.Parameters.Kind=="D19")
            {
                var v=plan.Variant;
                double z=-v.HeightA/2;
                parts.Add(SolidPrimitiveFactory.Element(Box(f,plan.L2Mm,plan.L2Mm+v.ConnectorThickness,
                    -v.ConnectorLength/2,v.ConnectorLength/2,
                    z-v.ConnectorHeight/2,z+v.ConnectorHeight/2),7));
            }
            if(plan.Parameters.Kind=="G12")AddG12Bolts(parts,f,plan);
            if(plan.Plate!=null)
            {
                double offset=plan.Parameters.PlateOffsetMm;
                double faceOffset=plan.Variant.HeightB*Math.Sqrt(2)/2;
                double braceZ=plan.Parameters.Type==1
                    ?plan.P3ZMm+plan.BeamStartMm-faceOffset
                    :plan.P3ZMm-plan.BeamStartMm+faceOffset;
                parts.AddRange(G2AnchorBuilder.Build(plan.Plate,f.P(offset,0,-plan.Variant.HeightA/2)));
                parts.AddRange(G2AnchorBuilder.Build(plan.Plate,f.P(offset,0,braceZ)));
            }
            return parts;
        }
        private static SolidKernelEntity Beam(Frame f,TriangleBracketPlan plan,double outer,double sign)
        {
            var v=plan.Variant;
            bool channel=plan.Parameters.Kind!="D5";
            var mode=Profile(v.SectionA,channel?"web_outside_center":"geometric_center");
            return SteelMemberFactory.AlongAxisBody(mode,
                f.P(plan.BeamStartMm,outer,-v.HeightA/2),f.Scale,
                channel?new DVector3d(f.Tx*sign,f.Ty*sign,0):f.T,
                f.Z,f.R,plan.BeamLengthMm);
        }
        private static SolidKernelEntity Brace(Frame f,TriangleBracketPlan plan,double outer,double sign)
        {
            var v=plan.Variant;
            bool channel=plan.Parameters.Kind!="D5";
            double ux=1/Math.Sqrt(2),uz=plan.Parameters.Type==1?ux:-ux;
            var along=new DVector3d(f.Rx*ux,f.Ry*ux,uz);
            double overrun=channel?v.HeightB+v.WebB:v.HeightB+v.WebB;
            bool cutRoot=!channel||plan.Parameters.Kind=="D19";
            double startX=cutRoot?-ux*overrun:0;
            double startZ=plan.P3ZMm+(cutRoot?-uz*overrun:0);
            double total=plan.BraceLengthMm+overrun+(cutRoot?overrun:0);
            DVector3d heightDir;
            string modeId;
            double y=outer;
            if(channel)
            {
                heightDir=new DVector3d(-f.Rx*uz,-f.Ry*uz,ux);
                modeId="web_outside_center";
            }
            else
            {
                double typeSign=plan.Parameters.Type==1?1:-1;
                heightDir=new DVector3d(f.Rx*typeSign*uz,f.Ry*typeSign*uz,-typeSign*ux);
                modeId="outer_corner";
                y=-v.HeightB/2;
            }
            var body=SteelMemberFactory.AlongAxisBody(Profile(v.SectionB,modeId),
                f.P(startX,y,startZ),f.Scale,
                channel?new DVector3d(f.Tx*sign,f.Ty*sign,0):f.T,
                heightDir,along,total);
            double big=10000;
            if(cutRoot)
                SolidPrimitiveFactory.Subtract(ref body,new[]{Box(f,-big,plan.BeamStartMm,
                    -big,big,-big,big)},"斜撑根部剪切");
            if(plan.Parameters.Type==1)
                SolidPrimitiveFactory.Subtract(ref body,new[]{Box(f,-big,big,-big,big,
                    plan.P1ZMm,big)},"斜撑横担端剪切");
            else
                SolidPrimitiveFactory.Subtract(ref body,new[]{Box(f,-big,big,-big,big,
                    -big,plan.P1ZMm)},"斜撑横担端剪切");
            return body;
        }
        private static void AddG12Bolts(List<Element> parts,Frame f,TriangleBracketPlan plan)
        {
            var v=plan.Variant;
            double heading=Math.Atan2(f.Ty,f.Tx)*180/Math.PI;
            foreach(double distance in new[]{75.0,75.0+v.BoltSpacing})
            {
                foreach(bool beam in new[]{true,false})
                {
                    double web=beam?v.WebA:v.WebB;
                    var bolt=G2AnchorCalculator.Calculate(new G2AnchorParameters {
                        SubtypeKey=v.BoltSubtype,HeadingDegrees=heading });
                    bolt.PlateThicknessMm=web;
                    bolt.BoltOutLengthMm=web+bolt.WasherThicknessMm+bolt.NutHeightMm+
                        G2AnchorCatalog.BoltProtrusionMm;
                    bolt.ActualEmbedmentMm=bolt.BoltLengthMm-bolt.BoltOutLengthMm;
                    if(bolt.ActualEmbedmentMm<bolt.RequiredEmbedmentMm)
                        throw new InvalidOperationException("G12 锚栓有效埋深不足。");
                    bolt.SleeveLengthMm=bolt.ActualEmbedmentMm*G2AnchorCatalog.SleeveEmbedFraction;
                    double z=beam?-v.HeightA/2:plan.P3ZMm+
                        (plan.P1ZMm-plan.P3ZMm)*distance/plan.L1Mm;
                    var frame=new G2AnchorFrame(f.P(distance,0,z),f.Scale,heading,G2MountFace.Wall);
                    parts.AddRange(G2AnchorBuilder.BuildSingleBolt(bolt,frame));
                }
            }
        }
        private static ModeData Profile(string section,string mode)
        {
            string family,name;
            if(section.StartsWith("[")) {family="parallel_channel";name=section.Substring(1);}
            else if(section.StartsWith("L")) {family="equal_angle";name=section;}
            else {family="hot_rolled_h";name=section+"xr";}
            var data=ProfileLookup.Family(RuntimeData.Families,family);
            if(data==null)throw new InvalidOperationException("型钢目录缺少 "+family);
            var profile=data.Profiles.FirstOrDefault(x=>x.Name.StartsWith(name,StringComparison.Ordinal));
            if(profile==null)throw new InvalidOperationException("型钢目录缺少 "+section);
            return ProfileLookup.Mode(RuntimeData.Families,family,profile.Name,mode);
        }
        private static SolidKernelEntity Box(Frame f,double x0,double x1,double y0,double y1,double z0,double z1)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{f.P(x0,y0,z0),f.P(x1,y0,z0),
                f.P(x1,y1,z0),f.P(x0,y1,z0)},f.V(0,0,z1-z0));
        }
    }
}
