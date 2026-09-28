using System;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    /// <summary>
    /// 放置管夹（A2 / E1 / K1 / T4）的纯计算检查。断言对象为四种管夹的表数据、尺寸推导、
    /// 坐标架、编号与非法输入拒绝，口径须与 Python 各脚本一致。
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
            CheckA2();
            CheckK1();
            CheckT4();
            Console.WriteLine("放置管夹：A2 / E1 / K1 / T4 的表数据、尺寸推导、坐标架与非法输入校验通过。");
        }

        /// <summary>四种管夹的清单属性契约（中文类型名 + ASCII 代号）。</summary>
        private static void CheckCatalog()
        {
            var types=PipeClampCatalog.All;
            Equal(types.Length,4,"管夹类型数量");
            string[] codes={"A2","E1","K1","T4"};
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

        private static void CheckT4()
        {
            Equal(T4ShoeCatalog.All.Length,13,"T4 表 1 行数");
            var row=T4ShoeCatalog.Require(200);
            Equal(row.Nps,"8\"","DN200 NPS");
            Equal(row.OutsideMm,219.1,"DN200 外径");
            Equal(row.Bolt,"M20","DN200 螺栓");
            Equal(row.EarWidthMm,60.0,"DN200 耳板宽");
            Equal(row.T1Mm,12.0,"DN200 底板厚");
            Equal(row.T3Mm,12.0,"DN200 承重板厚");
            Equal(row.PlateGapJMm,30.0,"DN200 承重板间隙 J");
            Equal(T4ShoeCatalog.BoltCount(200),4,"DN80~600 均 4 颗螺栓");
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
