using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class MixedPathChecks
    {
        internal static void Run()
        {
            int combinations=0;
            foreach(int side in new[]{1,-1})foreach(bool reverse in new[]{false,true})
            foreach(int direction in new[]{1,-1})foreach(int flights in new[]{2,4})
            foreach(HandrailConnection connection in new[]{HandrailConnection.Type1,HandrailConnection.Type2,HandrailConnection.Type3,HandrailConnection.Type4}){
                var points=new List<HandrailPoint>();double angle=0,z=200,r=10800,inner=10100;
                for(int flight=0;flight<flights;flight++){
                    double sweep=direction*250.0/inner*(100/flights),rise=20000.0/flights;
                    for(int j=flight==0?0:1;j<=64;j++){
                        double a=angle+sweep*j/64;points.Add(new HandrailPoint(r*Math.Cos(a),r*Math.Sin(a),z+rise*j/64));}
                    angle+=sweep;z+=rise;angle+=direction*1000/inner;
                    points.Add(new HandrailPoint(r*Math.Cos(angle),r*Math.Sin(angle),z));
                }
                points.Add(new HandrailPoint(inner*Math.Cos(angle),inner*Math.Sin(angle),z));
                var parameters=new HandrailParameters{Side=side,Reverse=reverse,Connection=connection};
                var plan=HandrailCalculator.CalculateArc(parameters,new HandrailArcInput{MixedPoints=points});
                if(!plan.IsSpatialMixed||plan.Stations.Count<10||plan.Stations.Count>50)throw new Exception("混合路径排柱异常");
                if(plan.LengthMm<20000||plan.Kickplate.Count<10)throw new Exception("混合路径长度或踢脚板异常");
                for(int i=1;i<plan.Pieces.Count;i++)if((plan.Pieces[i].Start-plan.Pieces[i-1].End).Length>.01)throw new Exception("围栏路径不连续");
                for(int i=1;i<plan.Kickplate.Count;i++)if((plan.Kickplate[i].Start-plan.Kickplate[i-1].End).Length>.01)throw new Exception("踢脚板偏移不连续");
                for(int i=1;i<plan.Stations.Count;i++)if(plan.Stations[i]-plan.Stations[i-1]>2000.01||plan.Stations[i]-plan.Stations[i-1]<.01)throw new Exception("柱距或重复立柱异常");
                var graded=plan.Pieces.Where(p=>!p.IsArc&&Math.Abs(p.End.Z-p.Start.Z)>1).ToList();
                if(graded.Count==0)throw new Exception("螺旋梯段高度丢失");
                foreach(var p in graded)if(Math.Sign(p.End.Z-p.Start.Z)!=(reverse?-1:1))throw new Exception("反向路径高度错误");
                combinations++;
            }
            Console.WriteLine("混合盘梯路径："+combinations+"组正反向、内外侧、两/四梯段和四种连接检查通过。");
            var arcPoints=new List<HandrailPoint>{new HandrailPoint(5000,-1000,0)};
            for(int i=0;i<=100;i++){double a=i*Math.PI/200;arcPoints.Add(new HandrailPoint(5000*Math.Cos(a),5000*Math.Sin(a),0));}
            var arcPlan=HandrailCalculator.Calculate(new HandrailParameters(),arcPoints,true);
            if(arcPlan.Stations.Count>10)throw new Exception("圆弧求值点被当作密集转角排柱");
            var crossing=new[]{new HandrailPoint(0,0,0),new HandrailPoint(1000,1000,0),
                               new HandrailPoint(0,1000,500),new HandrailPoint(1000,0,500)};
            HandrailCalculator.Clean(crossing,true);
            bool rejected=false;
            try{HandrailCalculator.Clean(new[]{crossing[0],crossing[1],new HandrailPoint(0,1000,0),new HandrailPoint(1000,0,0)},true);}
            catch(InvalidOperationException){rejected=true;}
            if(!rejected)throw new Exception("真实自交未被拒绝");
            rejected=false;
            try{HandrailCalculator.Calculate(new HandrailParameters(),new[]{new HandrailPoint(0,0,0),new HandrailPoint(1000,0,500),new HandrailPoint(1000,1000,1000)},true);}
            catch(InvalidOperationException){rejected=true;}
            if(!rejected)throw new Exception("空间急转未被拒绝");
        }
    }
}
