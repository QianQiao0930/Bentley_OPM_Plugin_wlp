using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Collections.Generic;
namespace SteelSectionProbe
{
    internal sealed class Reference
    {
        public int direction;
        public double interval,gap;
        public double[][][] beamPoints,railPoints;
        public double[][][][] profiles;
        public double[][][] plates;
        public int[] plateIndices,counts;
    }
    internal static class Program
    {
        private static void Check(bool ok,string name){if(!ok)throw new Exception(name);}
        private static void Near(double a,double b,string name){Check(Math.Abs(a-b)<1e-6,name+": "+a+" != "+b);}
        private static void Point(HandrailPoint p,double[] q){Near(p.X,q[0],"X");Near(p.Y,q[1],"Y");Near(p.Z,q[2],"Z");}
        private static void Reject(SpiralStairParameters p){try{SpiralStairCalculator.Calculate(p);}catch(InvalidOperationException){return;}throw new Exception("非法参数未拒绝");}
        private static void Main()
        {
            PreviewChecks.Run();
            string folder=Path.Combine(Path.GetTempPath(),"SpiralStairLogCheck_"+Guid.NewGuid().ToString("N"));string logPath;
            using(var log=new SpiralStairLog(folder)){
                logPath=log.FilePath;log.Parameters(new SpiralStairParameters());
                log.Write("内侧梯梁放样 1/128",new InvalidOperationException("直纹扫掠诊断测试").ToString());
            }
            SpiralStairLog.Append(logPath,"确认生成","完成");string contents=File.ReadAllText(logPath);
            Check(contents.Contains("TankDiameterMm=20000")&&contents.Contains("内侧梯梁放样 1/128")&&contents.Contains("InvalidOperationException")&&contents.Contains("确认生成"),"UTF8日志内容");
            using(var failedLog=new SpiralStairLog(logPath))Check(failedLog.FilePath.StartsWith("日志创建失败"),"日志目录失败不阻断建模");
            using(var overwritten=new SpiralStairLog(folder)){Check(overwritten.FilePath==logPath,"固定日志文件");overwritten.Write("新建模","新一轮记录");}
            contents=File.ReadAllText(logPath);Check(contents.Contains("新一轮记录")&&!contents.Contains("直纹扫掠诊断测试"),"每次建模覆盖旧日志");
            using(var bounded=new SpiralStairLog(folder)){bounded.Write("测试",new string('A',2100000));bounded.Write("失败","最后阶段错误保留");}
            Check(new FileInfo(logPath).Length<10000&&File.ReadAllText(logPath).Contains("最后阶段错误保留"),"日志大小限制与最新异常");
            File.Delete(logPath);Directory.Delete(folder);
            var refs=JsonSerializer.Deserialize<Reference[]>(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"python_reference.json")),new JsonSerializerOptions{IncludeFields=true});
            foreach(var c in refs)
            {
                var p=new SpiralStairParameters{Direction=c.direction,LandingIntervalMm=c.interval,WallGapMm=c.gap,StartAngleDegrees=17,StartZmm=1000,EndZmm=21000};
                var plan=SpiralStairCalculator.Calculate(p);Check(plan.FlightCounts.SequenceEqual(c.counts),"梯段数量");
                for(int side=0;side<2;side++)
                {
                    var beam=plan.Beams[side];Check(beam.Points.Count==c.beamPoints[side].Length,"路径点数");
                    for(int i=0;i<beam.Points.Count;i++){Point(beam.Points[i],c.beamPoints[side][i]);Point(plan.RailingPaths[side][i],c.railPoints[side][i]);}
                    int[] indices={0,beam.Points.Count/2,beam.Points.Count-2,beam.Points.Count-1};
                    for(int j=0;j<indices.Length;j++)for(int k=0;k<8;k++)Point(beam.Profiles[indices[j]][k],c.profiles[side][j][k]);
                    foreach(var profile in beam.Profiles){Near(profile[0].Z-profile[7].Z,200,"梁高");Near(profile[1].Z,profile[0].Z,"栏杆顶面");}
                }
                for(int j=0;j<c.plateIndices.Length;j++)
                {var plate=plan.Plates[c.plateIndices[j]];Check(plate.Corners.Count==c.plates[j].Length,"板件点数");for(int k=0;k<plate.Corners.Count;k++)Point(plate.Corners[k],c.plates[j][k]);}
                Check(plan.Plates.Count==plan.TreadCount*3+plan.FlightCounts.Count,"踏板/平台构件数");
                Check(plan.Parameters.RequiresInnerRailing==(p.WallGapMm>100),"内侧栏杆强制规则");
                foreach(var plate in plan.Plates)Check(plate.Corners.All(q=>Math.Abs(q.Z-plate.Corners[0].Z)<1e-8),"水平板件");
                foreach(double spacing in new[]{1500.0,1800.0,2000.0})foreach(var connection in new[]{HandrailConnection.Type1,HandrailConnection.Type2,HandrailConnection.Type3,HandrailConnection.Type4})
                {
                    plan.Parameters.MaxPostSpacingMm=spacing;plan.Parameters.Connection=connection;
                    foreach(bool inner in new[]{false,true})
                    {
                        var rail=SpiralStairCalculator.Railing(plan,inner);Check(rail.IsSpatialMixed,"复用混合栏杆业务");
                        Check(rail.Stations.Zip(rail.Stations.Skip(1),(a,b)=>b-a).All(d=>d>0.01&&d<=spacing+0.01),"栏杆间距");
                        Check(rail.Pieces.Zip(rail.Pieces.Skip(1),(a,b)=>(a.End-b.Start).Length).All(d=>d<0.01),"栏杆连续");
                        foreach(var run in HandrailSmoothPath.Runs(rail.Pieces).Where(q=>q.Count>1)){
                            List<HandrailPoint> poles;List<double> knots;HandrailSmoothPath.Spline(run,out poles,out knots);
                            Check(poles.Count==run.Count*3+1&&knots.Count==poles.Count+4,"样条阶数及节点");
                            for(int i=0;i<run.Count;i++){
                                Near((poles[i*3]-run[i].Start).Length,0,"样条穿过原始起点");Near((poles[i*3+3]-run[i].End).Length,0,"样条穿过原始终点");
                                var middle=poles[i*3]*.125+poles[i*3+1]*.375+poles[i*3+2]*.375+poles[i*3+3]*.125;
                                Check((middle-(run[i].Start+run[i].End)*.5).Length<1,"盘梯光滑曲线相对折线偏差小于1mm");
                                if(i>0){var left=(poles[i*3]-poles[i*3-1])*(3/run[i-1].Length);var right=(poles[i*3+1]-poles[i*3])*(3/run[i].Length);Near((left-right).Length,0,"样条切向连续");}
                            }
                        }
                    }
                }
                p.WallGapMm=999;Near(plan.Parameters.WallGapMm,c.gap,"参数快照");
            }
            Check(!SpiralStairCalculator.Calculate(new SpiralStairParameters{WallGapMm=100}).Parameters.RequiresInnerRailing,"100mm可选");
            Check(SpiralStairCalculator.Calculate(new SpiralStairParameters{WallGapMm=100.01}).Parameters.RequiresInnerRailing,"超过100mm强制");
            Check(SpiralStairCalculator.Calculate(new SpiralStairParameters{InnerRailing=true}).Parameters.RequiresInnerRailing,"内侧可主动选择");
            Check(SpiralStairCalculator.Calculate(new SpiralStairParameters{EndZmm=17000,LandingIntervalMm=5000}).FlightCounts.SequenceEqual(new[]{25,25,25,10}),"末段不足间隔");
            foreach(var p in new[]{new SpiralStairParameters{LandingIntervalMm=0},new SpiralStairParameters{RiserMm=210},new SpiralStairParameters{WallGapMm=-1},new SpiralStairParameters{TreadDepthMm=100},new SpiralStairParameters{TankDiameterMm=double.NaN},new SpiralStairParameters{ClearWidthMm=640},new SpiralStairParameters{Direction=0},new SpiralStairParameters{MaxPostSpacingMm=2001}})Reject(p);
            Console.WriteLine("盘梯：12组Python几何对照、288组栏杆组合及边界/非法输入检查通过。");
        }
    }
}
