using System;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static void Equal(double actual,double expected,string label)
        {
            if (Math.Abs(actual-expected)>0.01) throw new Exception(label+": "+actual+" != "+expected);
        }
        private static void Reject(Action action,string label)
        {
            try { action(); }
            catch(InvalidOperationException) { return; }
            throw new Exception(label+" 应被拒绝。");
        }
        private static double[] Matrix(bool horizontal)
        {
            return horizontal
                ? new double[] {1,0,0,0, 0,0,1,0, 0,1,0,0}
                : new double[] {1,0,0,0, 0,0,0,0, 0,0,1,0};
        }
        private static void Main()
        {
            Equal(ElbowTrunnionCalculator.ExtentFromViewProjection(
                10,20,10,120,10,70,1000),500,"视图投影拉伸长度");
            Reject(()=>ElbowTrunnionCalculator.ExtentFromViewProjection(
                10,20,10,20,15,30,1000),"端视图中不可见的拉伸方向");
            var vf=ElbowTrunnionCalculator.Frame(Matrix(false),1,100,100,
                ElbowOrientation.Vertical,false);
            var hf=ElbowTrunnionCalculator.Frame(Matrix(true),1,100,100,
                ElbowOrientation.Horizontal,false);
            Equal(vf.VerticalPort.Z,100,"竖直弯头端口");
            Equal(hf.SupportAxis.X,100/Math.Sqrt(2),"水平弯头 45° 中点 X");
            Equal(hf.SupportAxis.Y,100-100/Math.Sqrt(2),"水平弯头 45° 中点 Y");
            var vertical=new ElbowTrunnionParameters { Elbow=ElbowOrientation.Vertical,
                Trunnion=TrunnionOrientation.Vertical,ExtentMm=1000,Plate='A' };
            var vs=new ElbowTrunnionSelection { MainDn=100,OutsideDiameterMm=114.3,Frame=vf };
            var f2=ElbowTrunnionCalculator.Calculate(vs,vertical);
            Equal(f2.TubeEndMm.Z,100,"F2 竖直耳轴上端");
            Equal(f2.TubeStartMm.Z,-990,"F2 底板高度");
            if (!f2.AssemblyTag.StartsWith("F2-DN100-DN")) throw new Exception("F2 公制编号");
            vertical.NamingUnit=PipeNamingUnit.Imperial;
            if (!ElbowTrunnionCalculator.Calculate(vs,vertical).AssemblyTag.StartsWith("F2-4\"-"))
                throw new Exception("F2 英制编号");
            vertical.NamingUnit=PipeNamingUnit.Metric;
            var horizontalVertical=new ElbowTrunnionParameters { Elbow=ElbowOrientation.Horizontal,
                Trunnion=TrunnionOrientation.Vertical,ExtentMm=1000,Plate='A' };
            var hs=new ElbowTrunnionSelection { MainDn=100,OutsideDiameterMm=114.3,Frame=hf };
            var f2he=ElbowTrunnionCalculator.Calculate(hs,horizontalVertical);
            Equal(f2he.TubeEndMm.X,hf.SupportAxis.X,"水平弯头竖直耳轴定位");
            if (!f2he.AssemblyTag.StartsWith("F2-DN100-DN") || !f2he.AssemblyTag.EndsWith("-HE"))
                throw new Exception("F2-HE 公制编号");
            var f4p=new ElbowTrunnionParameters { Elbow=ElbowOrientation.Vertical,
                Trunnion=TrunnionOrientation.Horizontal,ExtentMm=1000,Plate='A',
                BottomFlat=true };
            var f4=ElbowTrunnionCalculator.Calculate(vs,f4p);
            Equal(f4.PlateEndMm.X,1100,"F4 水平伸出末端");
            if (!f4.AssemblyTag.StartsWith("F4-DN100-DN") || !f4.AssemblyTag.EndsWith("-FB1"))
                throw new Exception("F4 公制底平编号");
            f4p.NamingUnit=PipeNamingUnit.Imperial;
            if (!ElbowTrunnionCalculator.Calculate(vs,f4p).AssemblyTag.StartsWith("F4-4\"-"))
                throw new Exception("F4 英制编号");
            var f5p=new ElbowTrunnionParameters { Elbow=ElbowOrientation.Horizontal,
                Trunnion=TrunnionOrientation.Horizontal,ExtentMm=1000,Plate='A',OutletSide=true };
            var f5=ElbowTrunnionCalculator.Calculate(hs,f5p);
            Equal(f5.Direction.Y,-1,"F5 Outlet 伸出方向");
            if (!f5.AssemblyTag.StartsWith("F5-DN100-DN")) throw new Exception("F5 公制编号");
            f5p.NamingUnit=PipeNamingUnit.Imperial;
            if (!ElbowTrunnionCalculator.Calculate(hs,f5p).AssemblyTag.StartsWith("F5-4\"-"))
                throw new Exception("F5 英制编号");
            Reject(()=>ElbowTrunnionCatalog.MainDn(65),"未列出的主 DN65");
            Reject(()=>ElbowTrunnionCalculator.Frame(Matrix(true),1,100,100,
                ElbowOrientation.Vertical,false),"错误的弯头方向");
            vertical.ExtentMm=20;
            Reject(()=>ElbowTrunnionCalculator.Calculate(vs,vertical),"过短的 F2 高度");
            CheckListingContract(f4);
            Console.WriteLine("ElbowTrunnionCheck: 4 variants, projection, geometry, numbering, listing contract and invalid input passed.");
        }

        /// <summary>
        /// 清单属性契约：<c>SupportCode</c> 是 ASCII 代号（只用于 ItemType 命名），
        /// 写入 <c>PipeSupportComponents</c> 的 <c>SupportType</c> 必须是中文类型名，
        /// 与 Python 四个脚本的 <c>SUPPORT_TYPE</c> 逐字一致，否则两边写入的支吊架
        /// 无法按同一类型聚合套数。
        /// </summary>
        private static void CheckListingContract(ElbowTrunnionPlan plan)
        {
            // 弯头/耳轴方向 -> 代号 -> Python 的中文类型名
            var combos=new[]{
                new[]{ElbowTrunnionCatalog.F2VerticalCode,"F2-[竖直弯头的竖直耳轴]"},
                new[]{ElbowTrunnionCatalog.F2HorizontalCode,"F2-[水平弯头的竖直耳轴]"},
                new[]{ElbowTrunnionCatalog.F4VerticalCode,"F4-[竖直弯头的水平耳轴]"},
                new[]{ElbowTrunnionCatalog.F5HorizontalCode,"F5-[水平弯头的水平耳轴]"}};
            for(int i=0;i<combos.Length;i++)
            {
                if(ElbowTrunnionCatalog.SupportType(combos[i][0])!=combos[i][1])
                    throw new Exception("耳轴 SupportType 与 Python 不一致："+combos[i][1]);
                if(combos[i][0].IndexOf('[')>=0)
                    throw new Exception("耳轴 SupportCode 必须是 ASCII 代号："+combos[i][0]);
                for(int j=i+1;j<combos.Length;j++)
                    if(combos[i][0]==combos[j][0])
                        throw new Exception("耳轴 SupportCode 重复："+combos[i][0]);
            }
            if(plan.SupportCode!=ElbowTrunnionCatalog.F4VerticalCode)
                throw new Exception("F4 组合代号错误："+plan.SupportCode);
            bool rejected=false;
            try { ElbowTrunnionCatalog.SupportType("NOT_A_COMBO"); }
            catch(InvalidOperationException) { rejected=true; }
            if(!rejected) throw new Exception("未知耳轴组合代号应被拒绝。");
        }
    }
}
