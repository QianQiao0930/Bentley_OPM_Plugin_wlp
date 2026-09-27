using System;
namespace SteelSectionProbe
{
    /// <summary>
    /// G2 混凝土锚板的纯计算检查。断言对象为表 1 四子项尺寸、间距校验、
    /// 埋深自检与三种安装面的局部坐标轴方向（须与 Python
    /// <c>模块/公共/混凝土锚板.py</c> 的 <c>ANCHOR_TABLE</c> / <c>_PlateFrame</c> 一致）。
    /// </summary>
    internal static class Program
    {
        private static void Equal(double a,double b,string label)
        { if(Math.Abs(a-b)>0.00001) throw new Exception(label+": "+a+" != "+b); }
        private static void Equal(string a,string b,string label)
        { if(a!=b) throw new Exception(label+": \""+a+"\" != \""+b+"\""); }
        private static void Reject(Action action,string label)
        { try { action(); } catch(InvalidOperationException) { return; } throw new Exception(label+" 应被拒绝。"); }
        private static void Axis(double[] axis,double x,double y,double z,string label)
        { Equal(axis[0],x,label+" X"); Equal(axis[1],y,label+" Y"); Equal(axis[2],z,label+" Z"); }

        private static void Main()
        {
            CheckItems();
            CheckSpacing();
            CheckMountAxes();
            Console.WriteLine("G2 混凝土锚板：表 1 四子项、间距与埋深校核、三种安装面朝向矩阵全部通过。");
        }

        /// <summary>表 1 四子项：锚板、锚栓分段、埋深自检与清单规格串。</summary>
        private static void CheckItems()
        {
            // 子项 / 锚栓 / L / h_ef / G / T / MIN.S
            double[] boltDia={8,12,16,20}, boltLength={80,120,140,180}, embedment={55,90,100,125};
            double[] holeDia={10,14,18,22}, plateT={10,12,16,20}, minSpacing={75,100,125,150};
            double[] washerT={1.6,2.5,3.0,3.0}, nutH={6.5,10.0,13.0,16.0};
            string[] keys={"A","B","C","D"};
            double[] expectedOut={23.1,29.5,37.0,44.0};
            for(int i=0;i<keys.Length;i++)
            {
                var plan=G2AnchorCalculator.Calculate(new G2AnchorParameters {SubtypeKey=keys[i]});
                string tag=keys[i]+" 子项";
                Equal(plan.BoltDiameterMm,boltDia[i],tag+" 锚栓直径");
                Equal(plan.BoltLengthMm,boltLength[i],tag+" 锚栓总长 L");
                Equal(plan.HoleDiameterMm,holeDia[i],tag+" 孔径 G");
                Equal(plan.PlateThicknessMm,plateT[i],tag+" 板厚 T");
                Equal(plan.SpacingMm,minSpacing[i],tag+" 默认取 MIN.S");
                Equal(plan.PlateSideMm,minSpacing[i]+2.0*G2AnchorCatalog.PlateMarginMm,tag+" 锚板边长");
                // 螺杆外端 = 板厚 + 垫圈厚 + 螺母高 + 露头 5；总长 L 不变。
                Equal(plan.BoltOutLengthMm,plateT[i]+washerT[i]+nutH[i]+
                    G2AnchorCatalog.BoltProtrusionMm,tag+" 螺杆外端");
                Equal(plan.ActualEmbedmentMm,boltLength[i]-expectedOut[i],tag+" 有效埋深");
                if(plan.ActualEmbedmentMm<embedment[i])
                    throw new Exception(tag+" 有效埋深小于表 1 要求："+plan.ActualEmbedmentMm);
                Equal(plan.SleeveDiameterMm,boltDia[i]*G2AnchorCatalog.SleeveDiameterFactor,tag+" 套管外径");
                Equal(plan.SleeveLengthMm,plan.ActualEmbedmentMm*G2AnchorCatalog.SleeveEmbedFraction,
                    tag+" 套管长度");
                Equal(plan.BoltCount,4,tag+" 锚栓数量");
                Equal(plan.AssemblyTag,"G2-"+keys[i],tag+" 编号");
                Equal(plan.AssemblySpecification,
                    string.Format("G2-{0}：锚板 {1}×{1}×{2}（S={3}，4-φ{4}），膨胀锚栓 M{5}×{6} ×4",
                        keys[i],minSpacing[i]+100.0,plateT[i],minSpacing[i],holeDia[i],boltDia[i],
                        boltLength[i]),tag+" 整组规格");
            }
            Equal(G2AnchorCalculator.DescribeItem(G2AnchorCatalog.Require("A")),
                "A  |  M8×80  |  板厚 10  |  孔 φ10","A 子项下拉标签");
            Equal(G2AnchorCalculator.DescribePlate(G2AnchorCatalog.Require("D")),
                "250×250×20（板厚 T=20）","D 子项标准锚板读数");
            Equal(G2AnchorCalculator.DescribeBolt(G2AnchorCatalog.Require("C")),
                "M16×140 膨胀锚栓，孔径 φ18","C 子项锚栓读数");
            // 清单属性契约：SupportType 为中文类型名（写入属性值），FeatureCode 为 ASCII 代号
            // （只用于 ItemType 命名），须与 Python SUPPORT_TYPE / SUPPORT_CODE 一致。
            Equal(G2AnchorCatalog.SupportType,"G2-[混凝土锚板（膨胀螺栓）]","G2 中文类型名");
            Equal(G2AnchorCatalog.FeatureCode,"G2_ANCHOR_PLATE","G2 ASCII 代号");
        }

        /// <summary>间距 S：默认取 MIN.S，小于 MIN.S 或非正数被拒绝。</summary>
        private static void CheckSpacing()
        {
            var larger=G2AnchorCalculator.Calculate(new G2AnchorParameters {
                SubtypeKey="A",SpacingMm=120.0});
            Equal(larger.SpacingMm,120.0,"自定义间距");
            Equal(larger.PlateSideMm,220.0,"自定义间距下的锚板边长");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                SubtypeKey="A",SpacingMm=70.0}),"间距小于 MIN.S");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                SubtypeKey="A",SpacingMm=0.0}),"间距为零");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                SubtypeKey="C",SpacingMm=-20.0}),"间距为负数");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                SubtypeKey="Z"}),"未知子项");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                HeadingDegrees=double.NaN}),"非法朝向");
            Reject(()=>G2AnchorCalculator.Calculate(new G2AnchorParameters {
                MountFace=(G2MountFace)9}),"非法安装面");
        }

        /// <summary>三种安装面的局部坐标轴，与 Python _PlateFrame 的 axis_x / axis_y / axis_z 逐项对照。</summary>
        private static void CheckMountAxes()
        {
            double[] x,y,z;
            G2AnchorCalculator.Axes(G2MountFace.Wall,0.0,out x,out y,out z);
            Axis(x,1,0,0,"墙面 0° +X"); Axis(y,0,1,0,"墙面 0° +Y"); Axis(z,0,0,1,"墙面 0° +Z");
            G2AnchorCalculator.Axes(G2MountFace.Wall,90.0,out x,out y,out z);
            Axis(x,0,1,0,"墙面 90° +X"); Axis(y,-1,0,0,"墙面 90° +Y"); Axis(z,0,0,1,"墙面 90° +Z");
            G2AnchorCalculator.Axes(G2MountFace.FloorTop,0.0,out x,out y,out z);
            Axis(x,0,0,1,"楼板顶面 +X（朝世界 +Z）");
            Axis(y,1,0,0,"楼板顶面 +Y"); Axis(z,0,1,0,"楼板顶面 +Z");
            G2AnchorCalculator.Axes(G2MountFace.FloorTop,90.0,out x,out y,out z);
            Axis(x,0,0,1,"楼板顶面 90° +X"); Axis(y,0,1,0,"楼板顶面 90° +Y"); Axis(z,-1,0,0,"楼板顶面 90° +Z");
            G2AnchorCalculator.Axes(G2MountFace.CeilingBottom,0.0,out x,out y,out z);
            Axis(x,0,0,-1,"楼板底面 +X（朝世界 -Z）");
            Axis(y,1,0,0,"楼板底面 +Y"); Axis(z,0,-1,0,"楼板底面 +Z");
            // 三个轴必须两两正交且为单位向量。
            var mounts=new[]{G2MountFace.Wall,G2MountFace.FloorTop,G2MountFace.CeilingBottom};
            for(int i=0;i<mounts.Length;i++)
                foreach(double heading in new[]{0.0,37.0,90.0,-135.0})
                {
                    G2AnchorCalculator.Axes(mounts[i],heading,out x,out y,out z);
                    string label=mounts[i]+"@"+heading+"°";
                    Equal(Dot(x,x),1.0,label+" +X 单位长");
                    Equal(Dot(y,y),1.0,label+" +Y 单位长");
                    Equal(Dot(z,z),1.0,label+" +Z 单位长");
                    Equal(Dot(x,y),0.0,label+" X⊥Y");
                    Equal(Dot(x,z),0.0,label+" X⊥Z");
                    Equal(Dot(y,z),0.0,label+" Y⊥Z");
                    // 右手系：X × Y = Z。
                    double cx=y[1]*z[2]-y[2]*z[1],cy=y[2]*z[0]-y[0]*z[2],cz=y[0]*z[1]-y[1]*z[0];
                    Equal(cx,x[0],label+" X×Y=Z (x)");
                    Equal(cy,x[1],label+" X×Y=Z (y)");
                    Equal(cz,x[2],label+" X×Y=Z (z)");
                }
        }
        private static double Dot(double[] a,double[] b)
        { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
    }
}
