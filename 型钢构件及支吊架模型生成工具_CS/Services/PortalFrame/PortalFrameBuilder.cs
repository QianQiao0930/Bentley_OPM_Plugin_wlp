using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class PortalFrameBuilder
    {
        private sealed class Frame
        {
            internal double X,Y,Z,Ux,Uy,Vx,Vy,Scale;
            internal DPoint3d P(double u,double v,double w)
            {return new DPoint3d((X+u*Ux+v*Vx)*Scale,(Y+u*Uy+v*Vy)*Scale,(Z+w)*Scale);}
            internal DVector3d Axis(double u,double v,double w)
            {return new DVector3d(u*Ux+v*Vx,u*Uy+v*Vy,w);}
            internal DVector3d V(double u,double v,double w)
            {return new DVector3d((u*Ux+v*Vx)*Scale,(u*Uy+v*Vy)*Scale,w*Scale);}
        }
        internal static IList<Element> Build(PortalFramePlan plan,PipeClampSelection line)
        {
            if(plan==null||line==null)throw new InvalidOperationException("请先选择竖直辅助线。");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("门型架需要三维活动模型。");
            if(plan.Parameters.Kind=="D16")return BuildHorizontal(plan,line,model.GetModelInfo().UorPerMeter/1000.0);
            double a=plan.Parameters.HeadingDegrees*Math.PI/180;
            var f=new Frame{X=line.StartZ<=line.EndZ?line.StartX:line.EndX,
                Y=line.StartZ<=line.EndZ?line.StartY:line.EndY,
                Z=Math.Min(line.StartZ,line.EndZ),Ux=Math.Cos(a),Uy=Math.Sin(a),
                Vx=-Math.Sin(a),Vy=Math.Cos(a),Scale=model.GetModelInfo().UorPerMeter/1000.0};
            var result=new List<Element>();
            string kind=plan.Parameters.Kind;
            bool angle=plan.Variant.PostFamily=="equal_angle";
            for(int side=0;side<2;side++)
            {
                double u=(side==0?-1:1)*plan.PostPitchMm/2;
                double bottom=kind=="D8"&&plan.Parameters.Type>=3
                    ?-(plan.Variant.ArmDepth-plan.Variant.ArmFlange-10):plan.GroundLiftMm;
                if(kind=="D8"&&plan.Parameters.Type<3||kind=="D13")bottom=0;
                DVector3d xx,yy;
                if(angle&&side==0){xx=f.Axis(0,1,0);yy=f.Axis(-1,0,0);}
                else if(angle){xx=f.Axis(1,0,0);yy=f.Axis(0,1,0);}
                else{xx=f.Axis(0,-1,0);yy=f.Axis(1,0,0);}
                var mode=Mode(plan.Variant.PostFamily,plan.Variant.PostProfile);
                result.Add(SteelMemberFactory.AlongAxis(mode,f.P(u,plan.PostVOffsetMm,bottom),
                    f.Scale,xx,yy,f.Axis(0,0,1),plan.PostLengthMm,7));
            }
            double top=(kind=="D8"&&plan.Parameters.Type>=3||kind=="D13"&&plan.Parameters.Type==2)
                ?0:plan.HeightMm;
            double armStart=(kind=="G6"||kind=="D20")?-plan.SpanMm/2:-plan.ArmLengthMm/2;
            double armLength=(kind=="G6"||kind=="D20")?plan.SpanMm:plan.ArmLengthMm;
            if(kind=="G6"||kind=="D20")
            {
                double v=plan.Variant.ChannelGap/2+plan.Variant.ArmWidth/2;
                AddArm(result,f,plan,armStart,armLength,v,top,false);
                AddArm(result,f,plan,armStart,armLength,-v,top,true);
            }
            else AddArm(result,f,plan,armStart,armLength,0,top,false);
            if(plan.Variant.Ground!=null)
                foreach(int side in new[]{-1,1})
                {
                    double u=side*plan.PostPitchMm/2,v=plan.PostVOffsetMm;
                    // Python 地脚板始终沿模型 X/Y 轴；只把中心随门架方向移动。
                    var ground=new Frame{X=f.X+u*f.Ux+v*f.Vx,Y=f.Y+u*f.Uy+v*f.Vy,
                        Z=f.Z,Ux=1,Uy=0,Vx=0,Vy=1,Scale=f.Scale};
                    AddGround(result,ground,plan.Variant.Ground,0,0);
                }
            return result;
        }
        private static IList<Element> BuildHorizontal(PortalFramePlan plan,PipeClampSelection line,double scale)
        {
            double dx=line.EndX-line.StartX,dy=line.EndY-line.StartY;
            double length=Math.Sqrt(dx*dx+dy*dy);
            if(length<1e-9)throw new InvalidOperationException("请选择有效水平辅助线。");
            var f=new Frame{X=line.StartX,Y=line.StartY,Z=line.StartZ,Ux=dx/length,Uy=dy/length,
                Vx=-dy/length,Vy=dx/length,Scale=scale};
            var result=new List<Element>();
            // 两侧 A 腹板/竖肢背靠背，开口向外；角钢水平肢在上。
            bool angleA=plan.Variant.PostFamily=="equal_angle";
            foreach(int side in new[]{-1,1})result.Add(SteelMemberFactory.AlongAxis(
                Mode(plan.Variant.PostFamily,plan.Variant.PostProfile),f.P(plan.MemberAStartMm,side*plan.PostPitchMm/2,0),
                scale,f.Axis(0,side,0),f.Axis(0,0,angleA?-1:1),f.Axis(1,0,0),plan.PostLengthMm,7));
            if(plan.Plate!=null){
                plan.Plate.Parameters.HeadingDegrees=Math.Atan2(f.Uy,f.Ux)*180/Math.PI;
                foreach(int side in new[]{-1,1})result.AddRange(G2AnchorBuilder.Build(plan.Plate,
                    f.P(plan.Parameters.PlateOffsetMm,side*plan.PostPitchMm/2,0)));
            }
            bool angleB=plan.Variant.ArmFamily=="equal_angle";
            foreach(double station in plan.MemberBStationsMm)
            {
                // 类型 1 竖肢/腹板朝外端；类型 2 两根 B 腹板背靠背、开口向外。
                double sectionX=plan.Parameters.Type==2&&station>plan.L1Mm?1:-1;
                result.Add(SteelMemberFactory.AlongAxis(
                    Mode(plan.Variant.ArmFamily,plan.Variant.ArmProfile),f.P(station,-plan.ArmLengthMm/2,0),
                    scale,f.Axis(sectionX,0,0),f.Axis(0,0,angleB?-1:1),f.Axis(0,1,0),plan.ArmLengthMm,7));
            }
            return result;
        }
        private static void AddArm(List<Element> result,Frame f,PortalFramePlan plan,
            double start,double length,double v,double top,bool mirror)
        {
            bool angle=plan.Variant.ArmFamily=="equal_angle";
            DVector3d xx=angle?f.Axis(0,-1,0):f.Axis(0,mirror?-1:1,0);
            DVector3d yy=angle?f.Axis(0,0,-1):f.Axis(0,0,mirror?-1:1);
            result.Add(SteelMemberFactory.AlongAxis(
                Mode(plan.Variant.ArmFamily,plan.Variant.ArmProfile),
                f.P(start,v,top-plan.Variant.ArmDepth/2),f.Scale,xx,yy,f.Axis(1,0,0),
                length,7));
        }
        private static ModeData Mode(string family,string name)
        {return ProfileLookup.Mode(RuntimeData.Families,family,name,"geometric_center");}
        internal static IList<Element> BuildGround(PortalGroundSpec spec,
            double xMm,double yMm,double zMm,double uorPerMm)
        {
            var frame=new Frame{X=xMm,Y=yMm,Z=zMm,Ux=1,Uy=0,Vx=0,Vy=1,Scale=uorPerMm};
            var result=new List<Element>();
            AddGround(result,frame,spec,0,0);
            return result;
        }
        private static void AddGround(List<Element> result,Frame f,PortalGroundSpec g,double u,double v)
        {
            double h=g.PlateSide/2,spacing=g.HoleSpacing/2;
            var plate=SolidPrimitiveFactory.PolygonPrism(Square(f,u,v,25,h),f.V(0,0,g.PlateThickness));
            var cutters=new List<SolidKernelEntity>();
            foreach(int sx in new[]{-1,1})foreach(int sy in new[]{-1,1})
                cutters.Add(SolidPrimitiveFactory.Cylinder(
                    f.P(u+sx*spacing,v+sy*spacing,23),
                    f.P(u+sx*spacing,v+sy*spacing,27+g.PlateThickness),
                    g.HoleDiameter/2*f.Scale));
            SolidPrimitiveFactory.Subtract(ref plate,cutters,"门型架锚板孔");
            result.Add(SolidPrimitiveFactory.Element(plate,7));
            double nutHeight=g.BoltDiameter==8?6.5:g.BoltDiameter==12?10:
                g.BoltDiameter==16?13:16;
            double nutFlat=g.BoltDiameter==8?13:g.BoltDiameter==12?19:
                g.BoltDiameter==16?24:30;
            double boltTop=25+g.PlateThickness+nutHeight+5;
            foreach(int sx in new[]{-1,1})foreach(int sy in new[]{-1,1})
            {
                double x=u+sx*spacing,y=v+sy*spacing;
                result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(
                    f.P(x,y,boltTop-g.BoltLength),f.P(x,y,boltTop),g.BoltDiameter/2*f.Scale),7));
                var nut=new List<DPoint3d>();double radius=nutFlat/Math.Sqrt(3);
                for(int i=0;i<6;i++)
                {double a=i*Math.PI/3;nut.Add(f.P(x+radius*Math.Cos(a),y+radius*Math.Sin(a),
                    25+g.PlateThickness));}
                result.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(nut,
                    f.V(0,0,nutHeight)),7));
            }
            // 与 Python 公共锚板模块一致：方体减去四条顶边外侧的楔体。
            // BodyFromLoft 对这两张矩形截面在 OPM 中会返回 Error，不能用作唯一建模路径。
            var grout=SolidPrimitiveFactory.PolygonPrism(Square(f,u,v,0,h+20),f.V(0,0,25));
            double outer=h+20,extension=4,over=5;
            // (outer+extension,-over) 与 (h-extension,25+over) 同在斜面延长线上。
            // 刀具体积略超出方体，避免恰好共面的边界使布尔差集失败。
            foreach(int sign in new[]{-1,1})
            {
                var yWedge=SolidPrimitiveFactory.PolygonPrism(new[]{
                    f.P(u-outer-over,v+sign*(outer+extension),-over),
                    f.P(u-outer-over,v+sign*(outer+extension),25+over),
                    f.P(u-outer-over,v+sign*(h-extension),25+over)},
                    f.V(2*(outer+over),0,0));
                SolidPrimitiveFactory.Subtract(ref grout,new[]{yWedge},"现场灌浆梯台 Y 侧斜面");
                var xWedge=SolidPrimitiveFactory.PolygonPrism(new[]{
                    f.P(u+sign*(outer+extension),v-outer-over,-over),
                    f.P(u+sign*(outer+extension),v-outer-over,25+over),
                    f.P(u+sign*(h-extension),v-outer-over,25+over)},
                    f.V(0,2*(outer+over),0));
                SolidPrimitiveFactory.Subtract(ref grout,new[]{xWedge},"现场灌浆梯台 X 侧斜面");
            }
            result.Add(SolidPrimitiveFactory.Element(grout,5));
        }
        private static DPoint3d[] Square(Frame f,double u,double v,double z,double half)
        {return new[]{f.P(u-half,v-half,z),f.P(u+half,v-half,z),
            f.P(u+half,v+half,z),f.P(u-half,v+half,z)};}
    }
}
