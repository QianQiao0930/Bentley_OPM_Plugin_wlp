using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    internal static class TankManholeCalculator
    {
        // 吊杆回转支撑件常数：与 罐壁人孔/tank_wall_manhole.py 的 DAVIT_SUPPORT_* 一一对应。
        internal const double DavitSupportThicknessMm=16;
        internal const double DavitSupportClearHeightMm=128;
        internal const double DavitSupportOuterRadiusMm=20;
        internal const double DavitSupportInnerRadiusMm=10;
        internal const double DavitSupportChamferDegrees=30;
        internal const int DavitSupportArcSteps=8;

        internal static TankManholePlan Calculate(TankManholeParameters p)
        {
            if(p==null) throw new InvalidOperationException("缺少人孔参数。");
            if(double.IsNaN(p.HeadingDegrees) || double.IsInfinity(p.HeadingDegrees))
                throw new InvalidOperationException("朝向必须是有限数字。");
            if(double.IsNaN(p.NeckLengthMm) || double.IsInfinity(p.NeckLengthMm) ||
                p.NeckLengthMm<=0 || p.NeckLengthMm>20000)
                throw new InvalidOperationException("筒节长度必须在 0～20000 mm 内。");
            if(p.CoverMode!=TankCoverMode.Davit && p.CoverMode!=TankCoverMode.Hinge)
                throw new InvalidOperationException("未知盖板连接形式。");
            var s=TankManholeCatalog.For(p.NominalDn,p.PressureLbs);
            var result=new TankManholePlan { Parameters=p,Size=s,
                HeadingRadians=(p.HeadingDegrees+(p.Mirrored?180:0))*Math.PI/180,
                FlangeBackMm=p.NeckLengthMm,FlangeFrontMm=p.NeckLengthMm+s.FlangeThicknessMm,
                FlangeRadiusMm=s.FlangeOutsideMm/2,BoltCircleRadiusMm=s.BoltCircleMm/2,
                BoltHoleRadiusMm=(s.BoltDiameterMm+2)/2 };
            result.CoverBackMm=result.FlangeFrontMm+2;
            result.CoverFrontMm=result.CoverBackMm+s.CoverThicknessMm;
            result.DavitPivotXmm=(result.FlangeBackMm+result.FlangeFrontMm)/2;
            result.DavitXmm=result.CoverFrontMm+10;
            result.PostYmm=result.FlangeRadiusMm+55;
            result.ArmZmm=result.FlangeRadiusMm+140;
            result.PostTopZmm=result.ArmZmm-220;
            result.StudZmm=result.FlangeRadiusMm+40;
            result.FlatThicknessMm=s.DavitDiameterMm/2;
            result.LoftLengthMm=s.DavitDiameterMm*1.5;
            if(s.BoreMm>=s.NeckOutsideMm || s.BoltCircleMm>=s.FlangeOutsideMm)
                throw new InvalidOperationException("人孔参考尺寸不满足几何约束。");
            return result;
        }
        /// <summary>支撑件开口端（焊在法兰外缘的那一面）到人孔轴线的径向距离。</summary>
        internal static double DavitSupportAnchorY(double flangeRadiusMm)
        {
            double zOuter=DavitSupportClearHeightMm/2.0+DavitSupportThicknessMm;
            return Math.Sqrt(flangeRadiusMm*flangeRadiusMm-zOuter*zOuter)-2;
        }
        /// <summary>支撑件背板**外**表面到人孔轴线的径向距离。
        /// 立柱轴线到该面 = D/2 + 20 + 16（16 为扫掠轮廓厚度，原脚本的扫掠把它加在路径终点之外）。</summary>
        internal static double DavitSupportOuterFaceY(double postYmm,double davitDiameterMm)
        {
            return postYmm+davitDiameterMm/2.0+20.0+DavitSupportThicknessMm;
        }
        /// <summary>开口端 30° 倒角沿板长的收窄长度 = (D+30-FT)/2 × tan60°（与法兰厚度对齐用）。</summary>
        internal static double DavitSupportChamferDistance(double davitDiameterMm,double flangeThicknessMm)
        {
            return (davitDiameterMm+30.0-flangeThicknessMm)/2.0*Math.Sqrt(3.0);
        }
        /// <summary>盖板吊耳的轴向范围：板长不变（盖板厚 + 前伸 25），但**对称于螺柱轴线**
        /// DavitXmm，让螺柱孔落在板宽正中。返回 {后端, 前端}。</summary>
        internal static double[] CoverLugSpan(double coverBackMm,double coverFrontMm,double davitXmm)
        {
            double half=(coverFrontMm+25.0-coverBackMm)/2.0;
            return new[]{davitXmm-half,davitXmm+half};
        }
        /// <summary>支撑件径向剖面的一段：直线（默认）或真圆弧（圆角）。
        /// 单位 mm，(径向, 竖直)；圆弧带圆心的三个参数，供 Bentley 侧直接造圆弧原语用。</summary>
        internal sealed class DavitSupportSegment
        {
            internal bool IsArc;
            internal double Y1,Z1,Y2,Z2;
            internal double CenterY,CenterZ,Radius,StartAngle,SweepAngle;
            internal double PointY(double t){ double a=StartAngle+SweepAngle*t; return CenterY+Radius*Math.Cos(a); }
            internal double PointZ(double t){ double a=StartAngle+SweepAngle*t; return CenterZ+Radius*Math.Sin(a); }
            internal double MidY{ get { return PointY(0.5); } }
            internal double MidZ{ get { return PointZ(0.5); } }
        }
        /// <summary>支撑件径向剖面路径：8 段直线 + 4 段**真圆弧**（与原脚本的 R20/R10 完全圆角一致，
        /// 不要改成折线——折线的通长棱会产生明显的分面着色条纹）。</summary>
        internal static List<DavitSupportSegment> DavitSupportProfile(double davitDiameterMm,
            double flangeThicknessMm,double postYmm,double flangeRadiusMm)
        {
            double width=davitDiameterMm+30.0;
            double outerHalf=DavitSupportClearHeightMm/2.0+DavitSupportThicknessMm;
            double innerHalf=DavitSupportClearHeightMm/2.0;
            if(!(flangeThicknessMm>0.0 && flangeThicknessMm<width))
                throw new InvalidOperationException("吊杆支撑件要求 0 < 法兰边缘厚度 < D+30。");
            double front=DavitSupportAnchorY(flangeRadiusMm);
            double back=DavitSupportOuterFaceY(postYmm,davitDiameterMm);
            double innerSpan=back-DavitSupportThicknessMm-front;
            double chamferDistance=DavitSupportChamferDistance(davitDiameterMm,flangeThicknessMm);
            if(chamferDistance>=innerSpan-DavitSupportInnerRadiusMm)
                throw new InvalidOperationException("吊杆支撑件端部倒角过长，已进入背部圆角区域。");
            double outer=DavitSupportOuterRadiusMm,inner=DavitSupportInnerRadiusMm;
            double webInner=back-DavitSupportThicknessMm;
            var segments=new List<DavitSupportSegment>();
            AddLine(segments,front,-outerHalf,back-outer,-outerHalf);                       // 下臂底面
            AddArc(segments,back-outer,-outerHalf+outer,outer,-Math.PI/2,Math.PI/2);        // 背部下外圆角
            AddLine(segments,back,-outerHalf+outer,back,outerHalf-outer);                   // 腹板外表面
            AddArc(segments,back-outer,outerHalf-outer,outer,0.0,Math.PI/2);                // 背部上外圆角
            AddLine(segments,back-outer,outerHalf,front,outerHalf);                         // 上臂顶面
            AddLine(segments,front,outerHalf,front,innerHalf);                              // 开口端上臂端面
            AddLine(segments,front,innerHalf,webInner-inner,innerHalf);                     // 上臂内表面
            AddArc(segments,webInner-inner,innerHalf-inner,inner,Math.PI/2,-Math.PI/2);     // 背部上内圆角
            AddLine(segments,webInner,innerHalf-inner,webInner,-innerHalf+inner);           // 腹板内表面
            AddArc(segments,webInner-inner,-innerHalf+inner,inner,0.0,-Math.PI/2);          // 背部下内圆角
            AddLine(segments,webInner-inner,-innerHalf,front,-innerHalf);                   // 下臂内表面
            AddLine(segments,front,-innerHalf,front,-outerHalf);                            // 开口端下臂端面
            return segments;
        }
        /// <summary>剖面路径 → 点列（圆弧按 DavitSupportArcSteps 段展开，仅用于纯计算校验/对照）。</summary>
        internal static List<double[]> DavitSupportOutline(double davitDiameterMm,
            double flangeThicknessMm,double postYmm,double flangeRadiusMm)
        {
            var segments=DavitSupportProfile(davitDiameterMm,flangeThicknessMm,postYmm,flangeRadiusMm);
            var points=new List<double[]>();
            for(int index=0;index<segments.Count;index++)
            {
                var segment=segments[index];
                if(index==0) points.Add(new[]{segment.Y1,segment.Z1});
                if(segment.IsArc)
                {
                    for(int i=1;i<=DavitSupportArcSteps;i++)
                        points.Add(new[]{segment.PointY((double)i/DavitSupportArcSteps),
                            segment.PointZ((double)i/DavitSupportArcSteps)});
                }
                else if(index<segments.Count-1)
                    points.Add(new[]{segment.Y2,segment.Z2});
            }
            return points;
        }
        private static void AddLine(List<DavitSupportSegment> segments,
            double y1,double z1,double y2,double z2)
        {
            segments.Add(new DavitSupportSegment { Y1=y1,Z1=z1,Y2=y2,Z2=z2 });
        }
        private static void AddArc(List<DavitSupportSegment> segments,double centerY,double centerZ,
            double radius,double startRadians,double sweepRadians)
        {
            var segment=new DavitSupportSegment { IsArc=true,CenterY=centerY,CenterZ=centerZ,
                Radius=radius,StartAngle=startRadians,SweepAngle=sweepRadians };
            segment.Y1=segment.PointY(0.0); segment.Z1=segment.PointZ(0.0);
            segment.Y2=segment.PointY(1.0); segment.Z2=segment.PointZ(1.0);
            segments.Add(segment);
        }
        internal static double[] BoltPosition(int index,int count,double radiusMm)
        {
            if(count<=0 || index<0 || index>=count || radiusMm<=0)
                throw new InvalidOperationException("螺栓圆参数无效。");
            double angle=2*Math.PI*(index+0.5)/count;
            return new[]{radiusMm*Math.Cos(angle),radiusMm*Math.Sin(angle)};
        }
    }
}
