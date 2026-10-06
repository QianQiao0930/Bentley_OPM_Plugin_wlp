using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
namespace SteelSectionProbe
{
    internal sealed class ReferenceNode
    {public double[] point,tangent,bottom,plate1,plate2,elbow,tube;}
    internal sealed class ReferenceCase
    {public double[][] vertices,kickStarts,kickEnds;public double[] stations,kickRadii;public int side;public bool reverse;public double length;public ReferenceNode[] nodes;}
    internal static class Program
    {
        private static HandrailPoint P(double[] p){return new HandrailPoint(p[0],p[1],p[2]);}
        private static void Near(double a,double b,string message){if(double.IsNaN(a)||Math.Abs(a-b)>1e-6)throw new Exception(message+": "+a+" != "+b);}
        private static void Point(HandrailPoint a,double[] b,string label){Near(a.X,b[0],label+" X");Near(a.Y,b[1],label+" Y");Near(a.Z,b[2],label+" Z");}
        private static void Check(bool condition,string label){if(!condition)throw new Exception(label);}
        private static void Reject(Action action,string label){try{action();}catch(InvalidOperationException){return;}throw new Exception(label+" 应被拒绝。");}
        private static void Main(string[] args)
        {
            MixedPathChecks.Run();
            foreach(double maximum in new[]{1500.0,1800.0,2000.0,1575.0})
            {
                foreach(double length in new[]{maximum-1,maximum,maximum+1,10001.0})
                {
                    var adjustableSpans=HandrailCalculator.ModularSpans(length,maximum);
                    Near(adjustableSpans.Sum(),length,"可调间距总长");
                    Check(adjustableSpans.All(x=>x>0&&x<=maximum+0.01),"可调最大间距");
                }
                var input=new HandrailArcInput{Center=new HandrailPoint(0,0,0),Vector0=new HandrailPoint(10000,0,0),Vector90=new HandrailPoint(0,10000,0),SweepAngle=1,IsHelix=true,RiseMm=5000};
                foreach(int mode in new[]{0,1,2,3})
                {
                    var p=new HandrailParameters{MaxPostSpacingMm=maximum};
                    input.IsHelix=mode==2;
                    input.MixedPoints=mode==3?new List<HandrailPoint>{new HandrailPoint(0,0,0),new HandrailPoint(5000,0,2000),new HandrailPoint(10000,200,4000)}:null;
                    var plan=mode==0?HandrailCalculator.Calculate(p,new[]{new HandrailPoint(0,0,0),new HandrailPoint(10001,0,3000)}):HandrailCalculator.CalculateArc(p,input);
                    Near(plan.Parameters.MaxPostSpacingMm,maximum,"间距快照");
                    Check(plan.Stations.Zip(plan.Stations.Skip(1),(a,b)=>b-a).All(x=>x<=maximum+0.01),"各类路径最大间距");
                }
            }
            foreach(double invalid in new[]{0.0,299.0,2001.0,double.NaN,double.PositiveInfinity})
                Reject(()=>HandrailCalculator.ModularSpans(10000,invalid),"非法最大间距");
            var cases=JsonSerializer.Deserialize<ReferenceCase[]>(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"reference.json")),new JsonSerializerOptions{IncludeFields=true});
            foreach(var c in cases)foreach(var type in new[]{HandrailConnection.Type1,HandrailConnection.Type2,HandrailConnection.Type3,HandrailConnection.Type4}){
                var parameters=new HandrailParameters{Side=c.side,Reverse=c.reverse,Connection=type,StructureOffsetMm=120,Closure=HandrailClosure.Both};
                var plan=HandrailCalculator.Calculate(parameters,c.vertices.Select(P).ToList());Near(plan.LengthMm,c.length,"Python 路径长度");
                Check(plan.Stations.Count==c.stations.Length,"Python 立柱数");
                for(int i=0;i<c.stations.Length;i++){
                    Near(plan.Stations[i],c.stations[i],"Python 站号");
                    HandrailPoint point,tangent;HandrailCalculator.At(plan.Pieces,plan.Stations[i],out point,out tangent);
                    var expected=c.nodes[i];Point(point,expected.point,"Python 立柱位置");Point(tangent,expected.tangent,"Python 切向");
                    var node=HandrailCalculator.Node(point,tangent,parameters);
                    if(type==HandrailConnection.Type1){Point(node.Bottom,expected.bottom,"压扁端底部");Point(node.PlateCenter,expected.plate1,"类型1连接板");
                        foreach(var section in node.Sections)Near(HandrailPoint.Dot(section.Center-point,node.Normal)+section.Minor,24.15,"压扁截面保持与板相切");}
                    if(type==HandrailConnection.Type2){Point(node.PlateCenter,expected.plate2,"类型2连接板");Point(node.ElbowEnd,expected.elbow,"下弯端");Point(node.TubeEnd,expected.tube,"管端搭接");}
                    if(type==HandrailConnection.Type3)Near(node.Bottom.Z-point.Z,10,"坡段水平底板");
                    Near(HandrailPoint.Dot(node.PlateLong,node.PlateShort),0,"板件轴线正交");
                }
                Check(plan.Kickplate.Count==c.kickStarts.Length,"偏移路径段数");
                for(int i=0;i<plan.Kickplate.Count;i++){
                    Point(plan.Kickplate[i].Start,c.kickStarts[i],"踢脚板起点");Point(plan.Kickplate[i].End,c.kickEnds[i],"踢脚板终点");
                    if(plan.Kickplate[i].IsArc)Near(plan.Kickplate[i].Radius,c.kickRadii[i],"踢脚板圆角半径");
                }
                Near(plan.Materials.Single(m=>m.Code=="BALL").Quantity,2*plan.Stations.Count,"连接球数量");
                Near(plan.Materials.Single(m=>m.Code=="POST").LengthMm,type==HandrailConnection.Type3?1007:1017,"立柱下料长");
                Near(plan.Materials.Single(m=>m.Code=="END_CLOSURE").Quantity,2,"两端闭合清单");
                Near(plan.Materials.Single(m=>m.Code=="KICKPLATE").LengthMm,plan.Kickplate.Sum(x=>x.Length),"踢脚板实际偏移长");
                parameters.Side=-c.side;Check(plan.Parameters.Side==c.side,"预览参数快照");
            }
            foreach(double span in new[]{2000.1,5000,5999,9999,12345.67}){
                var lengths=HandrailCalculator.ModularSpans(span);Near(lengths.Sum(),span,"模数总长");Check(lengths.Max()<=2000.01,"最大柱距");
                Check(lengths.Count(x=>Math.Abs(x/50-Math.Round(x/50))>1e-6)<=1,"仅一跨非模数尾数");}
            var spans=HandrailCalculator.ModularSpans(5000);Check(spans.SequenceEqual(new[]{1650.0,1650,1700}),"首尾余量优先");
            var straight=new List<HandrailPoint>{new HandrailPoint(0,0,0),new HandrailPoint(5000,0,0)};
            foreach(HandrailClosure mode in Enum.GetValues(typeof(HandrailClosure))){var plan=HandrailCalculator.Calculate(new HandrailParameters{Closure=mode},straight);
                var item=plan.Materials.SingleOrDefault(x=>x.Code=="END_CLOSURE");Check(mode==HandrailClosure.None?item==null:item.Quantity==(mode==HandrailClosure.Both?2:1),"四种闭合方式");}
            Reject(()=>HandrailCalculator.Calculate(new HandrailParameters{StructureOffsetMm=83},straight),"类型2最小连接距离");
            Reject(()=>HandrailCalculator.Calculate(new HandrailParameters{StructureOffsetMm=double.NaN},straight),"无效连接距离");
            Reject(()=>HandrailCalculator.Calculate(new HandrailParameters{Side=0},straight),"非法侧向");
            Reject(()=>HandrailCalculator.BuildPath(new[]{new HandrailPoint(0,0,0),new HandrailPoint(0,0,200)}),"竖直段");
            Reject(()=>HandrailCalculator.BuildPath(new[]{new HandrailPoint(0,0,0),new HandrailPoint(3000,0,1000),new HandrailPoint(3000,3000,1000)}),"空间转向变坡");
            Reject(()=>HandrailCalculator.BuildPath(new[]{new HandrailPoint(0,0,0),new HandrailPoint(100,0,0),new HandrailPoint(100,100,0)}),"过短圆角");
            Reject(()=>HandrailCalculator.BuildPath(new[]{new HandrailPoint(0,0,0),new HandrailPoint(3000,0,0),new HandrailPoint(1000,0,0)}),"折返");
            Reject(()=>HandrailCalculator.Clean(new[]{new HandrailPoint(0,0,0),new HandrailPoint(1000,1000,0),new HandrailPoint(0,1000,0),new HandrailPoint(1000,0,0)}),"自交");
            Reject(()=>HandrailCalculator.Clean(new[]{new HandrailPoint(0,0,0),new HandrailPoint(1000,0,0),new HandrailPoint(0,0,0)}),"闭合");
            foreach(int side in new[]{-1,1})foreach(bool reverse in new[]{false,true})foreach(double sweep in new[]{Math.PI/2,-Math.PI/2,Math.PI*1.5})
            foreach(HandrailConnection type in Enum.GetValues(typeof(HandrailConnection))){
                var input=new HandrailArcInput{Center=new HandrailPoint(10000,20000,3000),Vector0=new HandrailPoint(2000,0,0),
                    Vector90=new HandrailPoint(0,2000,0),StartAngle=0.3,SweepAngle=sweep};
                var plan=HandrailCalculator.CalculateArc(new HandrailParameters{Side=side,Reverse=reverse,Connection=type},input);
                var piece=plan.Pieces.Single();double sign=Math.Sign(sweep)*(reverse?-1:1);
                Near(piece.Radius,2000-sign*side*HandrailCatalog.PathOffset,"圆弧偏移");
                Near(plan.LengthMm,piece.Radius*Math.Abs(sweep),"圆弧长度");
                Near(plan.Kickplate[0].Radius,piece.Radius-sign*side*HandrailCatalog.KickOffset,"踢脚板偏移");
                Near(piece.Start.Z+plan.Origin.Z,3000,"标高");
                Near(plan.Stations.Last(),plan.LengthMm,"末端柱");
                for(int i=1;i<plan.Stations.Count;i++)Check(plan.Stations[i]-plan.Stations[i-1]<=2000.01,"最大柱距");
            }
            var bad=new HandrailArcInput{Vector0=new HandrailPoint(2000,0,0),Vector90=new HandrailPoint(0,1000,0),SweepAngle=1};
            Reject(()=>HandrailCalculator.CalculateArc(new HandrailParameters(),bad),"椭圆");
            bad.Vector90=new HandrailPoint(0,0,2000);Reject(()=>HandrailCalculator.CalculateArc(new HandrailParameters(),bad),"倾斜圆弧");
            bad.Vector90=new HandrailPoint(0,2000,0);bad.SweepAngle=2*Math.PI;Reject(()=>HandrailCalculator.CalculateArc(new HandrailParameters(),bad),"整圆");
            bad.SweepAngle=2*Math.PI-0.001;Reject(()=>HandrailCalculator.CalculateArc(new HandrailParameters(),bad),"近整圈");
            bad.SweepAngle=1;bad.Vector0=new HandrailPoint(100,0,0);bad.Vector90=new HandrailPoint(0,100,0);
            Reject(()=>HandrailCalculator.CalculateArc(new HandrailParameters(),bad),"半径过小");
            foreach(double sweep in new[]{Math.PI*3,-Math.PI*3})foreach(double rise in new[]{6000.0,-6000.0})
            foreach(bool reverse in new[]{false,true})foreach(int side in new[]{-1,1})foreach(HandrailConnection type in Enum.GetValues(typeof(HandrailConnection))){
                var samples=Enumerable.Range(0,513).Select(i=>{double t=i/512.0,a=0.7+sweep*t;
                    return new HandrailPoint(1e7+5000*Math.Cos(a),-2e7+5000*Math.Sin(a),300+rise*t);}).ToList();
                var fit=HandrailHelixCalculator.Fit(samples);Near(fit.Vector0.Length,5000,"螺旋半径");Near(fit.RiseMm,rise,"螺旋高度");Near(fit.SweepAngle,sweep,"螺旋扫角");
                var plan=HandrailCalculator.CalculateArc(new HandrailParameters{Side=side,Reverse=reverse,Connection=type},fit);
                var piece=plan.Pieces[0];Near(piece.At(1).Z-piece.At(0).Z,reverse?-rise:rise,"反向升降");
                Near(piece.Length,Math.Sqrt(Math.Pow(piece.Radius*Math.Abs(sweep),2)+rise*rise),"三维弧长");
                Near(piece.Direction(0).Length,1,"三维切向");Near(plan.Kickplate[0].RiseMm,piece.RiseMm,"踢脚板升高一致");}
            var variable=Enumerable.Range(0,513).Select(i=>{double t=i/512.0,a=3*Math.PI*t;return new HandrailPoint(5000*Math.Cos(a),5000*Math.Sin(a),6000*t*t);}).ToList();
            Reject(()=>HandrailHelixCalculator.Fit(variable),"变螺距");
            variable=Enumerable.Range(0,513).Select(i=>{double t=i/512.0,a=3*Math.PI*t,r=5000+100*t;return new HandrailPoint(r*Math.Cos(a),r*Math.Sin(a),6000*t);}).ToList();
            Reject(()=>HandrailHelixCalculator.Fit(variable),"变半径");
            if(args.Length>0)CheckPastedSpline(args[0]);
            Console.WriteLine("围栏：原有基准、48 组圆弧和 64 组螺旋组合及非法输入检查通过。");
        }
        private static void CheckPastedSpline(string path)
        {
            string text=File.ReadAllText(path);var poles=new SortedDictionary<int,HandrailPoint>();
            foreach(System.Text.RegularExpressions.Match match in System.Text.RegularExpressions.Regex.Matches(text,"ControlPoints\\[(\\d+)\\]\\s+<DPoint3d xyz=\"([^\"]+)\"")){
                var v=match.Groups[2].Value.Split(',').Select(x=>double.Parse(x,System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                poles.Add(int.Parse(match.Groups[1].Value),new HandrailPoint(v[0],v[1],v[2]));}
            var values=new SortedDictionary<int,double>();var multiplicity=new Dictionary<int,int>();
            foreach(System.Text.RegularExpressions.Match match in System.Text.RegularExpressions.Regex.Matches(text,"Knots\\[(\\d+)\\]\\.(Value|Multiplicity)\\s+([^\\r\\n]+)")){
                int index=int.Parse(match.Groups[1].Value);if(match.Groups[2].Value=="Value")values[index]=double.Parse(match.Groups[3].Value,System.Globalization.CultureInfo.InvariantCulture);
                else multiplicity[index]=int.Parse(match.Groups[3].Value);}
            var knots=values.SelectMany(x=>Enumerable.Repeat(x.Value,multiplicity[x.Key])).ToArray();var p=poles.Values.ToArray();
            Check(p.Length==130&&knots.Length==p.Length+4,"用户样条数据完整");var samples=new List<HandrailPoint>();
            for(int i=0;i<=4096;i++){
                double t=i/4096.0;int span=p.Length-1;if(i<4096){span=3;while(span<p.Length-1&&knots[span+1]<=t)span++;}
                var d=new HandrailPoint[4];for(int j=0;j<4;j++)d[j]=p[span-3+j];
                for(int r=1;r<=3;r++)for(int j=3;j>=r;j--){int k=span-3+j;double a=(t-knots[k])/(knots[k+4-r]-knots[k]);d[j]=d[j-1]*(1-a)+d[j]*a;}
                samples.Add(d[3]);}
            // 属性未提供模型 UOR 换算。这里仅按半径归一到 5000 mm 验证形状，运行时读取真实模型单位。
            double scale=5000/HandrailHelixCalculator.Fit(samples,double.MaxValue).Vector0.Length;
            var fit=HandrailHelixCalculator.Fit(samples.Select(x=>x*scale).ToList());
            var plan=HandrailCalculator.CalculateArc(new HandrailParameters(),fit);
            Console.WriteLine("用户样条形状检查通过（半径归一化）：圈数="+(Math.Abs(fit.SweepAngle)/(2*Math.PI)).ToString("0.###")+"，立柱="+plan.Stations.Count);
        }
    }
}
