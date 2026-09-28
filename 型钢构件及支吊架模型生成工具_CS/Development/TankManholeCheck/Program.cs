using System;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Equal(double a,double b,string label)
        { if(Math.Abs(a-b)>0.00001) throw new Exception(label+": "+a+" != "+b); }
        private static void Reject(Action action,string label)
        { try { action(); } catch(InvalidOperationException) { return; } throw new Exception(label+" 应被拒绝。"); }
        private static void Main()
        {
            var expected=new double[,] {{35,45,50},{40,50,60},{45,55,65}};
            int[] dn={450,500,600},pressure={150,300,600},counts={16,20,20};
            for(int i=0;i<3;i++) for(int j=0;j<3;j++)
            {
                var p=TankManholeCalculator.Calculate(new TankManholeParameters {NominalDn=dn[i],PressureLbs=pressure[j]});
                Equal(p.Size.DavitDiameterMm,expected[i,j],"吊杆规格");
                Equal(p.Size.BoltCount,counts[i],"螺栓数量");
                Equal(p.CoverFrontMm,p.FlangeFrontMm+2+p.Size.CoverThicknessMm,"盖板站位");
                for(int k=0;k<p.Size.BoltCount;k++)
                { var pt=TankManholeCalculator.BoltPosition(k,p.Size.BoltCount,p.BoltCircleRadiusMm);
                  Equal(Math.Sqrt(pt[0]*pt[0]+pt[1]*pt[1]),p.BoltCircleRadiusMm,"螺栓圆"); }
            }
            var normal=TankManholeCalculator.Calculate(new TankManholeParameters());
            Equal(normal.Size.NominalDn,600,"默认 DN"); Equal(normal.FlangeFrontMm,205,"法兰站位");
            Equal(normal.CoverFrontMm,262,"盖板站位");
            var reversed=TankManholeCalculator.Calculate(new TankManholeParameters {Mirrored=true});
            Equal(reversed.HeadingRadians,Math.PI,"反向角度");
            Reject(()=>TankManholeCalculator.Calculate(new TankManholeParameters {NominalDn=550}),"非法公称尺寸");
            Reject(()=>TankManholeCalculator.Calculate(new TankManholeParameters {PressureLbs=900}),"非法压力等级");
            Reject(()=>TankManholeCalculator.Calculate(new TankManholeParameters {NeckLengthMm=0}),"非法筒节长度");
            Reject(()=>TankManholeCalculator.Calculate(new TankManholeParameters {HeadingDegrees=double.NaN}),"非法方向");
            CheckDavitSupport();
            CheckHingePin();
            Console.WriteLine("罐壁人孔尺寸、站位、螺栓圆、吊杆回转支撑件、铰链销轴开口销和非法输入校验通过。");
        }
        private static void Near(double a,double b,double tolerance,string label)
        { if(Math.Abs(a-b)>tolerance) throw new Exception(label+": "+a+" 与 "+b+" 相差超过 "+tolerance); }
        /// <summary>铰链销轴与开口销：销轴上下**两端**必须各有一个开口销，位置对称、
        /// 落在上下吊耳之外，孔与销轴同轴才能插得进去。</summary>
        private static void CheckHingePin()
        {
            Equal(TankManholeCalculator.HingeLugZmm,45.5,"吊耳站位");
            Equal(TankManholeCalculator.HingeLugZmm*2,TankManholeCalculator.HingeLugGapMm+
                TankManholeCalculator.HingeLugThicknessMm,"吊耳净距 75 + 板厚");
            Equal(TankManholeCalculator.HingePinHalfLength(),73.5,"销轴半长 = 45.5 + 8 + 20");
            var stations=TankManholeCalculator.HingeCotterStations();
            Equal(stations.Length,2,"开口销数量（上下各一个）");
            Near(stations[0]+stations[1],0.0,1e-12,"两只开口销关于销轴中心对称");
            Equal(stations[1],-stations[0],"两只开口销等距反向");
            Near(Math.Abs(stations[0]),
                TankManholeCalculator.HingePinHalfLength()-TankManholeCalculator.HingeCotterEndInsetMm,
                1e-12,"开口销孔到销轴端面 12");
            double lugFace=TankManholeCalculator.HingeLugZmm+TankManholeCalculator.HingeLugThicknessMm/2.0;
            if(Math.Abs(stations[0])<=lugFace) throw new Exception("开口销必须落在吊耳外侧，否则挡不住销轴。");
            if(Math.Abs(stations[0])>TankManholeCalculator.HingePinHalfLength())
                throw new Exception("开口销孔必须在销轴范围之内。");
            if(!(TankManholeCalculator.HingeCotterHoleDiameterMm>TankManholeCalculator.HingeCotterDiameterMm))
                throw new Exception("开口销孔必须大于开口销直径。");
        }
        /// <summary>吊杆回转支撑件：与 Python 版（tank_wall_manhole.py）对齐后的径向几何。</summary>
        private static void CheckDavitSupport()
        {
            var p=TankManholeCalculator.Calculate(new TankManholeParameters {
                NominalDn=500,PressureLbs=150});   // 支撑件几何断言固定在 DN500/ASA150（D=40）
            double d=p.Size.DavitDiameterMm;
            Equal(d,40.0,"DN500/ASA150 吊杆直径");
            // 焊面 = √(R²-80²)-2（80 = 净高 128/2 + 板厚 16）。
            Near(TankManholeCalculator.DavitSupportAnchorY(p.FlangeRadiusMm),374.596602,0.0001,"支撑件焊面径向位置");
            // 外端面 = 立柱轴线 + D/2 + 20 + 16（16 为扫掠轮廓厚度，Python 扫掠把它加在路径终点之外）。
            Near(TankManholeCalculator.DavitSupportOuterFaceY(p.PostYmm,d),496.0,0.0001,"支撑件外端面径向位置");
            Equal(TankManholeCalculator.DavitSupportOuterFaceY(p.PostYmm,d)-p.PostYmm,d/2+20+16,"立柱轴线到外端面");
            Near(TankManholeCalculator.DavitSupportChamferDistance(d,p.Size.FlangeThicknessMm),
                10.0*Math.Sqrt(3.0),0.0001,"开口端 30° 倒角收窄长度");
            var outline=TankManholeCalculator.DavitSupportOutline(d,p.Size.FlangeThicknessMm,p.PostYmm,p.FlangeRadiusMm);
            if(outline.Count!=40) throw new Exception("支撑件轮廓点数应为 40，实际 "+outline.Count);
            double minY=double.MaxValue,maxY=double.MinValue,minZ=double.MaxValue,maxZ=double.MinValue;
            double front=TankManholeCalculator.DavitSupportAnchorY(p.FlangeRadiusMm);
            int mouthPoints=0,outerPoints=0;
            foreach(var q in outline)
            {
                minY=Math.Min(minY,q[0]); maxY=Math.Max(maxY,q[0]);
                minZ=Math.Min(minZ,q[1]); maxZ=Math.Max(maxZ,q[1]);
                if(Math.Abs(q[0]-front)<0.0001) mouthPoints++;                       // 开口端的四个角
                if(q[0]>TankManholeCalculator.DavitSupportOuterFaceY(p.PostYmm,d)-0.0001) outerPoints++;
            }
            Equal(maxY,TankManholeCalculator.DavitSupportOuterFaceY(p.PostYmm,d),"轮廓外端面");
            Near(minY,front,0.0001,"轮廓焊面");
            Near(maxY-minY,121.403398,0.0001,"支撑件径向长度（路径 105.4 + 腹板厚 16）");
            Equal(maxZ,80.0,"轮廓顶面"); Equal(minZ,-80.0,"轮廓底面");
            Equal(mouthPoints,4,"开口端轮廓点（上下臂各 2 个，臂厚 16）");
            Equal(outerPoints,2,"背板外表面轮廓点（= 上下 R20 切点）");
            // 全规格不变量：立柱轴线到外端面恒为 D/2 + 20 + 16。
            int[] dn={450,500,600},pressure={150,300,600};
            for(int i=0;i<3;i++) for(int j=0;j<3;j++)
            {
                var q=TankManholeCalculator.Calculate(new TankManholeParameters {NominalDn=dn[i],PressureLbs=pressure[j]});
                Equal(TankManholeCalculator.DavitSupportOuterFaceY(q.PostYmm,q.Size.DavitDiameterMm)-q.PostYmm,
                    q.Size.DavitDiameterMm/2+36,"全规格支撑件外端面");
                TankManholeCalculator.DavitSupportOutline(q.Size.DavitDiameterMm,q.Size.FlangeThicknessMm,
                    q.PostYmm,q.FlangeRadiusMm);
            }
            Reject(()=>TankManholeCalculator.DavitSupportOutline(d,0.0,p.PostYmm,p.FlangeRadiusMm),"非法法兰边缘厚度");
            // 剖面段：必须是 8 直线 + 4 真圆弧、首尾闭合，圆弧半径 20/20/10/10，
            // 且圆弧中点确实在弧上（到弦的矢高 = r(1-cos45°)）——折线近似会让圆角出现成排分面棱。
            var profile=TankManholeCalculator.DavitSupportProfile(d,p.Size.FlangeThicknessMm,p.PostYmm,p.FlangeRadiusMm);
            if(profile.Count!=12) throw new Exception("支撑件剖面应为 12 段，实际 "+profile.Count);
            int arcCount=0;
            foreach(var segment in profile)
            {
                if(!segment.IsArc) continue;
                arcCount++;
                Near(Math.Abs(segment.SweepAngle),Math.PI/2,1e-9,"圆角圆弧包角");
                bool isOuter=segment.Radius>15.0;
                Near(segment.Radius,isOuter?20.0:10.0,1e-9,"圆角半径");
                double chordY=(segment.Y1+segment.Y2)/2.0,chordZ=(segment.Z1+segment.Z2)/2.0;
                Near(Math.Sqrt((segment.MidY-chordY)*(segment.MidY-chordY)+
                    (segment.MidZ-chordZ)*(segment.MidZ-chordZ)),
                    segment.Radius*(1.0-Math.Cos(Math.PI/4.0)),1e-9,"圆弧矢高（必须真圆弧）");
                Near(Math.Sqrt((segment.MidY-segment.CenterY)*(segment.MidY-segment.CenterY)+
                    (segment.MidZ-segment.CenterZ)*(segment.MidZ-segment.CenterZ)),
                    segment.Radius,1e-9,"圆弧中点到圆心");
            }
            Equal(arcCount,4,"圆角圆弧段数");
            for(int i=0;i<profile.Count;i++)
            {
                var current=profile[i];
                var next=profile[(i+1)%profile.Count];
                Near(current.Y2,next.Y1,1e-9,"剖面段首尾相接（径向）");
                Near(current.Z2,next.Z1,1e-9,"剖面段首尾相接（竖直）");
            }
            // 点列展开仍是 40 点，且与逐段展开一致（圆弧 8 段/个）。
            Equal(outline.Count,40,"剖面点列点数");
            // 盖板吊耳：轴向对称于螺柱轴线（孔在板宽正中），板长不变。
            var lugSpan=TankManholeCalculator.CoverLugSpan(p.CoverBackMm,p.CoverFrontMm,p.DavitXmm);
            Equal((lugSpan[0]+lugSpan[1])/2.0,p.DavitXmm,"吊耳孔居中（螺柱轴线=板宽中心）");
            Equal(lugSpan[1]-lugSpan[0],p.CoverFrontMm+25-p.CoverBackMm,"吊耳板长不变");
            Near(lugSpan[0],224.5,1e-9,"吊耳后端（DN500）");
            Near(lugSpan[1],299.5,1e-9,"吊耳前端（DN500）");
        }
    }
}
