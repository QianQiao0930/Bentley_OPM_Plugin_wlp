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
        private static void Main()
        {
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
            Console.WriteLine("围栏："+cases.Length+" 组 Python 基准 × 4 种连接形式、模数排柱、偏移路径、节点和非法输入检查通过。");
        }
    }
}
