using System;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Equal(double a,double b,string label)
        { if(Math.Abs(a-b)>0.00001)throw new Exception(label+": "+a+" != "+b); }
        private static void Reject(Action action,string label)
        { try { action(); } catch(InvalidOperationException) { return; } throw new Exception(label+" 应被拒绝。"); }
        private static void Main()
        {
            if(NozzleCatalog.Ratings.Length!=1 || NozzleCatalog.Ratings[0]!="CL150")throw new Exception("法兰等级");
            var small=NozzleCatalog.AvailableDns("CL150","Ia_Sch10");
            var large=NozzleCatalog.AvailableDns("CL150","Ia_large_dia_welded_wall12.5");
            if(!small.Contains(15) || !small.Contains(600) || small.Contains(650))throw new Exception("Sch10 DN 范围");
            if(!large.Contains(650) || !large.Contains(1500) || large.Contains(1600))throw new Exception("大直径 DN 范围");
            var p=NozzleCalculator.Calculate(new NozzleParameters());
            Equal(p.Size.PipeOutsideMm,114.3,"DN100 外径");
            Equal(p.WallMm,3.2,"DN100 壁厚");
            Equal(p.Size.FlangeThicknessMm,22.3,"DN100 法兰厚");
            Equal(p.PipeLengthMm,177.7,"名义长度");
            Equal(p.BoreRadiusMm,53.95,"通孔半径");
            if(!NozzleCalculator.Calculate(new NozzleParameters { DrawBoltHoles=true }).Parameters.DrawBoltHoles)throw new Exception("螺栓孔开关");
            var h=NozzleCalculator.BoltOffset(1,p.Size.BoltCount,p.Size.BoltCircleMm/2);
            Equal(Math.Sqrt(h[0]*h[0]+h[1]*h[1]),p.Size.BoltCircleMm/2,"螺栓圆");
            Reject(()=>NozzleCalculator.Calculate(new NozzleParameters{TotalLengthMm=20}),"短于法兰厚度");
            Reject(()=>NozzleCalculator.Calculate(new NozzleParameters{WallOverrideMm=60}),"过大壁厚");
            Reject(()=>NozzleCalculator.Calculate(new NozzleParameters{Axis="Q"}),"无效方向");
            Reject(()=>NozzleCatalog.Get("CL150","Ia_Sch10",650),"无效系列组合");
            Console.WriteLine("实体管口表、DN 联动、长度、通孔和非法输入校验通过。Sch10 "+small.Length+" 项，大直径 "+large.Length+" 项。");
        }
    }
}
