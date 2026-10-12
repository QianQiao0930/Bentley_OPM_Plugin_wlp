using System;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool value,string label){checks++;if(!value)throw new Exception(label);}
        private static void Equal(double a,double b,string label){Check(Math.Abs(a-b)<1e-8,label);}
        private static void Reject(Action action,string label)
        {checks++;try{action();}catch(InvalidOperationException){return;}throw new Exception(label+" 应拒绝");}
        private static void CheckQ2()
        {
            double[][] loads={new[]{.5,.2,0,0},new[]{2.0,1,.5,.2},new[]{4.0,2,1,.6}};
            for(int i=0;i<3;i++)for(int j=0;j<4;j++)
            {
                string item=new[]{"A","B","C"}[i];double l=new[]{250.0,500,750,1000}[j];
                if(loads[i][j]==0)Reject(()=>Q2SupportCatalog.Load(item,l),"空白荷载档");else Equal(Q2SupportCatalog.Load(item,l),loads[i][j],"Q2表1荷载");
            }
            foreach(int type in new[]{1,2,3,4})foreach(string item in new[]{"A","B","C"})foreach(bool guide in new[]{false,true})foreach(bool mirror in new[]{false,true})
            {
                var p=Q2SupportCalculator.Calculate(type,item,50,100,250,mirror,guide,"P");
                Check(p.SmallStationsMm.Length==(type==1?2:1),"Q2小管数量");
                Check((p.SmallClamp!=null)==(type>=3),"立管管卡");
                Check((p.SmallBlockMm!=null)==(type>=3),"被支撑立管承重块");
                if(type>=3){Equal(p.SmallBlockHeightMm,50,"DN50承重块长边沿管焊接50");Equal(p.SmallBlockProjectionMm,30,"DN50短边径向伸出30");}
                Equal(p.StartMm+p.LengthMm-p.LMm,type<=2?150:(p.SmallClamp.LegSpacingMm??p.SmallClamp.Row.C)/2+50,"Q2自由端距");
                Check(p.Number=="Q2-"+type+"-"+item+"-DN100-DN50-250","Q2编号");
                if(type>=3)
                {
                    Equal(p.SmallClamp.NutLow2Mm-p.SmallClamp.NutCenterMm,guide?p.ThicknessMm:0,"A/G螺母位置");
                    Equal(p.SmallYmm-p.SmallClamp.Row.OutsideMm/2-p.CornerYmm,guide?3:2,"A/G安装间隙");
                    if(guide)Equal((p.SmallClamp.LegSpacingMm.Value-p.SmallClamp.Row.Bolt-p.SmallClamp.Row.OutsideMm)/2,3,"导向U弧管壁净隙3mm");
                }
            }
            Equal(Q2SupportCatalog.Block(65)[0],50,"小承重块长");Equal(Q2SupportCatalog.Block(80)[0],100,"大承重块长");
            Equal(Q2SupportCatalog.Block(150)[1],50,"大承重块短边");
            Check(Q2SupportCalculator.Calculate(3,"C",150,300,500,false,false,"").SmallBlockMm[0]==100,"DN150小立管承重块");
            Reject(()=>Q2SupportCatalog.Block(200),"承重块超表");
            Check(Q2SupportCalculator.Calculate(4,"B",80,300,500,false,false,"").SmallBlockMm[0]==100,"截图DN300主管DN80小管L500允许放置");
            foreach(var row in A1ClampCatalog.All)
            {
                if(row.Dn<=80)continue;
                foreach(bool guide in new[]{false,true})foreach(bool mirror in new[]{false,true})
                {
                    var p=Q2SupportCalculator.Calculate(4,"B",80,row.Dn,1000,mirror,guide,"");
                    Check(p.BigVertical,"大立管选型");
                    Check(p.SmallBlockMm[0]==100,"只按小立管DN80选承重块");
                    Equal(p.SmallBlockHeightMm,100,"DN80沿管焊接长边100");Equal(p.SmallBlockProjectionMm,50,"DN80径向短边50");
                    Check(p.BigClamp.Row.Dn==row.Dn,"主管不受承重块表DN150限制");
                }
            }
            Reject(()=>Q2SupportCatalog.Load("A",500.01),"子项A长度超限");
            Reject(()=>Q2SupportCatalog.Load("B",1000.01),"L超限");
            double[] x,y,z;Q2SupportCalculator.Axes(new[]{0.0,0,1},true,false,out x,out y,out z);
            Reject(()=>Q2SupportCalculator.Axes(new[]{0.0,0,1},false,false,out x,out y,out z),"水平类型点取立管");
            Reject(()=>Q2SupportCalculator.Axes(new[]{1.0,0,0},true,false,out x,out y,out z),"立管类型点取水平管");
            Check(Q2SupportCatalog.SupportType.StartsWith("Q2-["),"Q2中文统计类型");
        }
        private static void Main()
        {
            Check(Q1SupportCatalog.SupportType=="Q1-[大管用角钢支撑小管(1/2\"~4\"，不保温管)]","中文统计类型");
            foreach(int dn in Q1SupportCatalog.SmallDns)foreach(int type in new[]{1,2,3,4})
            {
                var p=Q1SupportCalculator.Calculate(type,dn,150,500,false,"P-1",168.3,0);
                Check(p.Subitem==(dn<=25?"A":dn<=50?"B":"C"),"表 1 子项");
                Equal(p.LoadKn,dn<=25?.6:dn<=50?1.6:3,"表 1 荷载");
                Check(Q1SupportCatalog.Mode(p).Segments.Length>3,"型钢目录真实轮廓");
                Check(!p.Mirrored,"默认非镜像");
                var mirror=Q1SupportCalculator.Calculate(type,dn,150,500,true,"P-1",168.3,0);
                Check(mirror.Mirrored,"镜像状态");Equal(mirror.SmallYmm,p.SmallYmm,"镜像不改变上下类型");
                Equal(mirror.LengthMm,p.LengthMm,"镜像不改变角钢长度");
                if(!p.Parallel)Equal(p.SmallXmm+p.SmallClamp.NutLow2Mm-p.ThicknessMm/2,p.CornerXmm+p.ThicknessMm/2,"小管卡开口指向角钢正X");
                Equal(p.SmallYmm,(type==1||type==4?-500:500),"上下布置");
                Check(p.Parallel==(type>=3),"两管轴线关系");
                double high=p.LowMm+p.LengthMm;
                Equal(Math.Min(-p.BigClamp.Row.C/2.0,p.SmallYmm-p.SmallClamp.Row.C/2.0)-p.LowMm,50,"下端距");
                Equal(high-Math.Max(p.BigClamp.Row.C/2.0,p.SmallYmm+p.SmallClamp.Row.C/2.0),50,"上端距");
                Equal(p.BigClamp.NutLow2Mm-p.BigClamp.NutCenterMm,p.ThicknessMm,"大管螺母板厚间隙");
                Equal(p.SmallClamp.NutLow2Mm-p.SmallClamp.NutCenterMm,p.ThicknessMm,"小管螺母板厚间隙");
                Check(p.Number=="Q1-"+type+"-"+p.Subitem+"-DN150-DN"+dn+"-500","编号字段顺序");
                Equal(p.PadThicknessMm,p.Parallel?p.CornerZmm-p.SmallZmm-p.SmallClamp.Row.OutsideMm/2:0,"现场垫板厚度");
            }
            Equal(Q1SupportCalculator.Calculate(1,15,900,1000,false,"").HeightMm,1000,"H 上限");
            foreach(double h in new[]{0.0,-1,1000.01,double.NaN,double.PositiveInfinity,20})
                Reject(()=>Q1SupportCalculator.Calculate(1,15,150,h,false,""),"非法 H");
            Reject(()=>Q1SupportCalculator.Calculate(0,15,150,500,false,""),"非法类型");
            Reject(()=>Q1SupportCalculator.Calculate(5,15,150,500,false,""),"非法类型");
            Reject(()=>Q1SupportCalculator.Calculate(1,125,150,500,false,""),"小管超限");
            Reject(()=>Q1SupportCalculator.Calculate(1,50,50,500,false,""),"大管不大于小管");
            Reject(()=>Q1SupportCalculator.Calculate(1,15,150,500,false,"",200,0),"外径不符");
            Reject(()=>Q1SupportCalculator.Calculate(1,15,150,500,false,"",168.3,50),"保温管");
            foreach(var axis in new[]{new[]{1.0,0,0},new[]{0.0,1,0},new[]{1.0,1,0},new[]{0.0,0,1}})
            {
                double[] x,y,z,mx,my,mz;
                Q1SupportCalculator.Axes(axis,false,out x,out y,out z);
                Q1SupportCalculator.Axes(axis,true,out mx,out my,out mz);
                for(int i=0;i<3;i++){Equal(x[i],mx[i],"镜像保留大管轴");Equal(y[i],my[i],"镜像保留高度方向");Equal(z[i],-mz[i],"镜像反转横向侧");}
            }
            foreach(var big in A1ClampCatalog.All)foreach(int dn in Q1SupportCatalog.SmallDns)
            {
                if(big.Dn<=dn)continue;
                foreach(int type in new[]{1,2,3,4})foreach(bool mirrored in new[]{false,true})
                {
                    int standardD=big.D;
                    var p=Q1SupportCalculator.Calculate(type,dn,big.Dn,1000,mirrored,"");
                    Equal(p.CornerZmm-big.OutsideMm/2,2,"大管壁至角钢2mm");
                    Equal(p.Parallel?p.PadThicknessMm:p.CornerXmm-p.SmallXmm-p.SmallClamp.Row.OutsideMm/2,2,"小管壁安装净隙2mm");
                    foreach(var clamp in new[]{p.BigClamp,p.SmallClamp})
                    {
                        Check(clamp.StraightLegMm.HasValue&&clamp.StraightLegMm.Value<=clamp.Row.D,"只缩短Q1直腿");
                        Check(clamp.NutLow1Mm>0,"内侧螺母不越过弯弧");
                        Check(clamp.StraightLegMm.Value-clamp.NutLow2Mm-clamp.NutHeightMm>=3-1e-8,"螺母外留丝头");
                    }
                    Equal(big.D,standardD,"不修改公共A1目录");
                }
            }
            Check(!A1ClampCalculator.Calculate(150,false,null,0,"").StraightLegMm.HasValue,"独立A1仍使用标准D");
            foreach(double angle in new[]{0.0,90,180,270,359.5})foreach(bool mirrored in new[]{false,true})
            {
                double[] x,y,z;
                Q2SupportCalculator.Axes(new[]{0.0,0,1},true,mirrored,out x,out y,out z,angle);
                double a=angle*Math.PI/180,sign=mirrored?-1:1;
                Equal(x[0],sign*Math.Cos(a),"类型4旋转X");Equal(x[1],sign*Math.Sin(a),"类型4旋转Y");
                Equal(z[2],1,"类型4绕管轴旋转保留竖向");Equal(y[0],-Math.Sin(a),"角钢及管卡坐标共同旋转");
                double[] dx,dy,dz;Q2SupportCalculator.Axes(new[]{0.0,0,-1},true,mirrored,out dx,out dy,out dz,angle);
                for(int i=0;i<3;i++)Equal(dx[i],x[i],"反向管轴角度基准一致");
            }
            var origin=new[]{500.0,0,0};var start=new[]{0.0,0,0};var end=new[]{1000.0,0,0};
            Equal(AxisPlacementCalculator.Shift(origin,start,end,200,true)[0],700,"数值偏移");
            Equal(AxisPlacementCalculator.Offset(origin,new[]{700.0,0,0},start,end),200,"滑动锁定偏移");
            Reject(()=>AxisPlacementCalculator.Shift(origin,start,end,501,true),"偏移超出管段");
            Reject(()=>AxisPlacementCalculator.Shift(origin,start,end,double.NaN,true),"非法偏移");
            CheckQ2();
            Console.WriteLine("Q1/Q2："+checks+" 项表数据、四类型布局、端距、螺母间隙、编号与边界检查通过。");
        }
    }
}
