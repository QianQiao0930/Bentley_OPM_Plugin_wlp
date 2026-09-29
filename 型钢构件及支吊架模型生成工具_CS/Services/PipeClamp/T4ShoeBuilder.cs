using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// T4 高温隔热限位管托建模：外圆柱 − 内圆柱 − 45° 贯穿体 = 两片承重板；耳板开孔后
    /// 与管夹布尔并；底座 = 底板 + 中央纵向腹板，DN80 及以上另加横向弧顶支撑；再配紧固件。
    /// 与 Python <c>T4-[高温隔热限位管托].py</c> 的 <c>_build_components</c> 逐项对齐。
    /// 局部坐标：原点 = 管道中线，X = 管轴，Z 竖直向上；尺寸为毫米。
    /// </summary>
    internal static class T4ShoeBuilder
    {
        private const double Margin=T4ShoeCatalog.ThroughMarginMm;

        internal static List<Element> Build(T4ShoeLayout layout,T4ShoeBooleanLayout bl,
            DPoint3d center,DVector3d axis,bool buildPipe,bool buildInsulation)
        {
            if(layout==null) throw new ArgumentNullException("layout");
            if(bl==null) throw new ArgumentNullException("bl");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)
                throw new InvalidOperationException("T4 管托需要在三维 DGN 模型中放置。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var frame=new PipeClampFrame(center,scale,axis.X,axis.Y,axis.Z);
            var result=new List<Element>();
            double length=bl.ClampLengthMm;

            // 可选管道本体 / 保温层（管道钢灰、保温层岩棉黄，便于在模型里区分）。
            if(buildPipe)
            {
                double wall=Math.Max(3.0,layout.OutsideMm*0.04);
                double pipeLength=length+40.0;
                var pipe=Cone(frame,-length/2.0,0.0,0.0,-length/2.0+pipeLength,0.0,0.0,
                    layout.PipeRadiusMm);
                var pipeBore=Cone(frame,-length/2.0-Margin,0.0,0.0,
                    -length/2.0+pipeLength+Margin,0.0,0.0,layout.PipeRadiusMm-wall);
                SolidPrimitiveFactory.Subtract(ref pipe,new[]{pipeBore},"管道内孔");
                result.Add(SolidPrimitiveFactory.Element(pipe,T4ShoeCatalog.PipeColor));
            }
            if(buildInsulation)
            {
                var insulation=SolidPrimitiveFactory.Cylinder(
                    frame.Point(-length/2.0,0.0,0.0),
                    frame.Point(length/2.0,0.0,0.0),
                    layout.InsulationRadiusMm*scale);
                var bore=SolidPrimitiveFactory.Cylinder(
                    frame.Point(-length/2.0-Margin,0.0,0.0),
                    frame.Point(length/2.0+Margin,0.0,0.0),
                    layout.PipeRadiusMm*scale);
                SolidPrimitiveFactory.Subtract(ref insulation,new[]{bore},"保温层减去管道");
                result.Add(SolidPrimitiveFactory.Element(insulation,T4ShoeCatalog.InsulationColor));
            }

            var ring=BuildRing(frame,bl,layout);
            BuildSupport(frame,bl,layout,ref ring);
            result.Add(SolidPrimitiveFactory.Element(ring,T4ShoeCatalog.ClampColor));

            for(int i=0;i<bl.EarCenterXmm.Length;i++)
            {
                // 每个轴向位置有两处分口，各穿一套紧固件（孔心 a 取正、负各一）。
                AddFasteners(result,frame,bl,layout,bl.EarCenterXmm[i],bl.EarHoleA[2]);
                AddFasteners(result,frame,bl,layout,bl.EarCenterXmm[i],bl.EarHoleA[0]);
            }
            return result;
        }

        /// <summary>外圆柱 − 内圆柱 − 45° 矩形贯穿体，再逐块布尔并入开孔耳板。</summary>
        private static SolidKernelEntity BuildRing(PipeClampFrame frame,
            T4ShoeBooleanLayout bl,T4ShoeLayout layout)
        {
            double halfLength=bl.ClampLengthMm/2.0;
            var ring=Cone(frame,-halfLength,0.0,0.0,halfLength,0.0,0.0,bl.OuterRadiusMm);
            var bore=Cone(frame,-halfLength-Margin,0.0,0.0,halfLength+Margin,0.0,0.0,bl.InnerRadiusMm);
            SolidPrimitiveFactory.Subtract(ref ring,new[]{bore},"外圆柱减去管道及保温层圆柱");
            var cutter=RectangleCutter(frame,bl.CutAngleDeg,bl.ClampLengthMm,
                bl.OuterRadiusMm,bl.GapJMm);
            SolidPrimitiveFactory.Subtract(ref ring,new[]{cutter},"圆环减去 45 度矩形贯穿体");

            double c,s;
            T4ShoeCalculator.CutFrame(bl.CutAngleDeg,out c,out s);
            for(int group=0;group<bl.EarCenterXmm.Length;group++)
            {
                double centerX=bl.EarCenterXmm[group];
                for(int index=0;index<bl.EarBounds.Length;index++)
                {
                    var bounds=bl.EarBounds[index];
                    var ear=EarBody(frame,bl.CutAngleDeg,centerX,bounds[0],bounds[1],
                        bounds[2],bounds[3],bl.EarWidthMm);
                    double a=bl.EarHoleA[index];
                    double startB=bounds[2]-Margin;
                    double endB=bounds[3]+Margin;
                    var hole=Cone(frame,centerX,a*c-startB*s,a*s+startB*c,
                        centerX,a*c-endB*s,a*s+endB*c,bl.HoleDiameterMm/2.0);
                    SolidPrimitiveFactory.Subtract(ref ear,new[]{hole},
                        "耳板"+(index+1).ToString(System.Globalization.CultureInfo.InvariantCulture)+
                        "开螺栓通孔");
                    SolidPrimitiveFactory.Union(ref ring,new[]{ear},
                        "耳板"+(index+1).ToString(System.Globalization.CultureInfo.InvariantCulture)+
                        "与管夹布尔并");
                }
            }
            return ring;
        }

        /// <summary>底板 + 中央纵向腹板；DN80 及以上另加横向弧顶支撑。</summary>
        private static void BuildSupport(PipeClampFrame frame,T4ShoeBooleanLayout bl,
            T4ShoeLayout layout,ref SolidKernelEntity ring)
        {
            double length=bl.ClampLengthMm;
            double halfLength=length/2.0;
            double halfWidth=layout.BaseWidthMm/2.0;
            var based=SolidPrimitiveFactory.PolygonPrism(new[]{
                frame.Point(-halfLength,-halfWidth,bl.BaseBottomZMm),
                frame.Point(halfLength,-halfWidth,bl.BaseBottomZMm),
                frame.Point(halfLength,halfWidth,bl.BaseBottomZMm),
                frame.Point(-halfLength,halfWidth,bl.BaseBottomZMm)},
                frame.Direction(0.0,0.0,bl.BaseTopZMm-bl.BaseBottomZMm));
            var basePlate=based;

            double halfThickness=layout.T2Mm/2.0;
            var plates=new List<double[]>();
            foreach(double x in bl.SupportCenterXmm)
                plates.Add(new[]{x-halfThickness,x+halfThickness,-bl.SupportHalfSpanMm,
                    bl.SupportHalfSpanMm});
            double webStart=bl.SupportCenterXmm.Length>0?bl.SupportCenterXmm[0]:
                -halfLength+layout.SupportEndOffsetMm;
            double webEnd=bl.SupportCenterXmm.Length>0?
                bl.SupportCenterXmm[bl.SupportCenterXmm.Length-1]:
                halfLength-layout.SupportEndOffsetMm;
            plates.Add(new[]{webStart,webEnd,-halfThickness,halfThickness});

            double c,s;
            T4ShoeCalculator.CutFrame(bl.CutAngleDeg,out c,out s);
            for(int index=0;index<plates.Count;index++)
            {
                var plate=plates[index];
                var body=Box(frame,plate[0],plate[2],bl.BaseTopZMm-T4ShoeCatalog.SupportOverlapMm,
                    plate[1],plate[3],bl.SupportTopZMm);
                var cutter=Cone(frame,plate[0]-Margin,0.0,0.0,plate[1]+Margin,0.0,0.0,
                    bl.TrimRadiusMm);
                SolidPrimitiveFactory.Subtract(ref body,new[]{cutter},
                    "支撑"+(index+1).ToString(System.Globalization.CultureInfo.InvariantCulture)+
                    "剪切贴合圆弧");
                double maxB=Math.Max(-s*plate[2]+c*bl.SupportTopZMm,-s*plate[3]+c*bl.SupportTopZMm);
                if(maxB>-bl.GapJMm/2.0)
                {
                    var slit=RectangleCutter(frame,bl.CutAngleDeg,length,bl.OuterRadiusMm,bl.GapJMm);
                    SolidPrimitiveFactory.Subtract(ref body,new[]{slit},
                        "支撑"+(index+1).ToString(System.Globalization.CultureInfo.InvariantCulture)+
                        "避让管夹对开间隙");
                }
                SolidPrimitiveFactory.Union(ref basePlate,new[]{body},
                    "支撑"+(index+1).ToString(System.Globalization.CultureInfo.InvariantCulture)+
                    "连接底板");
            }
            SolidPrimitiveFactory.Union(ref ring,new[]{basePlate},"支腿与下半承重板连接");
        }

        /// <summary>一套紧固件：贯穿两耳板的光杆、六角头、六角螺母、两只圆环垫圈。</summary>
        private static void AddFasteners(List<Element> result,PipeClampFrame frame,
            T4ShoeBooleanLayout bl,T4ShoeLayout layout,double centerX,double a)
        {
            double c,s;
            T4ShoeCalculator.CutFrame(bl.CutAngleDeg,out c,out s);
            double d=layout.BoltDiameterMm;
            double far=bl.GapJMm/2.0+bl.EarSetbackMm+layout.EarThicknessMm;
            double seat=far+T4ShoeCatalog.WasherThicknessMm;
            double across=d*T4ShoeCatalog.HexAcrossFlatsRatio;
            double headHeight=d*T4ShoeCatalog.BoltHeadHeightRatio;
            double nutHeight=d*T4ShoeCatalog.NutHeightRatio;

            Func<double,double,double,SolidKernelEntity> cylinder=(b0,b1,radius)=>
                Cone(frame,centerX,a*c-b0*s,a*s+b0*c,centerX,a*c-b1*s,a*s+b1*c,radius);

            var shank=cylinder(-seat,seat+nutHeight+T4ShoeCatalog.BoltTipExtraMm,d/2.0);
            var head=HexBody(frame,bl.CutAngleDeg,centerX,a,-seat-headHeight,-seat,across);
            var nut=HexBody(frame,bl.CutAngleDeg,centerX,a,seat,seat+nutHeight,across);
            var nutBore=cylinder(seat-Margin,seat+nutHeight+Margin,bl.HoleDiameterMm/2.0);
            SolidPrimitiveFactory.Subtract(ref nut,new[]{nutBore},"螺母中心孔");

            result.Add(SolidPrimitiveFactory.Element(shank,T4ShoeCatalog.BoltColor));
            result.Add(SolidPrimitiveFactory.Element(head,T4ShoeCatalog.BoltColor));
            result.Add(SolidPrimitiveFactory.Element(nut,T4ShoeCatalog.BoltColor));
            foreach(var span in new[]{new[]{-seat,-far},new[]{far,seat}})
            {
                var washer=cylinder(span[0],span[1],d*T4ShoeCatalog.WasherOdRatio/2.0);
                var washerBore=cylinder(span[0]-Margin,span[1]+Margin,bl.HoleDiameterMm/2.0);
                SolidPrimitiveFactory.Subtract(ref washer,new[]{washerBore},"垫圈中心孔");
                result.Add(SolidPrimitiveFactory.Element(washer,T4ShoeCatalog.BoltColor));
            }
        }

        /// <summary>真圆柱：起点、终点为局部毫米坐标。</summary>
        private static SolidKernelEntity Cone(PipeClampFrame frame,
            double x0,double y0,double z0,double x1,double y1,double z1,double radius)
        {
            return SolidPrimitiveFactory.Cylinder(frame.Point(x0,y0,z0),
                frame.Point(x1,y1,z1),radius*frame.Scale);
        }

        /// <summary>长方体：截面在 z = z0 水平面，沿 +Z 拉伸到 z1。</summary>
        private static SolidKernelEntity Box(PipeClampFrame frame,
            double x0,double y0,double z0,double x1,double y1,double z1)
        {
            return SolidPrimitiveFactory.PolygonPrism(new[]{
                frame.Point(x0,y0,z0),frame.Point(x1,y0,z0),
                frame.Point(x1,y1,z0),frame.Point(x0,y1,z0)},
                frame.Direction(0.0,0.0,z1-z0));
        }

        /// <summary>耳板：截面在 x = centerX − width/2 平面，沿 +X 拉伸 width。</summary>
        private static SolidKernelEntity EarBody(PipeClampFrame frame,double splitAngle,
            double centerX,double a0,double a1,double b0,double b1,double width)
        {
            double c,s;
            T4ShoeCalculator.CutFrame(splitAngle,out c,out s);
            double x=centerX-width/2.0;
            var points=new[]{
                frame.Point(x,a0*c-b0*s,a0*s+b0*c),
                frame.Point(x,a1*c-b0*s,a1*s+b0*c),
                frame.Point(x,a1*c-b1*s,a1*s+b1*c),
                frame.Point(x,a0*c-b1*s,a0*s+b1*c)};
            return SolidPrimitiveFactory.PolygonPrism(points,frame.Direction(width,0.0,0.0));
        }

        /// <summary>45° 矩形贯穿切割体：截面在 x = −L/2 − 余量 平面，沿 +X 贯穿。</summary>
        private static SolidKernelEntity RectangleCutter(PipeClampFrame frame,double splitAngle,
            double length,double outerRadius,double gapJ)
        {
            double c,s;
            T4ShoeCalculator.CutFrame(splitAngle,out c,out s);
            double halfLength=outerRadius+T4ShoeCatalog.CutExtraLengthMm/2.0;
            double halfGap=gapJ/2.0;
            double x0=-length/2.0-Margin;
            var corners=new[]{
                new[]{-halfLength,-halfGap},new[]{halfLength,-halfGap},
                new[]{halfLength,halfGap},new[]{-halfLength,halfGap}};
            var points=new DPoint3d[corners.Length];
            for(int i=0;i<corners.Length;i++)
            {
                double a=corners[i][0],b=corners[i][1];
                points[i]=frame.Point(x0,a*c-b*s,a*s+b*c);
            }
            return SolidPrimitiveFactory.PolygonPrism(points,
                frame.Direction(length+2.0*Margin,0.0,0.0));
        }

        /// <summary>沿切口法向拉伸的六角棱柱（六角螺栓头 / 螺母）。</summary>
        private static SolidKernelEntity HexBody(PipeClampFrame frame,double splitAngle,
            double centerX,double a,double b0,double b1,double acrossFlats)
        {
            double c,s;
            T4ShoeCalculator.CutFrame(splitAngle,out c,out s);
            double radius=acrossFlats/(2.0*Math.Cos(Math.PI/6.0));
            var points=new DPoint3d[6];
            for(int index=0;index<6;index++)
            {
                double theta=Math.PI/6.0+index*Math.PI/3.0;
                double x=centerX+radius*Math.Cos(theta);
                double radial=a+radius*Math.Sin(theta);
                points[index]=frame.Point(x,radial*c-b0*s,radial*s+b0*c);
            }
            double distance=b1-b0;
            return SolidPrimitiveFactory.PolygonPrism(points,
                frame.Direction(0.0,-s*distance,c*distance));
        }
    }
}
