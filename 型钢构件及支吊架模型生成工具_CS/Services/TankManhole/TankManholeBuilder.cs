using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Builds detached model elements. All dimensions are millimetres until Frame.Point.</summary>
    internal static class TankManholeBuilder
    {
        internal static List<Element> Build(TankManholePlan p,DPoint3d origin)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d) throw new InvalidOperationException("请在三维 DGN 模型中放置人孔。");
            var f=new TankManholeFrame(origin,model.GetModelInfo().UorPerMeter/1000.0,p.HeadingRadians);
            var result=new List<Element>();
            AddDisk(result,f,0,p.FlangeBackMm,p.Size.NeckOutsideMm/2,p.Size.BoreMm/2,7,null,p.BoltHoleRadiusMm);
            var holes=BoltHoles(p);
            AddDisk(result,f,p.FlangeBackMm,p.FlangeFrontMm,p.FlangeRadiusMm,p.Size.BoreMm/2,7,holes,p.BoltHoleRadiusMm);
            AddDisk(result,f,p.CoverBackMm,p.CoverFrontMm,p.FlangeRadiusMm,0,6,holes,p.BoltHoleRadiusMm);
            if(p.Parameters.IncludeBolts) AddBolts(result,f,p);
            AddHandles(result,f,p);
            if(p.Parameters.IncludeLifting && p.Parameters.CoverMode==TankCoverMode.Hinge) AddHinge(result,f,p);
            else if(p.Parameters.IncludeLifting) AddDavit(result,f,p);
            return result;
        }
        private static List<double[]> BoltHoles(TankManholePlan p)
        {
            var holes=new List<double[]>();
            for(int i=0;i<p.Size.BoltCount;i++) holes.Add(TankManholeCalculator.BoltPosition(i,p.Size.BoltCount,p.BoltCircleRadiusMm));
            return holes;
        }
        private static void AddDisk(List<Element> r,TankManholeFrame f,double x0,double x1,double outer,double bore,uint color,List<double[]> holes,double holeRadius)
        {
            var body=SolidPrimitiveFactory.Cylinder(f.Point(x0,0,0),f.Point(x1,0,0),outer*f.Scale);
            var cutters=new List<SolidKernelEntity>();
            if(bore>0) cutters.Add(SolidPrimitiveFactory.Cylinder(f.Point(x0-2,0,0),f.Point(x1+2,0,0),bore*f.Scale));
            if(holes!=null) foreach(var h in holes)
                cutters.Add(SolidPrimitiveFactory.Cylinder(f.Point(x0-2,h[0],h[1]),f.Point(x1+2,h[0],h[1]),
                    holeRadius*f.Scale));
            SolidPrimitiveFactory.Subtract(ref body,cutters,"法兰孔");
            r.Add(SolidPrimitiveFactory.Element(body,color));
        }
        private static void AddCylinder(List<Element> r,TankManholeFrame f,double x0,double y0,double z0,
            double x1,double y1,double z1,double radius,uint color)
        { r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(f.Point(x0,y0,z0),f.Point(x1,y1,z1),radius*f.Scale),color)); }
        private static SolidKernelEntity Plate(TankManholeFrame f,double x0,double x1,double y0,double y1,double z0,double thick)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{f.Point(x0,y0,z0),f.Point(x1,y0,z0),
                f.Point(x1,y1,z0),f.Point(x0,y1,z0)},new DVector3d(0,0,thick*f.Scale));
        }
        private static void AddPlate(List<Element> r,TankManholeFrame f,double x0,double x1,double y0,double y1,double z0,double thick,uint color)
        { r.Add(SolidPrimitiveFactory.Element(Plate(f,x0,x1,y0,y1,z0,thick),color)); }
        private static SolidKernelEntity Hex(TankManholeFrame f,double x,double y,double z,double across,double height,char axis)
        {
            double radius=across/Math.Sqrt(3); var pts=new List<DPoint3d>();
            for(int i=0;i<6;i++)
            {
                double a=Math.PI*i/3, c=radius*Math.Cos(a),s=radius*Math.Sin(a);
                pts.Add(axis=='x'?f.Point(x,y+c,z+s):axis=='y'?f.Point(x+c,y,z+s):f.Point(x+c,y+s,z));
            }
            var vector=axis=='x'?new DVector3d(f.Ux*height*f.Scale,f.Uy*height*f.Scale,0):
                axis=='y'?new DVector3d(f.Vx*height*f.Scale,f.Vy*height*f.Scale,0):
                new DVector3d(0,0,height*f.Scale);
            return SolidPrimitiveFactory.PolygonPrism(pts,vector);
        }
        private static void AddBolts(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            double d=p.Size.BoltDiameterMm,head=.6*d,nut=.8*d;
            foreach(var h in BoltHoles(p))
            {
                double y=h[0],z=h[1];
                r.Add(SolidPrimitiveFactory.Element(Hex(f,p.FlangeBackMm-head,y,z,1.5*d,head,'x'),1));
                AddCylinder(r,f,p.FlangeBackMm-head,y,z,p.CoverFrontMm+3+nut,y,z,d/2,1);
                AddCylinder(r,f,p.CoverFrontMm,y,z,p.CoverFrontMm+3,y,z,.925*d,1);
                r.Add(SolidPrimitiveFactory.Element(Hex(f,p.CoverFrontMm+3,y,z,1.5*d,nut,'x'),1));
            }
        }
        private static void AddHandles(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            foreach(double y in new[]{-175.0,175.0})
            {
                double x=p.CoverFrontMm;
                var a=f.Point(x,y,75); var b=f.Point(x+60,y,75);
                var c=f.Point(x+100,y,35); var d=f.Point(x+100,y,-35);
                var e=f.Point(x+60,y,-75);var g=f.Point(x,y,-75);
                var segments=new List<SolidPathSegment>{SolidPathSegment.Line(a,b),
                    SolidPathSegment.Arc(b,f.Point(x+60+40/Math.Sqrt(2),y,35+40/Math.Sqrt(2)),c),
                    SolidPathSegment.Line(c,d),
                    SolidPathSegment.Arc(d,f.Point(x+60+40/Math.Sqrt(2),y,-35-40/Math.Sqrt(2)),e),
                    SolidPathSegment.Line(e,g)};
                r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.RoundPath(a,
                    new DVector3d(f.Ux,f.Uy,0),10*f.Scale,segments),4));
            }
        }
        private static List<DPoint3d> Slot(TankManholeFrame f,double x,double y,double z,double length,double width,bool longX)
        {
            var pts=new List<DPoint3d>(); double rad=width/2, straight=length/2-rad;
            for(int i=0;i<=12;i++)
            { double a=-Math.PI/2+i*Math.PI/12; double q=straight+rad*Math.Cos(a),v=rad*Math.Sin(a);
              pts.Add(longX?f.Point(x+q,y+v,z):f.Point(x+v,y+q,z)); }
            for(int i=0;i<=12;i++)
            { double a=Math.PI/2+i*Math.PI/12; double q=-straight+rad*Math.Cos(a),v=rad*Math.Sin(a);
              pts.Add(longX?f.Point(x+q,y+v,z):f.Point(x+v,y+q,z)); }
            return pts;
        }
        private static void AddHinge(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            double y=p.PostYmm,x=p.DavitXmm;
            double lugHalf=TankManholeCalculator.HingeLugThicknessMm/2.0;
            foreach(double z in new[]{-TankManholeCalculator.HingeLugZmm,TankManholeCalculator.HingeLugZmm})
            {
                AddPlate(r,f,p.FlangeBackMm-20,p.FlangeFrontMm,p.FlangeRadiusMm-45,y+25,z-lugHalf,
                    TankManholeCalculator.HingeLugThicknessMm,2);
                var plate=Plate(f,p.FlangeFrontMm,x+25,y-25,y+25,z-lugHalf,
                    TankManholeCalculator.HingeLugThicknessMm);
                SolidPrimitiveFactory.Subtract(ref plate,new[]{SolidPrimitiveFactory.Cylinder(
                    f.Point(x,y,z-10),f.Point(x,y,z+10),
                    TankManholeCalculator.HingePinHoleDiameterMm/2*f.Scale)},"铰链吊耳孔");
                r.Add(SolidPrimitiveFactory.Element(plate,2));
            }
            var cover=Plate(f,p.CoverFrontMm-30,x+25,p.FlangeRadiusMm-25,y+25,-lugHalf,
                TankManholeCalculator.HingeLugThicknessMm);
            SolidPrimitiveFactory.Subtract(ref cover,new[]{SolidPrimitiveFactory.PolygonPrism(Slot(f,x,y,-10,40,22,true),
                new DVector3d(0,0,(TankManholeCalculator.HingeLugThicknessMm+4)*f.Scale))},"铰链长圆孔");
            r.Add(SolidPrimitiveFactory.Element(cover,2));
            // 销轴 + **上下对称**两只开口销：两端开口销孔与插销一一对应地成对生成。
            double half=TankManholeCalculator.HingePinHalfLength();
            double cotterBore=TankManholeCalculator.HingePinDiameterMm/2.0+2.0;   // 孔刀具径向余量
            var stations=TankManholeCalculator.HingeCotterStations();
            var pin=SolidPrimitiveFactory.Cylinder(f.Point(x,y,-half),f.Point(x,y,half),
                TankManholeCalculator.HingePinDiameterMm/2*f.Scale);
            var pinHoles=new List<SolidKernelEntity>();
            foreach(double z in stations)
                pinHoles.Add(SolidPrimitiveFactory.Cylinder(f.Point(x,y-cotterBore,z),f.Point(x,y+cotterBore,z),
                    TankManholeCalculator.HingeCotterHoleDiameterMm/2*f.Scale));
            SolidPrimitiveFactory.Subtract(ref pin,pinHoles,"开口销孔");
            r.Add(SolidPrimitiveFactory.Element(pin,5));
            // 开口销本体：沿局部 y 的细圆柱，位置、尺寸、朝向与下端那根完全相同（镜像到上端）。
            foreach(double z in stations)
                AddCylinder(r,f,x,y-TankManholeCalculator.HingeCotterHalfLengthMm,z,
                    x,y+TankManholeCalculator.HingeCotterHalfLengthMm,z,
                    TankManholeCalculator.HingeCotterDiameterMm/2,5);
        }
        private static void AddDavit(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            double d=p.Size.DavitDiameterMm, x=p.DavitPivotXmm,y=p.PostYmm;
            AddDavitSupport(r,f,p);
            var post=SolidPrimitiveFactory.Cylinder(f.Point(x,y,-105),f.Point(x,y,p.PostTopZmm),d/2*f.Scale);
            SolidPrimitiveFactory.Subtract(ref post,new[]{SolidPrimitiveFactory.Cylinder(f.Point(x,y-2,-85),f.Point(x,y+2,-85),2.75*f.Scale)},"吊杆开口销孔");
            r.Add(SolidPrimitiveFactory.Element(post,2));
            AddCylinder(r,f,x,y-14,-85,x,y+14,-85,2.5,5);
            double dx=x-p.DavitXmm,reach=Math.Sqrt(dx*dx+y*y),vx=dx/reach,vy=y/reach;
            var h=f.Offset(p.DavitXmm,0,p.ArmZmm);
            h.Ux=vy*f.Ux-vx*f.Vx;h.Uy=vy*f.Uy-vx*f.Vy;
            h.Vx=vx*f.Ux+vy*f.Vx;h.Vy=vx*f.Uy+vy*f.Vy;
            double bendY=reach-220;
            var a=h.Point(0,reach,-220);var b=h.Point(0,bendY,0);
            r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.RoundPath(a,new DVector3d(0,0,1),d/2*f.Scale,
                new[]{SolidPathSegment.Arc(a,h.Point(0,bendY+220/Math.Sqrt(2),-220+220/Math.Sqrt(2)),b)}),2));
            AddCylinder(r,h,0,bendY,0,0,60+d*1.5,0,d/2,2);
            var head=Plate(h,-50,50,-60,60,-p.FlatThicknessMm/2,p.FlatThicknessMm);
            SolidPrimitiveFactory.Subtract(ref head,new[]{SolidPrimitiveFactory.PolygonPrism(Slot(h,0,0,-p.FlatThicknessMm/2-2,40,22,false),
                new DVector3d(0,0,(p.FlatThicknessMm+4)*f.Scale))},"吊杆扁头长圆孔");
            r.Add(SolidPrimitiveFactory.Element(head,4));
            // 圆管 → 扁头矩形过渡：与原脚本同序，先试直纹放样，失败才退回 24 段台阶近似。
            if(!AddRuledLoft(r,h,50,p.FlatThicknessMm/2,d/2,p.LoftLengthMm))
                AddSteppedLoft(r,h,50,p.FlatThicknessMm/2,d/2,p.LoftLengthMm);
            AddCoverConnection(r,f,p);
        }
        private static CurveVector SectionCurve(TankManholeFrame f,double y,double halfWidth,
            double halfThickness,double radius,double t)
        {
            var points=MorphSection(f,y,halfWidth,halfThickness,radius,t);
            var curve=CurveVector.Create(CurveVector.BoundaryType.Outer);
            for(int i=0;i<points.Count;i++)
                curve.Add(CurvePrimitive.CreateLine(new DSegment3d(points[i],points[(i+1)%points.Count])));
            return curve;
        }
        /// <summary>两个断面之间的直纹放样：等价于原脚本的 DgnRuledSweep 一等公民做法
        /// （segment=true = 断面之间线性连接、不做平滑），任何失败都返回 false。</summary>
        private static bool AddRuledLoft(List<Element> r,TankManholeFrame h,double halfWidth,
            double halfThickness,double radius,double loftLength)
        {
            try
            {
                var sections=new[]{SectionCurve(h,60.0,halfWidth,halfThickness,radius,0.0),
                    SectionCurve(h,60.0+loftLength,halfWidth,halfThickness,radius,1.0)};
                var guides=new CurveVector[0];
                SolidKernelEntity body;
                var status=Create.BodyFromLoft(out body,sections,sections.Length,guides,0,
                    Session.Instance.GetActiveDgnModelRef(),false,true);
                if(status!=BentleyStatus.Success || body==null) return false;
                r.Add(SolidPrimitiveFactory.Element(body,4));
                return true;
            }
            catch(Exception)
            { return false; }
        }
        /// <summary>台阶近似：24 片同角度采样的薄棱柱（与原脚本的 LOFT_SLICES 回退一致）。</summary>
        private static void AddSteppedLoft(List<Element> r,TankManholeFrame h,double halfWidth,
            double halfThickness,double radius,double loftLength)
        {
            double step=loftLength/24.0;
            for(int i=0;i<24;i++)
            {
                double t=(double)i/24;
                double station=60+i*step;
                var section=MorphSection(h,station,halfWidth,halfThickness,radius,t);
                // 反序：与 Python 版一致，轮廓法向朝圆管一侧，棱柱沿 +V 拉伸。
                section.Reverse();
                r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(section,
                    new DVector3d(h.Vx*step*h.Scale,h.Vy*step*h.Scale,0)),4));
            }
        }
        private static List<DPoint3d> MorphSection(TankManholeFrame f,double y,
            double halfWidth,double halfThickness,double radius,double t)
        {
            var pts=new List<DPoint3d>();
            var corners=new[]{new[]{halfWidth,-halfThickness},new[]{halfWidth,halfThickness},
                new[]{-halfWidth,halfThickness},new[]{-halfWidth,-halfThickness}};
            double startAngle=Math.Atan2(-halfThickness,halfWidth);
            for(int edge=0;edge<4;edge++) for(int step=0;step<6;step++)
            {
                double ratio=(double)step/6;
                double rx=corners[edge][0]*(1-ratio)+corners[(edge+1)%4][0]*ratio;
                double rz=corners[edge][1]*(1-ratio)+corners[(edge+1)%4][1]*ratio;
                int index=edge*6+step;
                double angle=startAngle+2*Math.PI*index/24;
                pts.Add(f.Point(rx*(1-t)+radius*Math.Cos(angle)*t,y,
                    rz*(1-t)+radius*Math.Sin(angle)*t));
            }
            return pts;
        }
        private static void AddDavitSupport(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            double d=p.Size.DavitDiameterMm,width=d+30;
            double front=TankManholeCalculator.DavitSupportAnchorY(p.FlangeRadiusMm);
            double x=p.DavitPivotXmm-width/2;
            var segments=TankManholeCalculator.DavitSupportProfile(d,p.Size.FlangeThicknessMm,
                p.PostYmm,p.FlangeRadiusMm);
            // 剖面 = 8 段直线 + 4 段真圆弧：圆角是真圆柱面，不会出现折线那种成排的分面棱。
            var profile=CurveVector.Create(CurveVector.BoundaryType.Outer);
            foreach(var segment in segments)
            {
                if(!segment.IsArc)
                {
                    profile.Add(CurvePrimitive.CreateLine(new DSegment3d(
                        f.Point(x,segment.Y1,segment.Z1),f.Point(x,segment.Y2,segment.Z2))));
                    continue;
                }
                DEllipse3d arc;
                if(!DEllipse3d.TryCircularArcFromStartMiddleEnd(f.Point(x,segment.Y1,segment.Z1),
                    f.Point(x,segment.MidY,segment.MidZ),f.Point(x,segment.Y2,segment.Z2),out arc))
                    throw new InvalidOperationException("吊杆支撑件 R20/R10 圆弧构造失败。");
                profile.Add(CurvePrimitive.CreateArc(arc));
            }
            var body=SolidPrimitiveFactory.Prism(profile,
                f.Point(x,segments[0].Y1,segments[0].Z1),
                new DVector3d(f.Ux*width*f.Scale,f.Uy*width*f.Scale,0));
            // 立柱孔：一根刀具同时贯穿上下两臂；-82/+82 = 净高/2 + 板厚 + 2 的余量（与原脚本一致）。
            double zBore=TankManholeCalculator.DavitSupportClearHeightMm/2.0+
                TankManholeCalculator.DavitSupportThicknessMm+2;
            var cutters=new List<SolidKernelEntity>{SolidPrimitiveFactory.Cylinder(
                f.Point(p.DavitPivotXmm,p.PostYmm,-zBore),f.Point(p.DavitPivotXmm,p.PostYmm,zBore),
                (d+3)/2*f.Scale)};
            // 30° 端部倒角：开口端保留法兰厚度，沿板长收紧到全宽。
            double nose=p.Size.FlangeThicknessMm/2;
            if(nose<width/2)
            {
                double chamfer=TankManholeCalculator.DavitSupportChamferDistance(d,p.Size.FlangeThicknessMm);
                foreach(double sign in new[]{-1.0,1.0})
                {
                    var triangle=new[]{f.Point(p.DavitPivotXmm+sign*nose,front-2,-zBore),
                        f.Point(p.DavitPivotXmm+sign*(width/2+2),front+chamfer+2,-zBore),
                        f.Point(p.DavitPivotXmm+sign*(width/2+2),front-2,-zBore)};
                    cutters.Add(SolidPrimitiveFactory.PolygonPrism(triangle,
                        new DVector3d(0,0,2*zBore*f.Scale)));
                }
            }
            SolidPrimitiveFactory.Subtract(ref body,cutters,"吊杆回转支撑孔与端部倒角");
            r.Add(SolidPrimitiveFactory.Element(body,2));
        }
        private static void AddCoverConnection(List<Element> r,TankManholeFrame f,TankManholePlan p)
        {
            double x=p.DavitXmm,z=p.StudZmm;
            // 耳板沿轴向对称于螺柱轴线（板长不变），螺柱孔因此落在板宽正中。
            var span=TankManholeCalculator.CoverLugSpan(p.CoverBackMm,p.CoverFrontMm,p.DavitXmm);
            double chamfer=35.0;   // 前下角 35mm×45° 倒角：前伸段在盖板顶边以下悬空，收掉
            foreach(double sign in new[]{-1.0,1.0})
            {
                double y=sign>0?33:-17;
                var pts=new[]{f.Point(span[0],y,p.FlangeRadiusMm-50),
                    f.Point(span[1]-chamfer,y,p.FlangeRadiusMm-50),
                    f.Point(span[1],y,p.FlangeRadiusMm-50+chamfer),
                    f.Point(span[1],y,p.FlangeRadiusMm+60),f.Point(span[0],y,p.FlangeRadiusMm+60)};
                // 螺柱孔：半径 = (STUD_DIA + STUD_HOLE_CLEARANCE)/2 = (16+1)/2 = 8.5，
                // 刀具沿 -y 覆盖整块耳板（板厚 16 + 两端各 12 余量），与原脚本一致。
                var lug=SolidPrimitiveFactory.PolygonPrism(pts,new DVector3d(-f.Vx*16*f.Scale,-f.Vy*16*f.Scale,0));
                SolidPrimitiveFactory.Subtract(ref lug,new[]{SolidPrimitiveFactory.Cylinder(
                    f.Point(x,y-16-12,z),f.Point(x,y+12,z),8.5*f.Scale)},"盖板吊耳孔");
                r.Add(SolidPrimitiveFactory.Element(lug,2));
            }
            AddCylinder(r,f,x,-59,z,x,59,z,8,5);
            // 螺母贴着耳板外表面（±33）：六角沿 +V 拉伸 nut 高度，- 侧从 -45.8 起拉到 -33。
            double lugOuter=33.0,nutHeight=12.8;
            foreach(double y in new[]{-lugOuter-nutHeight,lugOuter})
                r.Add(SolidPrimitiveFactory.Element(Hex(f,x,y,z,24,nutHeight,'y'),5));
            // M20 eye bolt: vertical shank, ring and two upper nuts.
            double neckHeight=Math.Sqrt(55*55-30*30);
            double neckAngle=Math.Atan2(-neckHeight*30/55,30-30*25/55);
            double startX=x-30*25/55,startZ=z+neckHeight*25/55;
            var neckStart=f.Point(startX,0,startZ);
            var neckMiddle=f.Point(x-30+30*Math.Cos(neckAngle/2),0,z+neckHeight+30*Math.Sin(neckAngle/2));
            var neckEnd=f.Point(x,0,z+neckHeight);
            r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.RoundPath(neckStart,
                new DVector3d(-Math.Sin(neckAngle)*f.Ux,-Math.Sin(neckAngle)*f.Uy,Math.Cos(neckAngle)),
                10*f.Scale,new[]{SolidPathSegment.Arc(neckStart,neckMiddle,neckEnd)}),3));
            AddCylinder(r,f,x,0,z+neckHeight,x,0,z+200,10,3);
            var seg=new List<SolidPathSegment>();
            // 圆环中心线半径 = 吊环孔半径 15 + 圆钢半径 10 = 25（与原脚本 eye_r 一致）。
            double ringRadius=30.0/2.0+10.0;
            for(int i=0;i<24;i++)
            {
                double a=i*2*Math.PI/24,b=(i+1)*2*Math.PI/24;
                seg.Add(SolidPathSegment.Arc(f.Point(x+ringRadius*Math.Cos(a),0,z+ringRadius*Math.Sin(a)),
                    f.Point(x+ringRadius*Math.Cos((a+b)/2),0,z+ringRadius*Math.Sin((a+b)/2)),
                    f.Point(x+ringRadius*Math.Cos(b),0,z+ringRadius*Math.Sin(b))));
            }
            r.Add(SolidPrimitiveFactory.Element(SolidPrimitiveFactory.RoundPath(seg[0].Start,new DVector3d(0,0,1),10*f.Scale,seg),3));
            double nutZ=p.ArmZmm+p.FlatThicknessMm/2+3;
            for(int i=0;i<2;i++)
            { AddCylinder(r,f,x,0,nutZ-3,x,0,nutZ,18.5,3);
              r.Add(SolidPrimitiveFactory.Element(Hex(f,x,0,nutZ,30,16,'z'),3)); nutZ+=19; }
        }
    }
}
