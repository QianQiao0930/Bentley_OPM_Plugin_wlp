using System;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Equal(double a,double b){if(Math.Abs(a-b)>1e-9)throw new Exception(a+" != "+b);}
        private static void Reject(Action<SquareManholeParameters> change)
        {
            var p=new SquareManholeParameters();change(p);
            try{SquareManholeCalculator.Calculate(p);}catch(InvalidOperationException){return;}
            throw new Exception("非法尺寸未拒绝。");
        }
        private static void Main()
        {
            var d=SquareManholeCalculator.Calculate(new SquareManholeParameters());
            Equal(d.BarrelOutsideWidthMm,608);Equal(d.BarrelOutsideDepthMm,608);
            Equal(d.TotalHeightMm,104);Equal(d.CoverBottomMm,64);Equal(d.ClearanceXmm,2);Equal(d.ClearanceYmm,2);
            var r=SquareManholeCalculator.Calculate(new SquareManholeParameters {BarrelWidthMm=500,BarrelDepthMm=400,
                BarrelHeightMm=150,CoverWidthMm=520,CoverDepthMm=420,RotationDegrees=90});
            Equal(r.BarrelOutsideWidthMm,508);Equal(r.BarrelOutsideDepthMm,408);Equal(r.CoverBottomMm,114);
            SquareManholeCalculator.Calculate(new SquareManholeParameters {CoverHeightMm=4,BarrelHeightMm=50});
            Reject(p=>p.BarrelWidthMm=0);Reject(p=>p.WallMm=-1);Reject(p=>p.CoverWidthMm=616);
            Reject(p=>p.CoverDepthMm=616);Reject(p=>p.CoverHeightMm=3);Reject(p=>p.BarrelHeightMm=49);
            Reject(p=>p.CoverHeightMm=105);Reject(p=>p.WallMm=double.NaN);
            Reject(p=>p.CoverWidthMm=double.PositiveInfinity);Reject(p=>p.RotationDegrees=double.NaN);
            Console.WriteLine("方形人孔：默认/矩形尺寸、间隙、套盖定位、边界与非法输入检查通过。");
        }
    }
}
