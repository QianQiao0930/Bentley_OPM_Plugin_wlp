using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    /// <summary>
    /// 放置管夹（A1 / A2 / A22 / A24 / E1 / K1 / T4 / L2）的纯计算检查。
    /// </summary>
    internal static class Program
    {
        private static void Equal(double a,double b,string label)
        { if(Math.Abs(a-b)>0.00001) throw new Exception(label+": "+a+" != "+b); }
        private static void Equal(int a,int b,string label)
        { if(a!=b) throw new Exception(label+": "+a+" != "+b); }
        private static void Equal(string a,string b,string label)
        { if(a!=b) throw new Exception(label+": \""+a+"\" != \""+b+"\""); }
        private static void Near(double a,double b,double tolerance,string label)
        { if(Math.Abs(a-b)>tolerance) throw new Exception(label+": "+a+" 与 "+b+" 相差超过 "+tolerance); }
        private static void Check(bool condition,string label)
        { if(!condition) throw new Exception(label); }
        private static void Reject(Action action,string label)
        { try { action(); } catch(InvalidOperationException) { return; } throw new Exception(label+" 应被拒绝。"); }

        private static void Main()
        {
            CheckCatalog();
            CheckA1();
            CheckA2();
            CheckA22();
            CheckA24();
            CheckK1();
            CheckT4();
            CheckL2();
            CheckL7();
            CheckL8();
            Console.WriteLine("放置管夹及 L7/L8 类型1/2：表数据、尺寸推导、坐标架与非法输入校验通过。");
        }

        private static void CheckL8()
        {
            var l7=L7GuideCalculator.Calculate(100,114.3,50,500,30,"P");
            var l8=L7GuideCalculator.Calculate(ColdRiserGuideSeries.L8,L7GuideKind.Type1,
                100,114.3,50,500,30,"P",300,"S");
            Equal(l8.MemberLengthMm,l7.MemberLengthMm,"L8 类型1复用长度");
            Equal(l8.MemberProfile,l7.MemberProfile,"L8 类型1复用截面");
            Equal(l8.Clamp.A,l7.Clamp.A,"L8 类型1复用 A22");
            Check(l8.Connection==null,"L8 类型1不带 N8");
            Equal(l8.Number,"L8-1-DN100-50-300-S-500","L8 编号字段顺序");
            var p=L7GuideCalculator.Calculate(ColdRiserGuideSeries.L8,L7GuideKind.Type2,
                100,114.3,50,500,30,"P",450,"C1");
            Equal(p.Clamp.Code,"A22","L8 类型2使用 A22");
            Equal(p.MemberProfile,"12.6","L8 类型2槽钢");
            Equal(p.Connection.Type,1,"L8 N8 类型1");
            Equal(p.MemberStartMm+p.MemberLengthMm+p.Connection.T,p.LengthMm,"L8 端板与构件末端贴合");
            Equal(p.Connection.BoltCount,4,"N8 四套螺栓");
            Equal(p.Number,"L8-2-DN100-50-450-C1-500","L8 类型2编号");
            Equal(L7GuideCatalog.CellName(p),"L8_COLD_RISER_GUIDE_TYPE2","L8 单元名");
            foreach(int dn in L7GuideCatalog.Dns)Check(L7GuideCatalog.AllowableLoad(dn)>0,"荷载表");
            Equal(L7GuideCatalog.AllowableLoad(15),0.4,"DN15 荷载");
            Equal(L7GuideCatalog.AllowableLoad(150),7.5,"DN150 荷载");
            Equal(L7GuideCatalog.AxialTravel(300).Value,30,"300 位移");
            Equal(L7GuideCatalog.AxialTravel(450).Value,100,"450 位移");
            Equal(L7GuideCatalog.AxialTravel(600).Value,180,"600 位移");
            Check(!L7GuideCatalog.AxialTravel(400).HasValue,"不外推位移");
            string f,s,label;
            foreach(double d in new[]{100.0,100.01,450,450.01,700}) {
                int type=L7GuideCatalog.EquipmentMember(d,out f,out s,out label);
                Equal(type,d<=450?1:2,"N8 分段边界");
                Check(ProfileLookup.Mode(RuntimeData.Families,f,s,"geometric_center")!=null,"型钢目录规格存在");
            }
            Reject(()=>L7GuideCatalog.EquipmentMember(701,out f,out s,out label),"L8 A 超限");
            Reject(()=>L7GuideCatalog.Material("X"),"非法材料");
            Reject(()=>L7GuideCatalog.AllowableLoad(32),"非标准 DN");
            Reject(()=>L7GuideCalculator.Calculate(ColdRiserGuideSeries.L8,L7GuideKind.Type2,
                100,114.3,50,double.NaN,0,"",300,"C1"),"L8 无效 L1");
        }

        private static void CheckL7()
        {
            var small=L7GuideCalculator.Calculate(15,21.3,50,50,370,"P-1");
            Equal(small.LengthMm,300,"L7 最小 L");
            Equal(small.MemberStartMm+small.MemberLengthMm,300,"L7 管心至末端");
            Equal(small.AngleDeg,10,"L7 角度归一化");
            Equal(small.MemberLabel,"H100×100×6×8","L7 按保冷后 A 选构件 A");
            Equal(small.BearingLengthMm,300,"L7 承重夹板默认长度");
            Equal(small.BearingBoolean.EarCenterXmm.Length,2,"L7 夹板两组耳板");
            Equal(small.Bearing.BoltCount,4,"L7 承重夹板 4 套螺栓");
            Check(small.PipeNumber=="P-1","L7 管道号");
            Equal(L7GuideCalculator.Calculate(15,21.3,25,300,0,"").MemberLabel,
                "∠75×7","L7 A≤100 角钢实选");
            var large=L7GuideCalculator.Calculate(150,168.3,100,1500,0,"");
            Equal(large.LengthMm,1000,"L7 大于 1 m 钳位");
            Equal(large.MemberStartMm+large.MemberLengthMm,1000,"L7 上限从管心计");
            Check(large.MemberLabel=="H100×100×6×8"||
                large.MemberLabel=="H125×125×6.5×9","L7 型钢表选型");
            Reject(()=>L7GuideCalculator.Calculate(200,219.1,50,300,0,""),"L7 超出 DN150");
            Reject(()=>L7GuideCalculator.Calculate(15,21.3,50,300,0,"",200),
                "L7 夹板长度小于 300");
            string family,profile,label;
            L7GuideCatalog.Member(100,out family,out profile,out label);
            Equal(profile,"L75x75x7","L7 A=100 边界");
            L7GuideCatalog.Member(450,out family,out profile,out label);
            Equal(profile,"H100x100x6x8xr8","L7 A=450 边界");
            L7GuideCatalog.Member(700,out family,out profile,out label);
            Equal(profile,"H125x125x6.5x9xr8","L7 A=700 边界");
            Reject(()=>L7GuideCatalog.Member(701,out family,out profile,out label),
                "L7 A>700");
            var type2=L7GuideCalculator.Calculate(L7GuideKind.Type2,100,114.3,50,
                double.NaN,90,"P-2",300);
            Equal(type2.Clamp.Code,"A24","L7 类型2 中心四螺栓管夹");
            Equal(type2.Clamp.BoltCentersYmm.Length,4,"L7 类型2 A24 螺栓数量");
            Equal(type2.MemberLengthMm,0,"L7 类型2 无构件 A");
            Equal(type2.BearingLengthMm,300,"L7 类型2 默认夹板长度");
            Check(type2.Number.StartsWith("L7-2-DN100-",StringComparison.Ordinal),
                "L7 类型2 编号");
            Equal(L7GuideCatalog.CellName(L7GuideKind.Type2),
                "L7_COLD_RISER_GUIDE_TYPE2","L7 类型2 单元名");
        }

        /// <summary>管夹的清单属性契约（中文类型名 + ASCII 代号）。</summary>
        private static void CheckCatalog()
        {
            var types=PipeClampCatalog.All;
            Equal(types.Length,8,"管夹类型数量");
            string[] codes={"A2","E1","K1","T4","A1","A22","A24","L2"};
            for(int i=0;i<types.Length;i++)
            {
                Equal(types[i].Code,codes[i],codes[i]+" 编号前缀");
                Check(types[i].SupportType.IndexOf('[')>=0,codes[i]+" 的 SupportType 应为中文类型名");
                Check(types[i].SupportCode.IndexOf('[')<0,codes[i]+" 的 SupportCode 应为 ASCII 代号");
                Check(types[i].CellName.Length>0,codes[i]+" 组合单元名");
            }
            for(int i=0;i<types.Length;i++)
                for(int j=i+1;j<types.Length;j++)
                    Check(types[i].SupportCode!=types[j].SupportCode,"管夹 SupportCode 重复");
        }

        private static void CheckA1()
        {
            Equal(A1ClampCatalog.All.Length,27,"A1 表 1 行数");
            foreach(var row in A1ClampCatalog.All)
            {Equal(row.C,row.B+row.Bolt,"A1 DN"+row.Dn+" C=B+d");
                Check(row.E<row.D,"A1 E 列只作参考且小于 D");
                Check(row.B>row.OutsideMm,"A1 弯弧与管道留净空");}
            var plan=A1ClampCalculator.Calculate(50,true,100,0,"P-1");
            Equal(plan.Row.Dn,100,"A1 自动匹配 DN100");
            Equal(plan.Row.C,132,"A1 DN100 两腿中心距");
            Near(plan.NutCenterMm,86.075,.001,"A1 螺母中心");
            Near(plan.NutLow1Mm,76.475,.001,"A1 第一螺母底");
            Equal(plan.AssemblyTag,"A1-DN100-M12-0°","A1 编号");
            Check(plan.PipeNumber=="P-1","A1 管道号");
            Equal(A1ClampCalculator.Calculate(50,false,100,370,"").Row.Dn,50,
                "普通辅助线使用面板 DN");
            Near(A1ClampCalculator.AngleFromCursor(new[]{1.0,0.0,0.0},
                new[]{0.0,0.0,1.0}),0,.001,"水平管朝上角度");
            Near(A1ClampCalculator.AngleFromCursor(new[]{1.0,0.0,0.0},
                new[]{0.0,-1.0,0.0}),90,.001,"水平管绕轴 90 度");
            Near(A1ClampCalculator.AngleFromCursor(new[]{0.0,0.0,1.0},
                new[]{1.0,0.0,0.0}),0,.001,"竖直管朝 +X");
            Reject(()=>A1ClampCatalog.Require(1200),"A1 表外 DN");
            CheckA1RadialFrame();
            CheckA1CompassFrame();
        }

        /// <summary>
        /// 精确绘图罗盘用的径向正交基：必须单位长、两两正交、右手系，
        /// 且 Z 轴=管轴（罗盘平面法向落在管道径向平面内不能靠猜）。
        /// </summary>
        private static void CheckA1RadialFrame()
        {
            var axes=new[]{new[]{1.0,0.0,0.0},new[]{0.0,1.0,0.0},new[]{0.0,0.0,1.0},
                new[]{1.0,2.0,3.0},new[]{-4.0,0.5,0.25},new[]{0.0,0.0,-2.5}};
            foreach(var axis in axes)
            {
                double[] x,y,z;
                A1ClampCalculator.RadialFrame(axis,out x,out y,out z);
                string tag="管轴("+axis[0]+","+axis[1]+","+axis[2]+")";
                Near(Norm(x),1,.001,tag+" X 轴单位长");
                Near(Norm(y),1,.001,tag+" Y 轴单位长");
                Near(Norm(z),1,.001,tag+" Z 轴单位长");
                Near(Dot(x,y),0,.001,tag+" X⊥Y");
                Near(Dot(x,z),0,.001,tag+" X⊥Z");
                Near(Dot(y,z),0,.001,tag+" Y⊥Z");
                Near(Cross(x,y)[0],z[0],.001,tag+" 右手系 X×Y=Z (x)");
                Near(Cross(x,y)[1],z[1],.001,tag+" 右手系 X×Y=Z (y)");
                Near(Cross(x,y)[2],z[2],.001,tag+" 右手系 X×Y=Z (z)");
                // Z 轴必须与管轴同向（缩放后比较）
                double axisLength=Norm(axis);
                Near(z[0],axis[0]/axisLength,.001,tag+" Z 轴=管轴 (x)");
                Near(z[1],axis[1]/axisLength,.001,tag+" Z 轴=管轴 (y)");
                Near(z[2],axis[2]/axisLength,.001,tag+" Z 轴=管轴 (z)");
                // X 轴上的向量角度必须是 0°，Y 轴上是 90°（罗盘读数=开口角）
                Near(A1ClampCalculator.AngleFromCursor(axis,x),0,.001,tag+" X 轴=0°");
                Near(A1ClampCalculator.AngleFromCursor(axis,y),90,.001,tag+" Y 轴=90°");
            }
            Reject(()=>{double[] x,y,z;A1ClampCalculator.RadialFrame(
                new[]{0.0,0.0,0.0},out x,out y,out z);},"零管轴");
        }

        /// <summary>
        /// 罗盘法线沿管轴，平面与管轴垂直；保持开口角基准不变。
        /// </summary>
        private static void CheckA1CompassFrame()
        {
            var axes=new[]{new[]{1.0,0.0,0.0},new[]{0.0,1.0,0.0},new[]{0.0,0.0,1.0},
                new[]{1.0,2.0,3.0},new[]{-4.0,0.5,0.25},new[]{0.0,0.0,-2.5}};
            foreach(var axis in axes)
            {
                double[] x,y,z;
                A1ClampCalculator.CompassFrame(axis,out x,out y,out z);
                string tag="管轴("+axis[0]+","+axis[1]+","+axis[2]+")";
                Near(Norm(x),1,.001,tag+" 罗盘 X 单位长");
                Near(Norm(y),1,.001,tag+" 罗盘 Y 单位长");
                Near(Norm(z),1,.001,tag+" 罗盘 Z 单位长");
                Near(Dot(x,y),0,.001,tag+" 罗盘 X⊥Y");
                Near(Dot(x,z),0,.001,tag+" 罗盘 X⊥Z");
                Near(Dot(y,z),0,.001,tag+" 罗盘 Y⊥Z");
                Near(Cross(x,y)[0],z[0],.001,tag+" 罗盘右手系 X×Y=Z (x)");
                Near(Cross(x,y)[1],z[1],.001,tag+" 罗盘右手系 X×Y=Z (y)");
                Near(Cross(x,y)[2],z[2],.001,tag+" 罗盘右手系 X×Y=Z (z)");
                double axisLength=Norm(axis);
                Near(z[0],axis[0]/axisLength,.001,tag+" 罗盘法线沿管轴 x");
                Near(z[1],axis[1]/axisLength,.001,tag+" 罗盘法线沿管轴 y");
                Near(z[2],axis[2]/axisLength,.001,tag+" 罗盘法线沿管轴 z");
                Near(Dot(axis,x),0,.001,tag+" 管轴垂直罗盘X");
                Near(Dot(axis,y),0,.001,tag+" 管轴垂直罗盘Y");
                Near(A1ClampCalculator.AngleFromCursor(axis,x),0,.001,tag+" 罗盘 X=0°");
                Near(A1ClampCalculator.AngleFromCursor(axis,y),90,.001,tag+" 罗盘 Y=90°");
            }
            Reject(()=>{double[] x,y,z;A1ClampCalculator.CompassFrame(
                new[]{0.0,0.0,0.0},out x,out y,out z);},"罗盘基零管轴");
        }
        private static double Norm(double[] v)
        { return Math.Sqrt(Dot(v,v)); }
        private static double Dot(double[] a,double[] b)
        { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
        private static double[] Cross(double[] a,double[] b)
        { return new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]}; }

        private static void CheckA2()
        {
            Equal(A2ClampCatalog.All.Length,24,"A2 表 1 行数");
            var row=A2ClampCatalog.Require(100);
            Equal(row.Nps,"4\"","DN100 的 NPS");
            Equal(row.A,117,"DN100 内孔 A");
            Equal(row.B,84,"DN100 孔心距 B");
            Equal(row.C,20,"DN100 板宽 C");
            Equal(row.D,50,"DN100 端距 D");
            Equal(row.PlateThickness,8,"DN100 板厚 t");
            Equal(row.Width,50,"DN100 板宽 w");
            Equal(row.BoltDiameterMm,16,"DN100 螺栓");

            var plan=A2ClampCalculator.Calculate(100,0.0);
            Equal(plan.CylinderDiameterMm,133,"圆柱外径 A+2t");
            Equal(plan.BoxLengthMm,233,"长方体长 A+2D+2t");
            Equal(plan.BoxWidthMm,36,"长方体宽 C+2t");
            Equal(plan.HoleRadiusMm,9,"螺栓孔半径 (16+2)/2");
            Equal(plan.AssemblyTag,"DN100","编号");
            Equal(plan.BoltCount,2,"螺栓套数");
            Equal(plan.BodySpecification,"DN100（4\"，A=117，C=20，t=8，w=50）","整组规格");

            // 保温：内孔 A+2B，孔心距 B+保温厚度（半径向同步外移）。
            var insulated=A2ClampCalculator.Calculate(100,50.0);
            Equal(insulated.InnerDiameterMm,217,"保温后内孔 A+2×50");
            Equal(insulated.BoltCenterMm,134,"保温后孔心距 B+50");
            Equal(insulated.CylinderDiameterMm,233,"保温后圆柱外径");

            // 点选管道时按公称直径匹配表 1；匹配不上或直线则用面板兜底管径。
            // 注意 A2 的表 1 只比公称直径数值（与脚本 _match_table_dn 一致），不比外径。
            var byPipe=A2ClampCalculator.Calculate(new A2ClampParameters {FallbackDn=50},
                true,100.0,20.0);
            Equal(byPipe.Dn,100,"按管道公称直径匹配");
            Equal(byPipe.InsulationMm,20.0,"按管道保温厚度");
            var byLine=A2ClampCalculator.Calculate(new A2ClampParameters {FallbackDn=150},
                false,114.3,20.0);
            Equal(byLine.Dn,150,"按直线时用面板兜底管径");
            var unmatched=A2ClampCalculator.Calculate(new A2ClampParameters {FallbackDn=150},
                true,900.0,0.0);
            Equal(unmatched.Dn,150,"公称直径匹配不上时用兜底管径");

            var match=A2ClampCatalog.MatchDn(120.0);
            Equal(match.HasValue?match.Value:0,125,"公称直径 120 匹配到 125");
            Check(!A2ClampCatalog.MatchDn(5000.0).HasValue,"超大公称直径匹配不上");

            Reject(()=>A2ClampCatalog.Require(800),"表 1 之外的管径");
            Reject(()=>A2ClampCalculator.Calculate(100,-5.0),"负保温厚度");
        }

        private static void CheckA22()
        {
            Equal(A22ClampCatalog.All.Length,13,"A22 表 1 行数");
            Equal(A22ClampCatalog.ForA(100).BoltDiameterMm,12,"A=100 表 1 首档");
            Equal(A22ClampCatalog.ForA(100.1).W,75.0,"A 超过 100 进入下一档");
            Equal(A22ClampCatalog.ForA(1400).AllowableLoadKn,72.0,"A=1400 表 1 末档");
            Reject(()=>A22ClampCatalog.ForA(1400.1),"A 超过表 1 上限");
            foreach(var sample in new[]{
                new[]{100.0,6.0},new[]{225.0,10.0},new[]{400.0,12.0},
                new[]{700.0,40.0},new[]{900.0,62.5}})
            {
                double a=sample[0],expectedR=sample[1];
                var rounded=A22ClampCalculator.Calculate(100,a-22.0,0.0,"A22");
                Near(rounded.RMinMm,expectedR,0.0001,"A22 过渡圆角 R_MIN A="+a);
                double centerDistance=Math.Sqrt(rounded.TransitionEndYmm*
                    rounded.TransitionEndYmm+Math.Pow(rounded.C+rounded.RMinMm,2));
                Near(centerDistance,rounded.OuterRadiusMm+rounded.RMinMm,0.0001,
                    "A22 圆角与承重环外圆相切 A="+a);
                Near(Math.Sqrt(rounded.TransitionTangentYmm*rounded.TransitionTangentYmm+
                    rounded.TransitionTangentZmm*rounded.TransitionTangentZmm),
                    rounded.OuterRadiusMm,0.0001,"A22 圆弧切点在外圆上 A="+a);
                Check(rounded.TransitionEndYmm<rounded.FlangeEndMm,
                    "A22 圆角在法兰端部以内 A="+a);
            }
            foreach(int dn in E1GuideCatalog.Dns)
            {
                double expected=dn<=100?6.0:dn<=150?8.0:dn<=400?10.0:12.0;
                Equal(A22ClampCatalog.BearingPlateThickness(dn),expected,
                    "A22 表 2 DN"+dn);
                var selected=A22ClampCalculator.Calculate(dn,E1GuideCatalog.Outside(dn),
                    50.0,"A22");
                Check(selected.B-selected.G/2.0>selected.FlangeRootMm,
                    "A22 螺栓孔不能碰到承重环 DN"+dn);
                Check(selected.B+selected.G/2.0<selected.FlangeEndMm,
                    "A22 螺栓孔不能越过法兰端部 DN"+dn);
            }
            Equal(A22ClampCatalog.MatchDn(100).Value,100,"A22 按公称 DN 匹配");
            var plan=A22ClampCalculator.Calculate(100,114.3,20.0,"A22");
            Near(plan.A,176.3,0.0001,"A=OD+2×(承重板厚+保冷厚)+10");
            Near(plan.B,113.15,0.0001,"B=0.5A+E");
            Equal(plan.C,30.0,"A22 表 1 C");
            Equal(plan.E,25.0,"A22 表 1 E");
            Equal(plan.T,6.0,"A22 表 1 T");
            Equal(plan.W,75.0,"A22 表 1 W");
            Equal(plan.G,19.0,"G=M16+3");
            Equal(plan.Number,"A22-DN100-20","A22 编号");
            var fromPipe=A22ClampCalculator.Calculate(new A22ClampParameters {
                FallbackDn=50,FallbackColdThicknessMm=10.0},true,100,120,30);
            Equal(fromPipe.Dn,100,"管道 EC 公称直径覆盖面板 DN");
            Equal(fromPipe.PipeOutsideMm,120.0,"管道 EC 外径覆盖表外径");
            Equal(fromPipe.ColdThicknessMm,30.0,"管道 EC 保冷厚度覆盖面板");
            var fromLine=A22ClampCalculator.Calculate(new A22ClampParameters {
                FallbackDn=50,FallbackColdThicknessMm=10.0},false,100,120,30);
            Equal(fromLine.Dn,50,"普通直线使用面板 DN");
            Equal(fromLine.PipeOutsideMm,E1GuideCatalog.Outside(50),"普通直线使用表外径");
            Equal(fromLine.ColdThicknessMm,10.0,"普通直线使用面板保冷厚度");
            Reject(()=>A22ClampCalculator.Calculate(100,114.3,-1,"A22"),"保冷厚度不可为负");
        }

        private static void CheckA24()
        {
            double[] limits={100,150,200,225,250,350,400,450,550,700,900,1050,1400};
            double[] fValues={100,100,100,100,100,100,100,120,145,145,170,195,225};
            for(int i=0;i<limits.Length;i++)
                Equal(A24ClampCatalog.FForA(limits[i]),fValues[i],"A24 F 分档 A="+limits[i]);
            Reject(()=>A24ClampCatalog.FForA(1400.1),"A24 A 超出上限");
            var a22=A22ClampCalculator.Calculate(100,114.3,20,"A22");
            var a24=A22ClampCalculator.Calculate(100,114.3,20,"A24",true);
            Equal(a24.Code,"A24","A24 类别");
            Equal(a24.F,100,"A24 A=176.3 的孔距");
            Equal(a24.B,a22.B,"A24 沿用 A22 的内侧孔位");
            Equal(a24.FlangeEndMm-a22.FlangeEndMm,a24.F,"A24 单侧增加 F");
            Equal(a24.BoltCentersYmm.Length,4,"A24 四套紧固件");
            Equal(a24.BoltCentersYmm[0],-a24.B-a24.F,"A24 左外孔");
            Equal(a24.BoltCentersYmm[1],-a24.B,"A24 左内孔");
            Equal(a24.BoltCentersYmm[2],a24.B,"A24 右内孔");
            Equal(a24.BoltCentersYmm[3],a24.B+a24.F,"A24 右外孔");
            Equal(a24.RMinMm,a22.RMinMm,"A24 沿用 A22 圆角");
            Check(a24.Specification.Contains("F=100"),"A24 规格应写入 F");
            Check(!a24.Specification.Contains("kN"),"A24 原表未给允许荷载");
            Equal(a24.Number,"A24-DN100-20","A24 编号");
            foreach(int dn in E1GuideCatalog.Dns)
            {
                var plan=A22ClampCalculator.Calculate(dn,E1GuideCatalog.Outside(dn),50,"A24",true);
                Check(plan.BoltCentersYmm[3]+plan.G/2.0<plan.FlangeEndMm,
                    "A24 外侧孔不得越过法兰端 DN"+dn);
            }
        }

        private static void CheckK1()
        {
            Equal(K1LimitCatalog.All.Length,3,"K1 子项数量");
            Equal(K1LimitCatalog.Od(100),114.3,"DN100 外径");
            Equal(K1LimitCatalog.Od(900),914.4,"DN900 外径");
            Equal(K1LimitCatalog.SubitemForDn(50),"A","DN50 子项");
            Equal(K1LimitCatalog.SubitemForDn(100),"B","DN100 子项");
            Equal(K1LimitCatalog.SubitemForDn(250),"B","DN250 子项");
            Equal(K1LimitCatalog.SubitemForDn(400),"C","DN400 子项");
            Equal(K1LimitCatalog.BuildNumber("A",50),"K1-A","子项 A 编号省略管径");
            Equal(K1LimitCatalog.BuildNumber("B",150),"K1-B-150","子项 B 编号");
            var matched=K1LimitCatalog.MatchDn(114.3);
            Equal(matched.HasValue?matched.Value:0,100,"按外径匹配 DN");
            Reject(()=>K1LimitCatalog.Od(1200),"DN/外径表之外的管径");

            // 法兰座：子项 A 无底板，接触高差 = OD/2。
            var halfT=K1LimitCatalog.Require("A");
            double contact,gap;
            K1LimitCalculator.FlangeSeat(halfT,60.3,out contact,out gap);
            Equal(contact,30.15,"子项 A 接触高差 OD/2");
            Equal(gap,0.0,"子项 A 无底板无间距");

            // 子项 B：H100×100×6×8，净距 b = 100−2×8 = 84。
            // contact = sqrt(57.15² − 42²) = 38.75722513；hTri = sqrt(114.3² − 42²) = 106.30376287，
            // gap = 2×(114.3 − hTri) = 15.99247426。
            var hbeam=K1LimitCatalog.Require("B");
            K1LimitCalculator.FlangeSeat(hbeam,114.3,out contact,out gap);
            Near(contact,38.75722513,0.0000001,"子项 B 接触高差 sqrt(57.15²−42²)");
            Near(gap,15.99247426,0.0000001,"子项 B 钢板顶面与翼缘端面间距");
            Reject(()=>{ double c,g; K1LimitCalculator.FlangeSeat(hbeam,60.3,out c,out g); },
                "OD 小于两翼缘净距时应被拒绝");

            // 水平坐标架：pipeDir 水平、pipeDir × perp = +Z，超过 5° 拒绝。
            double[] pipeDir,perp;
            K1LimitCalculator.HorizontalFrame(1,0,0,out pipeDir,out perp);
            Equal(pipeDir[0],1.0,"管轴 X"); Equal(pipeDir[2],0.0,"管轴水平");
            Equal(perp[0],0.0,"perp X"); Equal(perp[1],1.0,"perp Y");
            K1LimitCalculator.HorizontalFrame(1.0,0.0,Math.Tan(3.0*Math.PI/180.0),
                out pipeDir,out perp);
            Equal(pipeDir[2],0.0,"微倾管轴取水平投影");
            Near(pipeDir[0],1.0,0.000001,"微倾管轴归一化");
            Reject(()=>K1LimitCalculator.HorizontalFrame(1,0,0.3,out pipeDir,out perp),
                "与水平面夹角超过 5° 的管道");
            Reject(()=>K1LimitCalculator.HorizontalFrame(0,0,1,out pipeDir,out perp),
                "竖直管道");

            var center=new[]{0.0,0.0,1000.0};
            var pipe=new[]{1.0,0.0,0.0};
            // 子项 A：竖直立柱，截面在水平面，沿 +Z 拉伸 height。
            double[] origin,ax,ay,az;double length;
            K1LimitCalculator.MemberFrame(halfT,1,center,100.0,60.3,pipe,
                out origin,out ax,out ay,out az,out length);
            Equal(origin[0],50.0,"子项 A 内侧面沿管轴 50");
            Near(origin[2],1000.0-30.15-100.0,0.0001,"子项 A 底面标高 = 管底 − 柱高");
            Equal(ax[0],1.0,"子项 A 截面 X 沿管轴");
            Equal(az[2],1.0,"子项 A 沿竖直拉伸");
            Equal(length,100.0,"子项 A 立柱高");

            // 子项 B：H 型钢水平，截面在竖直面，沿管轴拉伸 length。
            K1LimitCalculator.MemberFrame(hbeam,1,center,100.0,114.3,pipe,
                out origin,out ax,out ay,out az,out length);
            Equal(origin[0],60.0,"子项 B 型钢内端 = W/2 + 板厚");
            Near(origin[2],911.242775,0.0001,"子项 B 截面中心标高 = 管轴 − contact − B/2");
            Equal(ax[2],-1.0,"子项 B 截面 X 朝竖直向下");
            Equal(az[0],1.0,"子项 B 沿管轴拉伸");
            Equal(length,150.0,"子项 B 型钢沿管轴长");

            var reflected=new[]{-1.0,0.0,0.0};
            double[] origin2,ax2,ay2,az2;double length2;
            K1LimitCalculator.MemberFrame(hbeam,-1,center,100.0,114.3,pipe,
                out origin2,out ax2,out ay2,out az2,out length2);
            Equal(origin2[0],-60.0,"子项 B 另一侧镜像");
            Equal(ax2[2],1.0,"子项 B 另一侧截面 X 朝竖直向上");
            Equal(az2[0],-1.0,"子项 B 另一侧沿管轴反向");
            Equal(reflected[0],-1.0,"镜像侧符号");

            // 底板：焊在型钢朝已有钢构那一端的截面上，顶面低于翼缘端面 gap。
            var box=K1LimitCalculator.PlateBox(hbeam,1,center,100.0,114.3,pipe);
            Check(box!=null,"子项 B 应有底板");
            Equal(box[0],50.0,"底板 u0"); Equal(box[1],60.0,"底板 u1（厚 10）");
            Equal(box[2],-75.0,"底板 v0"); Equal(box[3],75.0,"底板 v1");
            Near(box[5],945.2503006,0.0000001,"底板顶面标高 = 翼缘端面 − 间距");
            Near(box[4],795.2503006,0.0000001,"底板底面标高");
            Check(K1LimitCalculator.PlateBox(K1LimitCatalog.Require("A"),1,center,100.0,60.3,
                pipe)==null,"子项 A 无底板");

            var plan=K1LimitCalculator.Calculate(new K1LimitParameters {Dn=100},false,null);
            Equal(plan.SubitemKey,"B","按 DN 自动选子项");
            Equal(plan.Number,"K1-B-100","编号");
            Equal(plan.Plate[0],150.0,"底板边长");
            var byPipe=K1LimitCalculator.Calculate(new K1LimitParameters {Dn=50},true,168.3);
            Equal(byPipe.Dn,150,"点选管道时按其 DN 重算");
            Equal(byPipe.SubitemKey,"B","管道 DN150 对应子项 B");
            Reject(()=>K1LimitCalculator.Calculate(100,"B",0.0,"Q235B"),"已有钢构宽度为零");
        }

        private static void CheckL2()
        {
            Equal(L2ShoeCatalog.All.Length,18,"L2 表 1 行数");
            Equal(L2ShoeCatalog.HeightForCold(25),100,"L2 B=25 H=100");
            Equal(L2ShoeCatalog.HeightForCold(26),150,"L2 B=26 H=150");
            Equal(L2ShoeCatalog.HeightForCold(75),150,"L2 B=75 H=150");
            Equal(L2ShoeCatalog.HeightForCold(76),200,"L2 B=76 H=200");
            Equal(L2ShoeCatalog.HeightForCold(275),350,"L2 B=275 H=350");
            Reject(()=>L2ShoeCatalog.HeightForCold(276),"L2 保冷厚度超过表 2");
            Reject(()=>L2ShoeCatalog.Require(650),"L2 本阶段 DN 上限");
            foreach(var row in L2ShoeCatalog.All)
            {
                Equal(row.LengthMm,2*row.EndEMm+row.SpacingFMm,
                    "L2 L=2E+F DN"+row.Dn);
                var layout=L2ShoeCalculator.BuildLayout(new L2ShoeParameters {
                    Dn=row.Dn,ColdMm=50,FCode="A"},false,null,null);
                var bl=T4ShoeCalculator.BuildBooleanLayout(layout);
                Equal(layout.Code,"L2","L2 布局类别");
                Equal(layout.HeightMm,150,"L2 B=50 查 H");
                Equal(layout.ShoeLengthMm,row.LengthMm,"L2 最小长度 DN"+row.Dn);
                Equal(layout.T1Mm,row.T1Mm,"L2 T1 DN"+row.Dn);
                Equal(layout.T2Mm,row.T2Mm,"L2 T2 DN"+row.Dn);
                Equal(layout.T3Mm,row.T3Mm,"L2 T3 DN"+row.Dn);
                Equal(layout.Bolt,row.Bolt,"L2 螺栓 DN"+row.Dn);
                Equal(bl.EarCenterXmm.Length,2,"L2 两组耳板 DN"+row.Dn);
                Equal(bl.EarCenterXmm[1]-bl.EarCenterXmm[0],row.SpacingFMm,
                    "L2 螺栓组中心距 F DN"+row.Dn);
                Equal(bl.SupportCenterXmm.Length,row.Dn<=50?0:2,
                    "L2 简式 / 横向支撑 DN"+row.Dn);
                Equal(layout.Number,"L2-DN"+row.Dn+"-50-A","L2 编号 DN"+row.Dn);
                var items=T4ShoeCalculator.ComponentItems(layout,bl,false,false);
                Check(Array.Exists(items,x=>x[0]=="Bolt"&&x[4]=="4"),
                    "L2 应有四套螺栓 DN"+row.Dn);
                foreach(double cold in new[]{25.0,75.0,125.0,175.0,225.0,275.0})
                {
                    try { T4ShoeCalculator.BuildBooleanLayout(L2ShoeCalculator.BuildLayout(
                        new L2ShoeParameters {Dn=row.Dn,ColdMm=cold},false,null,null)); }
                    catch(Exception ex) { throw new Exception("L2 DN"+row.Dn+" B="+cold+"："+
                        ex.Message,ex); }
                }
            }
            var pipe=L2ShoeCalculator.BuildLayout(new L2ShoeParameters {Dn=50,ColdMm=25},
                true,200,75);
            Equal(pipe.Dn,200,"L2 管道 DN 覆盖面板");
            Equal(pipe.InsulationMm,75,"L2 管道保冷厚度覆盖面板");
            Equal(pipe.HeightMm,150,"L2 管道 B=75 H=150");
            var line=L2ShoeCalculator.BuildLayout(new L2ShoeParameters {Dn=50,ColdMm=25},
                false,200,75);
            Equal(line.Dn,50,"L2 普通直线使用面板 DN");
            Equal(line.HeightMm,100,"L2 B=25 H=100");
        }

        private static void CheckT4()
        {
            Equal(T4ShoeCatalog.All.Length,18,"T4 表 1 行数");
            int[] smallDns={15,20,25,40,50};
            double[] smallOds={21.3,26.7,33.4,48.3,60.3};
            for(int i=0;i<smallDns.Length;i++)
            {
                var small=T4ShoeCatalog.Require(smallDns[i]);
                Equal(small.OutsideMm,smallOds[i],"小管径外径 DN"+smallDns[i]);
                Equal(small.Bolt,"M12","小管径螺栓 DN"+smallDns[i]);
                Equal(small.EarWidthMm,40.0,"小管径耳板宽 DN"+smallDns[i]);
                Equal(small.EarHeightMm,40.0,"小管径耳板高 DN"+smallDns[i]);
                Equal(small.EarThicknessMm,12.0,"小管径耳板厚 DN"+smallDns[i]);
                Equal(small.T1Mm,8.0,"小管径 T1 DN"+smallDns[i]);
                Equal(small.T2Mm,8.0,"小管径 T2 DN"+smallDns[i]);
                Equal(small.T3Mm,6.0,"小管径 T3 DN"+smallDns[i]);
                Equal(small.VerticalLoadKn,i<3?10.0:30.0,"小管径垂直荷载 DN"+smallDns[i]);
                Equal(small.LateralLoadKn,i<3?2.0:6.0,"小管径横向荷载 DN"+smallDns[i]);
                Equal(small.AxialLoadKn,i<3?5.0:10.0,"小管径轴向荷载 DN"+smallDns[i]);
                Check(T4ShoeCatalog.UsesSimpleBase(smallDns[i]),"DN50 及以下用简式底座");
            }
            foreach(int dn in new[]{80,100})
            {
                var checkedRow=T4ShoeCatalog.Require(dn);
                Equal(checkedRow.Bolt,"M12","表图螺栓 DN"+dn);
                Equal(checkedRow.T1Mm,10.0,"表图 T1 DN"+dn);
                Equal(checkedRow.T2Mm,8.0,"表图 T2 DN"+dn);
                Equal(checkedRow.T3Mm,6.0,"表图 T3 DN"+dn);
                Equal(checkedRow.VerticalLoadKn,40.0,"表图垂直荷载 DN"+dn);
                Equal(checkedRow.LateralLoadKn,8.0,"表图横向荷载 DN"+dn);
                Equal(checkedRow.AxialLoadKn,30.0,"表图轴向荷载 DN"+dn);
                Check(!T4ShoeCatalog.UsesSimpleBase(dn),"DN80 及以上保留横向支撑");
            }
            var row=T4ShoeCatalog.Require(200);
            Equal(row.Nps,"8\"","DN200 NPS");
            Equal(row.OutsideMm,219.1,"DN200 外径");
            Equal(row.Bolt,"M20","DN200 螺栓");
            Equal(row.EarWidthMm,60.0,"DN200 耳板宽");
            Equal(row.T1Mm,12.0,"DN200 底板厚");
            Equal(row.T3Mm,12.0,"DN200 承重板厚");
            Equal(row.PlateGapJMm,30.0,"DN200 承重板间隙 J");
            Equal(T4ShoeCatalog.BoltCount(200),4,"DN15~600 表中为 4 颗螺栓");
            Equal(T4ShoeCatalog.BoltDiameterMm(200),20.0,"M20 直径");
            Reject(()=>T4ShoeCatalog.Require(700),"表 1 之外的管径");

            // 公称直径匹配（只比 DN 数值，容差 max(5, 15%)）。
            var matched200=T4ShoeCatalog.MatchDn(200.0);
            Equal(matched200.HasValue?matched200.Value:0,200,"公称直径 200 → DN200");
            var matched210=T4ShoeCatalog.MatchDn(210.0);
            Equal(matched210.HasValue?matched210.Value:0,200,"公称直径 210 → DN200");
            Check(!T4ShoeCatalog.MatchDn(null).HasValue,"无公称直径时匹配不上");
            Check(!T4ShoeCatalog.MatchDn(2000.0).HasValue,"超大公称直径匹配不上");

            // 点选管道时按管道信息覆盖 DN 与保温厚度，读不到才回落到面板值。
            var fromPipe=T4ShoeCalculator.BuildLayout(
                new T4ShoeParameters {Dn=200,InsulationMm=50.0,LengthMm=300.0},
                true,300.0,80.0);
            Equal(fromPipe.Dn,300,"按管道公称直径覆盖 DN");
            Equal(fromPipe.InsulationMm,80.0,"按管道保温厚度覆盖 B");
            Equal(fromPipe.HeightMm,200.0,"H 随管道保温厚度重查（B=80 → 200）");
            var panelOnly=T4ShoeCalculator.BuildLayout(
                new T4ShoeParameters {Dn=200,InsulationMm=50.0,LengthMm=300.0},
                false,300.0,80.0);
            Equal(panelOnly.Dn,200,"点选直线时用面板 DN");
            Equal(panelOnly.InsulationMm,50.0,"点选直线时用面板 B");
            var partial=T4ShoeCalculator.BuildLayout(
                new T4ShoeParameters {Dn=200,InsulationMm=50.0,LengthMm=300.0},
                true,300.0,null);
            Equal(partial.Dn,300,"读到 DN 时覆盖管径");
            Equal(partial.InsulationMm,50.0,"读不到保温时回落到面板 B");
            var unmatchedPipe=T4ShoeCalculator.BuildLayout(
                new T4ShoeParameters {Dn=200,InsulationMm=50.0,LengthMm=300.0},
                true,2000.0,60.0);
            Equal(unmatchedPipe.Dn,200,"公称直径匹配不上时回落到面板 DN");
            Equal(unmatchedPipe.InsulationMm,60.0,"保温厚度仍按管道值");

            // 表 2：隔热层外径 → 底板宽度。
            Equal(T4ShoeCatalog.BaseWidthForInsulationOd(200.0),100.0,"D=200 → W=100");
            Equal(T4ShoeCatalog.BaseWidthForInsulationOd(200.1),150.0,"D=200.1 → W=150");
            Equal(T4ShoeCatalog.BaseWidthForInsulationOd(1600.0),800.0,"D=1600 → W=800");
            Reject(()=>T4ShoeCatalog.BaseWidthForInsulationOd(1600.1),"超出表 2 上限");

            // 保温厚度 → H。
            Equal(T4ShoeCatalog.HeightForInsulation(50.0),150.0,"B=50 → H=150");
            Equal(T4ShoeCatalog.HeightForInsulation(75.0),150.0,"B=75 → H=150");
            Equal(T4ShoeCatalog.HeightForInsulation(100.0),200.0,"B=100 → H=200");
            Equal(T4ShoeCatalog.HeightForInsulation(275.0),350.0,"B=275 → H=350");
            Reject(()=>T4ShoeCatalog.HeightForInsulation(300.0),"超出保温厚度表上限");

            // 编号：名称-管径-温度代码-H-L-材料代码-F。
            Equal(T4ShoeCatalog.BuildNumber("T4",200,"350",400,500,"20","1"),
                "T4-200-350-400-500-20-1","管架编号");
            Equal(T4ShoeCatalog.BuildNumber("",200,"350",400,500,"",""),"","名称留空不编号");
            Equal(T4ShoeCatalog.RoundHalfUp(400.4),400,"四舍五入 400.4");
            Equal(T4ShoeCatalog.RoundHalfUp(400.5),401,"四舍五入 400.5");

            var parameters=new T4ShoeParameters {Dn=200,InsulationMm=50.0,LengthMm=300.0,
                Name="T4",TemperatureCode="350",MaterialCode="20",FCode="1"};
            var layout=T4ShoeCalculator.BuildLayout(parameters);
            Equal(layout.PipeRadiusMm,109.55,"管半径");
            Equal(layout.InsulationRadiusMm,159.55,"保温层半径 = 管半径 + B");
            Equal(layout.InsulationOdMm,319.1,"保温层外径 D");
            Equal(layout.ClampOuterRadiusMm,171.55,"管夹外圆半径 = 保温层半径 + T3");
            Equal(layout.HeightMm,150.0,"H 按 B 查表");
            Equal(layout.Height1Mm,138.0,"H1 = H − T1");
            Equal(layout.BaseWidthMm,200.0,"底板宽度按表 2");
            Near(layout.ShoeBottomZMm,-259.55,0.0001,"管托底面标高 = −(管半径 + H)");
            Near(layout.BaseTopZMm,-247.55,0.0001,"底板顶面标高");
            Equal(layout.BoltLengthMm,65.0,"螺栓长 = 2×耳板厚 + 25");
            Check(!layout.HasMiddleRib,"L=300 不加中间肋板");
            Equal(layout.Number,"T4-200-350-150-300-20-1","编号（H 取查表值）");

            var longShoe=T4ShoeCalculator.BuildLayout(new T4ShoeParameters {
                Dn=200,InsulationMm=50.0,LengthMm=700.0});
            Check(longShoe.HasMiddleRib,"L=700 应加中间肋板");
            Reject(()=>T4ShoeCalculator.BuildLayout(new T4ShoeParameters {
                Dn=200,InsulationMm=50.0,LengthMm=200.0}),"管托长 L 过小");
            Reject(()=>T4ShoeCalculator.BuildLayout(new T4ShoeParameters {
                Dn=200,InsulationMm=0.0,LengthMm=300.0}),"隔热层厚度过小");

            // 布尔布局：两片承重板对开、耳板 2 组 × 4 块、支撑 2 道。
            var bl=T4ShoeCalculator.BuildBooleanLayout(layout);
            Equal(bl.EarCenterXmm.Length,2,"L=300 时耳板 2 组");
            Equal(bl.EarBounds.Length,4,"每组 4 块耳板");
            Equal(bl.SupportCenterXmm.Length,2,"L=300 时横向支撑 2 道");
            foreach(int dn in smallDns) foreach(double insulation in new[]{25.0,50.0,100.0})
            {
                var smallLayout=T4ShoeCalculator.BuildLayout(new T4ShoeParameters {
                    Dn=dn,InsulationMm=insulation,LengthMm=300.0});
                var smallBoolean=T4ShoeCalculator.BuildBooleanLayout(smallLayout);
                Equal(smallBoolean.SupportCenterXmm.Length,0,
                    "详图 B 无横向弧板支撑 DN"+dn+" B"+insulation);
                Equal(smallBoolean.EarCenterXmm.Length,2,
                    "详图 B 两组耳板 DN"+dn+" B"+insulation);
            }
            Near(bl.EarCenterXmm[0],-75.0,0.0001,"首组耳板位置");
            Near(bl.EarCenterXmm[1],75.0,0.0001,"尾组耳板位置");
            Equal(bl.HoleDiameterMm,22.0,"螺栓通孔 = M20 + 2");
            Near(bl.SupportHalfSpanMm,90.0,0.0001,"横向支撑半宽 = W/2 − 10");
            Near(bl.TrimRadiusMm,170.55,0.0001,"弧顶剪切半径 = 外圆半径 − 搭接量");
            Near(bl.SupportTopZMm,-144.869909,0.0001,"弧顶支撑顶面标高");
            // 三组以上时中间加一道支撑。
            var bl3=T4ShoeCalculator.BuildBooleanLayout(longShoe);
            Equal(bl3.EarCenterXmm.Length,3,"L=700 时耳板 3 组");
            Equal(bl3.SupportCenterXmm.Length,3,"L=700 时含中间肋板共 3 道");
            Equal(bl3.SupportCenterXmm[1],0.0,"中间肋板在轴向中点");
            // 孔位校核：孔心在耳板边界内、且不与管夹本体相交。
            for(int i=0;i<bl.EarBounds.Length;i++)
            {
                var b=bl.EarBounds[i];
                double a=bl.EarHoleA[i];
                double radius=bl.HoleDiameterMm/2.0;
                Check(a-radius>b[0] && a+radius<b[1],"孔超出耳板边界");
                Check(Math.Abs(a)-radius>0.0,"孔心应在耳板外侧");
            }
            // 承重板间隙 J 必须小于内径；小管径 + 薄保温时耳板根部会穿入保温层，应被拒绝。
            Reject(()=>T4ShoeCalculator.BuildBooleanLayout(T4ShoeCalculator.BuildLayout(
                new T4ShoeParameters {Dn=80,InsulationMm=1.0,LengthMm=300.0})),
                "耳板根部穿入保温层 / 间隙不小于管夹内径");
            // 构件角色码会被支吊架清单写成固定的 ItemType 名后缀（PipeSupportComponent_T4_<code>），
            // 因此同一元素内必须互不重复，否则后一条记录会覆盖前一条。
            foreach(bool pipe in new[]{false,true}) foreach(bool insu in new[]{false,true})
            {
                var codes=new List<string>();
                foreach(var it in T4ShoeCalculator.ComponentItems(longShoe,bl,pipe,insu))
                {
                    Check(!codes.Contains(it[0]),
                        "T4 构件角色码重复（会导致 ItemType 名冲突）："+it[0]+
                        " 已生成管道="+pipe+" 已生成保温="+insu);
                    codes.Add(it[0]);
                }
                Check(codes.Count>0,"T4 至少应有一条构件记录");
            }
        }
    }
}
