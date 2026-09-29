using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class ElbowTrunnionCalculator
    {
        private const double OrientationTolerance = 0.02;
        private static readonly Dictionary<int, string> Nps = new Dictionary<int, string> {
            {15,"1/2\""},{20,"3/4\""},{25,"1\""},{32,"1-1/4\""},{40,"1-1/2\""},
            {50,"2\""},{65,"2-1/2\""},{80,"3\""},{100,"4\""},{125,"5\""},
            {150,"6\""},{200,"8\""},{250,"10\""},{300,"12\""},{350,"14\""},
            {400,"16\""},{450,"18\""},{500,"20\""},{550,"22\""},{600,"24\""},
            {650,"26\""},{700,"28\""},{750,"30\""},{800,"32\""},{850,"34\""},
            {900,"36\""},{950,"38\""},{1000,"40\""},{1050,"42\""},{1100,"44\""},
            {1200,"48\""} };

        internal static double UnitScale(string unit, double nominalRaw)
        {
            string value = (unit ?? "").Trim().ToUpperInvariant();
            if (value == "MM" || value == "MILLIMETER" || value == "MILLIMETRE" || value == "毫米") return 1;
            if (value == "M" || value == "METER" || value == "METRE" || value == "米") return 1000;
            if (value == "IN" || value == "INCH" || value == "INCHES") return 25.4;
            return nominalRaw > 0 && nominalRaw < 2 ? 1000 : 1;
        }

        internal static double ExtentFromViewProjection(double originX,double originY,
            double axisX,double axisY,double cursorX,double cursorY,double axisLengthMm)
        {
            if (!Finite(originX) || !Finite(originY) || !Finite(axisX) || !Finite(axisY) ||
                !Finite(cursorX) || !Finite(cursorY) || !Finite(axisLengthMm) || axisLengthMm<=0)
                throw new InvalidOperationException("视图投影坐标或基准长度无效。");
            double dx=axisX-originX,dy=axisY-originY;
            double denominator=dx*dx+dy*dy;
            if (denominator<=1e-6)
                throw new InvalidOperationException("当前视图看不到拉伸方向，请切换侧视图或轴测视图。");
            return axisLengthMm*((cursorX-originX)*dx+(cursorY-originY)*dy)/denominator;
        }
        internal static ElbowFrame Frame(double[] m, double uorPerMm, double run, double outlet,
            ElbowOrientation orientation, bool allowDownward)
        {
            if (m == null || m.Length != 12 || !Finite(uorPerMm) || !Finite(run) || !Finite(outlet) || uorPerMm <= 0 || run <= 0 || outlet <= 0)
                throw new InvalidOperationException("弯头变换矩阵或模型单位不完整。");
            foreach (double value in m) if (!Finite(value)) throw new InvalidOperationException("弯头变换矩阵含无效数值。");
            if (Math.Abs(run-outlet) > Math.Max(run,outlet)*0.02)
                throw new InvalidOperationException("仅支持两端中心距一致的标准 90° 弯头。");
            var x = new VectorMm(m[0],m[4],m[8]).Unit();
            var z = new VectorMm(m[2],m[6],m[10]).Unit();
            if (Math.Abs(x.Dot(z)) > OrientationTolerance)
                throw new InvalidOperationException("弯头变换矩阵的 X/Z 轴不正交。");
            var origin = new VectorMm(m[3],m[7],m[11]) * (1/uorPerMm);
            var center = origin + z*outlet;
            var end = origin + x*run + z*outlet;
            var f = new ElbowFrame { AxisX=x, AxisZ=z, Origin=origin, RunPort=origin,
                OutletPort=end, ArcCenter=center, RunLengthMm=run, OutletLengthMm=outlet };
            if (orientation == ElbowOrientation.Horizontal)
            {
                if (Math.Abs(x.Z)>OrientationTolerance || Math.Abs(z.Z)>OrientationTolerance)
                    throw new InvalidOperationException("所选弯头不是水平弯头，两端轴线应水平。");
                double radius=(run+outlet)/2;
                f.SupportAxis=center+(x-z)*(radius/Math.Sqrt(2));
                f.HorizontalPort=f.SupportAxis;
                f.VerticalPort=f.SupportAxis;
                f.HorizontalDirection=(x+z).Unit();
                return f;
            }
            VectorMm outward;
            if (Math.Abs(x.Z)<=OrientationTolerance && Math.Abs(z.Z)>=1-OrientationTolerance)
            {
                f.HorizontalPort=origin; f.VerticalPort=end; f.HorizontalDirection=x; outward=z;
            }
            else if (Math.Abs(x.Z)>=1-OrientationTolerance && Math.Abs(z.Z)<=OrientationTolerance)
            {
                f.HorizontalPort=end; f.VerticalPort=origin; f.HorizontalDirection=z*(-1); outward=x*(-1);
            }
            else throw new InvalidOperationException("所选弯头不是竖直弯头。");
            f.VerticalEndUp=outward.Z>0;
            if (!f.VerticalEndUp && !allowDownward)
                throw new InvalidOperationException("竖直耳轴只支持竖直端朝上的弯头。");
            f.HorizontalDirection=new VectorMm(f.HorizontalDirection.X,f.HorizontalDirection.Y,0).Unit();
            return f;
        }

        internal static ElbowTrunnionPlan Calculate(ElbowTrunnionSelection selection, ElbowTrunnionParameters p)
        {
            if (selection == null || selection.Frame == null || p == null)
                throw new InvalidOperationException("请先点选有效的弯头。");
            if (!Finite(p.ExtentMm) || p.ExtentMm <= 0 || p.ExtentMm > 20000)
                throw new InvalidOperationException("高度 H 或长度 L 必须在 0～20000 mm 内。");
            if (p.Plate!='A' && p.Plate!='B' && p.Plate!='C')
                throw new InvalidOperationException("未知底板或端板类型。");
            if (Array.IndexOf(new[]{"L","C1","C2","A1","A2","S"},p.Material)<0)
                throw new InvalidOperationException("未知材料代码。");
            if (p.Trunnion==TrunnionOrientation.Horizontal && p.Ptfe)
                throw new InvalidOperationException("水平耳轴没有 PTFE 覆面选项。");
            if (p.Trunnion==TrunnionOrientation.Vertical && p.BottomFlat)
                throw new InvalidOperationException("竖直耳轴没有底平对齐选项。");
            if (p.Ptfe && p.Plate=='C')
                throw new InvalidOperationException("无底板时不能选用 PTFE 覆面。");
            if (!Finite(selection.OutsideDiameterMm) || selection.OutsideDiameterMm<=0)
                throw new InvalidOperationException("主管外径无效。");
            var size=ElbowTrunnionCatalog.ForMainDn(selection.MainDn);
            double wall=p.WallOverrideMm ?? size.WallMm;
            if (!Finite(wall) || wall<=0 || wall>=size.OutsideMm/2)
                throw new InvalidOperationException("耳轴壁厚必须大于零且小于耳轴半径。");
            double plate=p.Trunnion==TrunnionOrientation.Vertical
                ? (p.Plate=='C' ? 0 : size.PlateThicknessMm)
                : ElbowTrunnionCatalog.EndPlateThickness(size.Dn,p.Plate);
            double liner=p.Ptfe ? 3 : 0;
            var f=selection.Frame;
            var result=new ElbowTrunnionPlan { Parameters=p,Selection=selection,TrunnionDn=size.Dn,
                TrunnionOdMm=size.OutsideMm,WallMm=wall,PlateSizeMm=size.SquarePlateMm,
                PlateThicknessMm=plate,LinerThicknessMm=liner };
            if (p.Trunnion==TrunnionOrientation.Vertical)
            {
                if (p.ExtentMm<=selection.OutsideDiameterMm/2+plate+liner)
                    throw new InvalidOperationException("高度 H 小于弯头半径、底板及覆面所需空间。");
                double lowest=f.HorizontalPort.Z-p.ExtentMm;
                var axis=f.VerticalPort;
                result.Direction=new VectorMm(0,0,1);
                result.LinerStartMm=new VectorMm(axis.X,axis.Y,lowest);
                result.LinerEndMm=result.LinerStartMm+result.Direction*liner;
                result.PlateStartMm=result.LinerEndMm;
                result.PlateEndMm=result.PlateStartMm+result.Direction*plate;
                result.TubeStartMm=result.PlateEndMm;
                result.TubeEndMm=axis;
                if (result.TubeEndMm.Z<=result.TubeStartMm.Z)
                    throw new InvalidOperationException("竖直耳轴上端必须高于底板。");
                double ventZ=result.TubeStartMm.Z+Math.Min(20,Math.Max(8,(p.ExtentMm-plate-liner)*0.08));
                var vent=new VectorMm(axis.X,axis.Y,ventZ);
                var cross=new VectorMm(-f.HorizontalDirection.Y,f.HorizontalDirection.X,0).Unit();
                result.VentStartMm=vent-cross*size.OutsideMm;
                result.VentEndMm=vent+cross*size.OutsideMm;
            }
            else
            {
                double min=selection.OutsideDiameterMm/2+size.OutsideMm+plate+20;
                if (p.ExtentMm<=min)
                    throw new InvalidOperationException("长度 L 太短，无法容纳鞍口、通气孔和端板。");
                double offset=0;
                if (p.BottomFlat)
                {
                    if (selection.OutsideDiameterMm<size.OutsideMm)
                        throw new InvalidOperationException("耳轴外径大于主管，无法底平。");
                    offset=(selection.OutsideDiameterMm-size.OutsideMm)/2;
                }
                VectorMm direction,origin,port;
                if (p.Elbow==ElbowOrientation.Vertical)
                {
                    direction=f.HorizontalDirection;
                    origin=new VectorMm(f.VerticalPort.X,f.VerticalPort.Y,f.HorizontalPort.Z);
                    port=f.HorizontalPort;
                }
                else
                {
                    direction=p.OutletSide ? f.AxisZ*(-1) : f.AxisX;
                    origin=f.RunPort+f.AxisX*f.RunLengthMm;
                    port=p.OutletSide ? f.OutletPort : f.RunPort;
                }
                origin=new VectorMm(origin.X,origin.Y,origin.Z-offset);
                port=new VectorMm(port.X,port.Y,port.Z-offset);
                result.Direction=direction;
                result.TubeStartMm=port+direction;
                result.TubeEndMm=origin+direction*(p.ExtentMm-plate);
                result.PlateStartMm=result.TubeEndMm;
                result.PlateEndMm=origin+direction*p.ExtentMm;
                if ((result.TubeEndMm-result.TubeStartMm).Dot(direction)<=0)
                    throw new InvalidOperationException("长度 L 不足以容纳耳轴管坯。");
                double holeX=Math.Max(selection.OutsideDiameterMm/2+size.OutsideMm/2,
                    p.ExtentMm-plate-20);
                var vent=origin+direction*holeX;
                result.VentStartMm=vent+new VectorMm(0,0,-size.OutsideMm);
                result.VentEndMm=vent+new VectorMm(0,0,size.OutsideMm);
            }
            result.SupportCode=(p.Trunnion==TrunnionOrientation.Vertical
                ? (p.Elbow==ElbowOrientation.Vertical ? ElbowTrunnionCatalog.F2VerticalCode : ElbowTrunnionCatalog.F2HorizontalCode)
                : (p.Elbow==ElbowOrientation.Vertical ? ElbowTrunnionCatalog.F4VerticalCode : ElbowTrunnionCatalog.F5HorizontalCode));
            result.AssemblyTag=Number(result,size);
            return result;
        }

        private static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }

        private static string Number(ElbowTrunnionPlan plan,TrunnionSize size)
        {
            var p=plan.Parameters;
            string suffix=Math.Abs(plan.WallMm-size.WallMm)<1e-6 ? "" :
                "("+plan.WallMm.ToString("G",CultureInfo.InvariantCulture)+")";
            string extent=Math.Floor(p.ExtentMm+0.5).ToString("0",CultureInfo.InvariantCulture);
            string mainDiameter=!string.IsNullOrEmpty(plan.Selection.MainSizeLabel)
                ? plan.Selection.MainSizeLabel : p.NamingUnit==PipeNamingUnit.Imperial
                ? Nps[plan.Selection.MainDn] : "DN"+plan.Selection.MainDn;
            string trunnionDiameter=p.NamingUnit==PipeNamingUnit.Imperial
                ? Nps[size.Dn] : "DN"+size.Dn;
            if (p.Trunnion==TrunnionOrientation.Vertical)
                return "F2-"+mainDiameter+"-"+trunnionDiameter+suffix+"-"+p.Material+"-"+extent+"-"+p.Plate+
                    (p.Ptfe?"-F":"")+(p.Elbow==ElbowOrientation.Horizontal?"-HE":"");
            if (p.Elbow==ElbowOrientation.Vertical)
                return "F4-"+mainDiameter+"-"+trunnionDiameter+suffix+"-"+p.Material+"-"+extent+"-"+p.Plate+
                    (p.BottomFlat?(plan.Selection.Frame.VerticalEndUp?"-FB1":"-FB2"):"");
            var d=plan.Direction;
            int azimuth=((int)Math.Floor((Math.Atan2(d.X,d.Y)*180/Math.PI+360)%360+0.5))%360;
            return "F5-"+mainDiameter+"-"+trunnionDiameter+suffix+"-"+p.Material+"-"+extent+"-"+p.Plate+"-"+azimuth+
                (p.BottomFlat?"-FB":"");
        }
    }
}

