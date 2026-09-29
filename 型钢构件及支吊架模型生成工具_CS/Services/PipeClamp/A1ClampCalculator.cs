using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class A1ClampCalculator
    {
        internal static A1ClampPlan Calculate(int fallbackDn,bool isPipe,double? nominal,
            double angleDeg,string pipeNumber)
        {
            int dn=isPipe?A1ClampCatalog.MatchDn(nominal)??fallbackDn:fallbackDn;
            var row=A1ClampCatalog.Require(dn);
            if(double.IsNaN(angleDeg)||double.IsInfinity(angleDeg))
                throw new InvalidOperationException("开口角度无效。");
            double angle=((angleDeg%360)+360)%360;
            double nutHeight=row.Bolt*.8;
            double center=row.D-(row.D-row.OutsideMm/2)/2;
            double low1=center-nutHeight;
            if(low1<=0||center+nutHeight>=row.D)
                throw new InvalidOperationException("螺母超出直腿，无法生成。");
            double length=center+nutHeight+row.C/2.0;
            string f=dn.ToString(CultureInfo.InvariantCulture);
            string bolt="M"+row.Bolt.ToString(CultureInfo.InvariantCulture);
            return new A1ClampPlan{
                Row=row,AngleDeg=angle,NutHeightMm=nutHeight,NutAcrossFlatsMm=row.Bolt*1.5,
                NutCenterMm=center,NutLow1Mm=low1,NutLow2Mm=center,
                BoltLengthMm=length,PipeNumber=pipeNumber??"",
                AssemblyTag="A1-DN"+f+"-"+bolt+"-"+angle.ToString("0.#",CultureInfo.InvariantCulture)+"°",
                AssemblySpecification="U型螺栓 "+bolt+"（DN"+f+" / "+row.Nps+"）：两腿中心距 C="+row.C+
                    "、管中心→腿端 D="+row.D+"、直腿段 "+row.D+
                    "、弯弧包管净空 "+((row.B-row.OutsideMm)/2).ToString("0.0",CultureInfo.InvariantCulture)+" mm",
                BoltSpecification=bolt+"×"+length.ToString("0.#",CultureInfo.InvariantCulture)+
                    "（C="+row.C+"，D="+row.D+"，直腿段 "+row.D+"）",
                NutSpecification=bolt+"（对边 "+(row.Bolt*1.5).ToString("0.#",CultureInfo.InvariantCulture)+"）"};
        }

        /// <summary>
        /// 管道径向平面的右手正交基（角度计算与精确绘图罗盘定向共用，保证两者一致）：
        /// zAxis = 管轴（径向平面法向，也是罗盘平面的法向）；
        /// xAxis = 开口角 0° 方向；yAxis = 角度增大方向。三轴两两正交、单位长、右手系。
        /// </summary>
        internal static void RadialFrame(double[] axis,out double[] xAxis,out double[] yAxis,
            out double[] zAxis)
        {
            double length=Math.Sqrt(Dot(axis,axis));
            if(length<1e-12)throw new InvalidOperationException("管轴长度为零。");
            double[] ex={axis[0]/length,axis[1]/length,axis[2]/length};
            double[] reference=Math.Abs(ex[2])>.99?new[]{1.0,0.0,0.0}:new[]{0.0,0.0,1.0};
            double dot=Dot(ex,reference);
            double[] ez={reference[0]-dot*ex[0],reference[1]-dot*ex[1],reference[2]-dot*ex[2]};
            double upLength=Math.Sqrt(Dot(ez,ez));
            if(upLength<1e-12)throw new InvalidOperationException("管轴方向与参考方向平行。");
            for(int i=0;i<3;i++)ez[i]/=upLength;
            double[] ey={ez[1]*ex[2]-ez[2]*ex[1],ez[2]*ex[0]-ez[0]*ex[2],
                ez[0]*ex[1]-ez[1]*ex[0]};
            zAxis=ex;
            xAxis=ez;
            yAxis=new[]{-ey[0],-ey[1],-ey[2]};
        }
        /// <summary>
        /// 精确绘图罗盘的右手正交基（**顺着管轴**定向，与 Python 端「本地 X 沿管轴」一致）：
        /// xAxis = 管轴（罗盘 X 轴顺着管道走向）；yAxis = 开口角 0° 方向（径向、默认朝上）；
        /// zAxis = 罗盘平面法向（切向，= xAxis×yAxis）。
        /// 于是罗盘平面同时包含管轴与开口方向 —— 顺着管轴，也正是"管道径向所在的平面"。
        /// 三轴与 <see cref="RadialFrame"/> 同一套基，只是换了一组循环次序，角度仍由
        /// <see cref="AngleFromCursor"/> 在径向平面内求，罗盘定向不会改动开口角的定义。
        /// </summary>
        internal static void CompassFrame(double[] axis,out double[] xAxis,out double[] yAxis,
            out double[] zAxis)
        {
            double[] up,turning,alongAxis;
            RadialFrame(axis,out up,out turning,out alongAxis);
            xAxis=alongAxis;   // 罗盘 X：顺管轴
            yAxis=up;          // 罗盘 Y：开口 0°（径向朝上）
            zAxis=turning;     // 罗盘 Z：平面法向（切向），X×Y=Z 保持右手系
        }
        private static double Dot(double[] a,double[] b)
        { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
        /// <summary>把光标向量投影到管道径向平面，求从默认开口方向起的右手旋转角。</summary>
        internal static double AngleFromCursor(double[] axis,double[] fromCenter)
        {
            double[] xAxis,yAxis,zAxis;
            RadialFrame(axis,out xAxis,out yAxis,out zAxis);
            double along=Dot(fromCenter,zAxis);
            double[] v={fromCenter[0]-along*zAxis[0],fromCenter[1]-along*zAxis[1],
                fromCenter[2]-along*zAxis[2]};
            double up=Dot(v,xAxis);
            double side=Dot(v,yAxis);
            if(up*up+side*side<1e-12) return 0;
            return (Math.Atan2(side,up)*180/Math.PI+360)%360;
        }
    }
}
