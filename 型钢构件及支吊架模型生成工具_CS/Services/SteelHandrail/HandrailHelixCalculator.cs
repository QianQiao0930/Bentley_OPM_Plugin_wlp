using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class HandrailHelixCalculator
    {
        // 使用原生曲线求值点，不能使用不在曲线上的 B 样条控制点。
        internal static HandrailArcInput Fit(IList<HandrailPoint> points,double tolerance=1)
        {
            if(points==null||points.Count<33)throw new InvalidOperationException("螺旋求值点不足。");
            var origin=points[0];var q=points.Select(x=>x-origin).ToList();
            if(q.Any(x=>double.IsNaN(x.Length)||double.IsInfinity(x.Length)))throw new InvalidOperationException("曲线坐标无效。");
            var m=new double[3,4];
            foreach(var x in q){double[] row={x.X,x.Y,1};double rhs=x.X*x.X+x.Y*x.Y;
                for(int i=0;i<3;i++){for(int j=0;j<3;j++)m[i,j]+=row[i]*row[j];m[i,3]+=row[i]*rhs;}}
            for(int i=0;i<3;i++){int pivot=i;for(int j=i+1;j<3;j++)if(Math.Abs(m[j,i])>Math.Abs(m[pivot,i]))pivot=j;
                if(Math.Abs(m[pivot,i])<1e-8)throw new InvalidOperationException("曲线投影不足以识别圆柱螺旋。");
                for(int k=i;k<4;k++){double t=m[i,k];m[i,k]=m[pivot,k];m[pivot,k]=t;}
                double d=m[i,i];for(int k=i;k<4;k++)m[i,k]/=d;
                for(int j=0;j<3;j++)if(j!=i){d=m[j,i];for(int k=i;k<4;k++)m[j,k]-=d*m[i,k];}}
            double cx=m[0,3]/2,cy=m[1,3]/2,radius=Math.Sqrt(cx*cx+cy*cy+m[2,3]);
            if(double.IsNaN(radius)||radius<140)throw new InvalidOperationException("螺旋半径无效或过小。");
            var angles=new List<double>{0};double first=Math.Atan2(q[0].Y-cy,q[0].X-cx),prev=first;
            foreach(var x in q.Skip(1)){double a=Math.Atan2(x.Y-cy,x.X-cx),step=a-prev;
                while(step>Math.PI)step-=2*Math.PI;while(step<-Math.PI)step+=2*Math.PI;
                if(Math.Abs(step)>Math.PI/8)throw new InvalidOperationException("螺旋圈数过多，曲线采样不足。");
                angles.Add(angles.Last()+step);prev=a;}
            double total=angles.Last();if(Math.Abs(total)<Math.PI/6||Math.Abs(total)>40*Math.PI)
                throw new InvalidOperationException("螺旋扫角需在 30° 至 20 圈之间。");
            double rise=q.Last().Z,rate=rise/total;
            if(Math.Abs(rise)<1)throw new InvalidOperationException("样条不是具有高度变化的螺旋线。");
            for(int i=0;i<q.Count;i++){
                var x=q[i];double rr=Math.Sqrt((x.X-cx)*(x.X-cx)+(x.Y-cy)*(x.Y-cy));
                if(Math.Abs(rr-radius)>tolerance||Math.Abs(x.Z-rate*angles[i])>tolerance||i>0&&(angles[i]-angles[i-1])*total<=0)
                    throw new InvalidOperationException("只支持固定半径、固定螺距的竖轴螺旋线（拟合容差 1 mm）。");}
            return new HandrailArcInput{Center=new HandrailPoint(origin.X+cx,origin.Y+cy,origin.Z),
                Vector0=new HandrailPoint(radius,0,0),Vector90=new HandrailPoint(0,radius,0),
                StartAngle=first,SweepAngle=total,RiseMm=rise,IsHelix=true};
        }
        internal static HandrailPlan Calculate(HandrailParameters p,HandrailArcInput input)
        {
            HandrailCalculator.Calculate(p,new[]{new HandrailPoint(0,0,0),new HandrailPoint(3000,0,0)});
            double sign=Math.Sign(input.SweepAngle)*(p.Reverse?-1:1),angle=Math.Abs(input.SweepAngle);
            double a=input.StartAngle+(p.Reverse?input.SweepAngle:0),rise=input.RiseMm*(p.Reverse?-1:1);
            double r=input.Vector0.Length-sign*p.Side*HandrailCatalog.PathOffset,k=r-sign*p.Side*HandrailCatalog.KickOffset;
            if(Math.Min(r,k)<140||angle<Math.PI/6||angle>40*Math.PI||double.IsNaN(angle)||double.IsInfinity(angle)
                ||double.IsNaN(rise)||double.IsInfinity(rise))throw new InvalidOperationException("螺旋偏移半径或高度无效。");
            if(angle>=2*Math.PI&&Math.Abs(rise/angle*2*Math.PI)<1200)
                throw new InvalidOperationException("螺旋每圈升高不足 1200 mm，围栏上下圈可能重叠。");
            var radial=new HandrailPoint(Math.Cos(a),Math.Sin(a),0);var tangent=new HandrailPoint(-Math.Sin(a)*sign,Math.Cos(a)*sign,0);
            var origin=input.Center+radial*input.Vector0.Length+HandrailPoint.Up*(p.Reverse?input.RiseMm:0);
            var piece=new HandrailPiece{IsArc=true,IsHelix=true,Center=input.Center-origin+HandrailPoint.Up*(p.Reverse?input.RiseMm:0),
                Radial=radial,Tangent=tangent,Radius=r,Angle=angle,RiseMm=rise,TurnSign=sign,Length=Math.Sqrt(r*r*angle*angle+rise*rise)};
            piece.Start=piece.At(0);piece.End=piece.At(1);
            var kick=new HandrailPiece{IsArc=true,IsHelix=true,Center=piece.Center,Radial=radial,Tangent=tangent,
                Radius=k,Angle=angle,RiseMm=rise,TurnSign=sign,Length=Math.Sqrt(k*k*angle*angle+rise*rise)};
            kick.Start=kick.At(0);kick.End=kick.At(1);
            var plan=new HandrailPlan{Origin=origin,LengthMm=piece.Length,Parameters=new HandrailParameters{Side=p.Side,Reverse=p.Reverse,
                Connection=p.Connection,Closure=p.Closure,StructureOffsetMm=p.StructureOffsetMm,MaxPostSpacingMm=p.MaxPostSpacingMm},Kickplate=new List<HandrailPiece>{kick}};
            plan.Pieces.Add(piece);plan.Stations=HandrailCalculator.PostStations(plan.LengthMm,plan.Corners,p.MaxPostSpacingMm);
            if(plan.Stations.Count>2000)throw new InvalidOperationException("螺旋立柱超过 2000 根，请拆分路径。");
            double clearance=p.Connection==HandrailConnection.Type2?Math.Max(146,p.StructureOffsetMm+38):146;
            for(int i=0;i<plan.Stations.Count;i++)for(int j=i+1;j<plan.Stations.Count;j++)
                if((piece.At(plan.Stations[i]/piece.Length)-piece.At(plan.Stations[j]/piece.Length)).Length<clearance)
                    throw new InvalidOperationException("螺旋立柱连接节点间距不足。");
            if(p.Closure!=HandrailClosure.None&&(piece.Start-piece.End).Length<643+clearance)
                throw new InvalidOperationException("螺旋两端过近，无法生成端部回弯。");
            foreach(double station in plan.Stations)HandrailCalculator.Node(piece.At(station/piece.Length),piece.Direction(station/piece.Length),p);
            plan.Materials=HandrailCalculator.Inventory(plan);plan.Number="围栏-螺旋-类型"+(int)p.Connection;return plan;
        }
    }
}
