using System;
namespace SteelSectionProbe
{
    internal static class SquareManholeCalculator
    {
        internal static SquareManholePlan Calculate(SquareManholeParameters p)
        {
            if(p==null)throw new ArgumentNullException("p");
            foreach(double v in new[]{p.BarrelWidthMm,p.BarrelDepthMm,p.BarrelHeightMm,p.CoverWidthMm,p.CoverDepthMm,p.CoverHeightMm,p.WallMm})
                if(double.IsNaN(v)||double.IsInfinity(v)||v<=0)throw new InvalidOperationException("所有尺寸和壁厚必须是有限的正数。");
            if(double.IsNaN(p.RotationDegrees)||double.IsInfinity(p.RotationDegrees))throw new InvalidOperationException("朝向角必须是有限的数字。");
            if(p.CoverHeightMm<p.WallMm)throw new InvalidOperationException("盖板高度必须不小于壁厚。");
            if(p.BarrelHeightMm<Math.Max(50,p.CoverHeightMm-p.WallMm))throw new InvalidOperationException("筒体高度不足，无法容纳盖板裙边和距底 50 mm 的把手。");
            double bx=p.BarrelWidthMm+2*p.WallMm,by=p.BarrelDepthMm+2*p.WallMm;
            double cx=(p.CoverWidthMm-2*p.WallMm-bx)/2,cy=(p.CoverDepthMm-2*p.WallMm-by)/2;
            if(cx<=0||cy<=0)throw new InvalidOperationException("盖板内腔必须大于筒体外形，请增大盖板长宽。");
            return new SquareManholePlan {Parameters=p,BarrelOutsideWidthMm=bx,BarrelOutsideDepthMm=by,
                ClearanceXmm=cx,ClearanceYmm=cy,CoverBottomMm=p.BarrelHeightMm-p.CoverHeightMm+p.WallMm,
                TotalHeightMm=p.BarrelHeightMm+p.WallMm};
        }
    }
}
