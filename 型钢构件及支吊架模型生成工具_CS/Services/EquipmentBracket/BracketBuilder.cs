using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class BracketBuilder
    {
        private sealed class Frame
        {
            internal double Ox,Oy,Oz,Rx,Ry,Tx,Ty,Scale;
            internal DPoint3d P(double r,double t,double z)
            {return new DPoint3d((Ox+r*Rx+t*Tx)*Scale,(Oy+r*Ry+t*Ty)*Scale,(Oz+z)*Scale);}
            internal DVector3d R {get{return new DVector3d(Rx,Ry,0);}}
            internal DVector3d T {get{return new DVector3d(Tx,Ty,0);}}
            internal DVector3d Z {get{return new DVector3d(0,0,1);}}
        }
        internal static IList<Element> Build(BracketPlan plan,PipeClampSelection line)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("N3/N4 需要三维活动模型。");
            BracketCalculator.ValidateHorizontal(line);
            double dx=line.AxisX,dy=line.AxisY,length=Math.Sqrt(dx*dx+dy*dy);
            if(length<=0)throw new InvalidOperationException("辅助线方向无效。");
            double rx=dx/length,ry=dy/length;
            double startX=plan.Reverse?line.EndX:line.StartX;
            double startY=plan.Reverse?line.EndY:line.StartY;
            double startZ=plan.Reverse?line.EndZ:line.StartZ;
            if(plan.Reverse){rx=-rx;ry=-ry;}
            if(plan.Double)
            {
                // Source line: equipment centre -> pipe centre. Move the working origin
                // back from the pipe centre by L1 to the outer face of the end plate.
                double pipeX=startX+plan.L*rx,pipeY=startY+plan.L*ry;
                startX=pipeX-plan.L1*rx;startY=pipeY-plan.L1*ry;
            }
            var f=new Frame {Ox=startX,Oy=startY,Oz=startZ,Rx=rx,Ry=ry,
                Tx=-ry,Ty=rx,Scale=model.GetModelInfo().UorPerMeter/1000.0};
            var parts=new List<Element>();
            SolidKernelEntity frameBody=null;
            var beamBodies=new List<SolidKernelEntity>();
            var stiffenerBodies=new List<SolidKernelEntity>();
            int subtype=plan.Subtype-'A';
            double flange=BracketCatalog.AFlange[subtype];
            bool channel=plan.SectionA.StartsWith("[");
            double heading=Math.Atan2(ry,rx)*180/Math.PI;
            var n8=N8Catalog.Resolve(plan.PlateType,"N",heading+180,G2MountFace.Wall);
            int sides=plan.Double?2:1;
            for(int side=0;side<sides;side++)
            {
                double offset=plan.Double?(side==0?-plan.L2/2:plan.L2/2):0;
                double beamStart=plan.Double?0:plan.PlateThickness;
                double beamZ=-plan.SectionAHeight/2;
                var beamBody=SteelMemberFactory.AlongAxisBody(Profile(plan.SectionA),
                    f.P(beamStart,offset,beamZ),f.Scale,f.T,f.Z,f.R,plan.BeamLength);
                beamBodies.Add(beamBody);
                // The brace ends at the contact face of the beam. Its centreline is
                // tilted 45 degrees in the radial/vertical plane.
                double braceZ0=plan.Type==1?-plan.H:plan.H;
                double braceZ1=plan.Type==1?-plan.SectionAHeight:0;
                double braceR0=plan.Double?0:plan.PlateThickness;
                double braceR1=braceR0+plan.BraceRun;
                double vr=braceR1-braceR0,vz=braceZ1-braceZ0;
                double vl=Math.Sqrt(vr*vr+vz*vz);
                var along=new DVector3d(f.Rx*vr/vl,f.Ry*vr/vl,vz/vl);
                var normal=new DVector3d(-f.Rx*vz/vl,-f.Ry*vz/vl,vr/vl);
                const double overrun=50;
                var braceBody=SteelMemberFactory.AlongAxisBody(Profile(plan.SectionB),
                    f.P(braceR0-overrun*vr/vl,offset,braceZ0-overrun*vz/vl),
                    f.Scale,f.T,normal,along,vl+2*overrun);
                double big=Math.Max(2000,plan.L+plan.BeamLength+plan.H+100);
                // Match Python N3/N4: trim the extended brace at the equipment
                // face and at the underside/topside of the crossbeam.
                SolidPrimitiveFactory.Subtract(ref braceBody,new[]{BoxBody(f,
                    -big,braceR0,-big,big,-big,big)},
                    "斜撑设备端剪切");
                if(plan.Type==1)
                    SolidPrimitiveFactory.Subtract(ref braceBody,new[]{BoxBody(f,
                        -big,big,-big,big,-plan.SectionAHeight,big)},
                        "斜撑横担端剪切");
                else
                    SolidPrimitiveFactory.Subtract(ref braceBody,new[]{BoxBody(f,
                        -big,big,-big,big,-big,0)},
                        "斜撑横担端剪切");
                parts.Add(SolidPrimitiveFactory.Element(braceBody,7));
                double plateOrigin=plan.Double?0:plan.PlateThickness;
                parts.AddRange(N8Builder.Build(n8,f.P(plateOrigin,offset,beamZ)));
                parts.AddRange(N8Builder.Build(n8,f.P(plateOrigin,offset,braceZ0)));
                stiffenerBodies.Add(Stiffener(f,braceR1,offset,plan,flange,channel,
                    side==0?-1:1));
            }
            frameBody=beamBodies[0];
            if(plan.Double)
            {
                double overlap=Math.Max(2,plan.SectionAWeb/2);
                foreach(int sign in new[]{-1,1})
                {
                    double edge=sign<0?plan.L1-plan.L4:plan.L1+plan.L3;
                    double r=edge+sign*plan.SectionCWidth/2;
                    var axisX=new DVector3d(sign*f.Rx,sign*f.Ry,0);
                    var cBody=SteelMemberFactory.AlongAxisBody(Profile(plan.SectionC),
                        f.P(r,-plan.ConnectorSpan/2-overlap,
                            -BracketCatalog.CHeight[subtype]/2),f.Scale,
                        axisX,f.Z,f.T,plan.ConnectorSpan+2*overlap);
                    Merge(ref frameBody,cBody,"构件 C 与横担融合");
                    foreach(double t in new[]{-plan.L2/2,plan.L2/2})
                        stiffenerBodies.Add(Stiffener(f,
                            channel?edge:r,t,plan,flange,channel,t<0?-1:1));
                }
                if(plan.ShowPreweld&&plan.Preweld>2*plan.PlateThickness)
                {
                    // Display-only reference geometry: never included in the BOM.
                    foreach(double t in new[]{-plan.L2/2,plan.L2/2})
                    {
                        foreach(double z in new[]{-plan.SectionAHeight/2,plan.Type==1?-plan.H:plan.H})
                        {
                            var baseFrame=new G2AnchorFrame(f.P(0,t,z),f.Scale,
                                heading+180,G2MountFace.Wall);
                            var padFrame=new G2AnchorFrame(baseFrame.Point(plan.PlateThickness,0,0),
                                f.Scale,heading+180,G2MountFace.Wall);
                            parts.Add(Transparent(N8Builder.BuildPlate(n8,padFrame)));
                            var tubeOuter=SolidPrimitiveFactory.Cylinder(
                                baseFrame.Point(2*plan.PlateThickness,0,0),
                                baseFrame.Point(plan.Preweld,0,0),50*f.Scale);
                            var tubeInner=SolidPrimitiveFactory.Cylinder(
                                baseFrame.Point(2*plan.PlateThickness-2,0,0),
                                baseFrame.Point(plan.Preweld+2,0,0),46*f.Scale);
                            SolidPrimitiveFactory.Subtract(ref tubeOuter,new[]{tubeInner},"预焊件空心管");
                            parts.Add(Transparent(SolidPrimitiveFactory.Element(tubeOuter,3)));
                        }
                    }
                }
            }
            if(plan.Double)Merge(ref frameBody,beamBodies[1],"第二根横担融合");
            foreach(var stiffener in stiffenerBodies)
                Merge(ref frameBody,stiffener,"筋板与横担融合");
            if(frameBody!=null)parts.Add(SolidPrimitiveFactory.Element(frameBody,7));
            return parts;
        }
        private static void Merge(ref SolidKernelEntity frame,SolidKernelEntity body,string name)
        {
            if(frame==null)frame=body;
            else SolidPrimitiveFactory.Union(ref frame,new[]{body},name);
        }
        private static SolidKernelEntity Stiffener(Frame f,double r,
            double offset,BracketPlan plan,double flange,bool channel,int sideSign)
        {
            bool fullWidth=channel||!plan.Double;
            double t0=fullWidth?offset-plan.SectionAWidth/2:
                (sideSign<0?offset-plan.SectionAWidth/2:offset);
            double t1=fullWidth?offset+plan.SectionAWidth/2:
                (sideSign<0?offset:offset+plan.SectionAWidth/2);
            return BoxBody(f,r-5,r+5,t0,t1,
                -plan.SectionAHeight+flange,-flange);
        }
        private static Element Member(string spec,Frame f,double r,double t,double z,
            DVector3d axisX,DVector3d axisY,DVector3d axisZ,double length,uint color)
        {
            var mode=Profile(spec);
            return SteelMemberFactory.AlongAxis(mode,f.P(r,t,z),f.Scale,
                axisX,axisY,axisZ,length,color);
        }
        private static ModeData Profile(string spec)
        {
            bool channel=spec.StartsWith("[");
            string family=channel?"parallel_channel":"hot_rolled_h";
            string prefix=channel?spec.Substring(1):spec+"xr";
            var data=ProfileLookup.Family(RuntimeData.Families,family);
            if(data==null)throw new InvalidOperationException("型钢目录缺少 "+family);
            var profile=data.Profiles.FirstOrDefault(x=>channel?x.Name==prefix:
                x.Name.StartsWith(prefix,StringComparison.Ordinal));
            if(profile==null)throw new InvalidOperationException("型钢目录缺少 "+spec);
            return ProfileLookup.Mode(RuntimeData.Families,family,profile.Name,"geometric_center");
        }
        private static Element Box(Frame f,double r0,double r1,double t0,double t1,double z0,double z1)
        {return SolidPrimitiveFactory.Element(BoxBody(f,r0,r1,t0,t1,z0,z1),7);}
        private static SolidKernelEntity BoxBody(Frame f,double r0,double r1,double t0,double t1,double z0,double z1)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{f.P(r0,t0,z0),f.P(r1,t0,z0),
                f.P(r1,t1,z0),f.P(r0,t1,z0)},new DVector3d(0,0,(z1-z0)*f.Scale));
        }
        private static Element Transparent(Element element)
        {
            var style=new ElementPropertiesSetter();
            style.SetTransparency(0.75);
            if(!style.Apply(element))throw new InvalidOperationException("设备预焊件透明度设置失败。");
            return element;
        }
    }
}
