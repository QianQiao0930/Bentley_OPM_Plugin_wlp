using System;
using System.Collections.Generic;
using System.Linq;
namespace SteelSectionProbe
{
    /// <summary>迁移 steel_handrail.py 的纯毫米路径、排柱及节点计算。</summary>
    internal static class HandrailCalculator
    {
        private const double Tol=HandrailCatalog.Tolerance;
        internal static HandrailPlan CalculateArc(HandrailParameters p,HandrailArcInput input)
        {
            if(input!=null&&input.MixedPoints!=null)return Calculate(p,input.MixedPoints,true);
            if(input!=null&&input.IsHelix)return HandrailHelixCalculator.Calculate(p,input);
            if(p==null||input==null)throw new InvalidOperationException("缺少圆弧参数。");
            // 复用既有参数校验，不将采样线用于实际建模。
            Calculate(p,new[]{new HandrailPoint(0,0,0),new HandrailPoint(3000,0,0)});
            var u=input.Vector0;var v=input.Vector90;
            double r=u.Length;
            if(!Finite(r)||!Finite(v.Length)||!Finite(input.StartAngle)||!Finite(input.SweepAngle)
                ||!Finite(input.Center.X)||!Finite(input.Center.Y)||!Finite(input.Center.Z)
                ||r<=Tol||Math.Abs(r-v.Length)>Tol||Math.Abs(HandrailPoint.Dot(u,v))>Tol*r)
                throw new InvalidOperationException("只支持圆形圆弧，不支持椭圆或无效圆弧。");
            if(Math.Abs(u.Z)>Tol||Math.Abs(v.Z)>Tol)throw new InvalidOperationException("只支持水平圆弧。");
            double angle=Math.Abs(input.SweepAngle);
            if(angle<1e-7||angle>=2*Math.PI-1e-7)throw new InvalidOperationException("请选择非闭合圆弧。");
            double a=input.StartAngle+(p.Reverse?input.SweepAngle:0);
            double direction=Math.Sign(input.SweepAngle)*(p.Reverse?-1:1);
            var radial=(u*Math.Cos(a)+v*Math.Sin(a))*(1/r);
            var tangent=(u*(-Math.Sin(a))+v*Math.Cos(a))*(direction/r);
            double sign=HandrailPoint.Cross(radial,tangent).Z>0?1:-1;
            double radius=r-sign*p.Side*HandrailCatalog.PathOffset;
            double kickRadius=radius-sign*p.Side*HandrailCatalog.KickOffset;
            if(Math.Min(radius,kickRadius)<140-Tol)
                throw new InvalidOperationException("偏移后围栏及踢脚板中心半径不得小于 140 mm。");
            var origin=input.Center+radial*r;
            var piece=new HandrailPiece{IsArc=true,Center=input.Center-origin,Radial=radial,Tangent=tangent,
                Radius=radius,Angle=angle,TurnSign=sign,Length=radius*angle};
            piece.Start=piece.At(0);piece.End=piece.At(1);
            var plan=new HandrailPlan{Origin=origin,LengthMm=piece.Length,Parameters=new HandrailParameters{
                Side=p.Side,Reverse=p.Reverse,Connection=p.Connection,Closure=p.Closure,StructureOffsetMm=p.StructureOffsetMm,MaxPostSpacingMm=p.MaxPostSpacingMm}};
            plan.Pieces.Add(piece);plan.Stations=PostStations(plan.LengthMm,plan.Corners,plan.Parameters.MaxPostSpacingMm);
            plan.Kickplate=OffsetPieces(plan.Pieces,p.Side,HandrailCatalog.KickOffset);
            // 按连接节点包络保守限制柱间及端部间距，避免小半径与近整圈相撞。
            double clearance=p.Connection==HandrailConnection.Type2?Math.Max(146,p.StructureOffsetMm+38):146;
            for(int i=0;i<plan.Stations.Count;i++)for(int j=i+1;j<plan.Stations.Count;j++)
                if((piece.At(plan.Stations[i]/plan.LengthMm)-piece.At(plan.Stations[j]/plan.LengthMm)).Length<clearance)
                    throw new InvalidOperationException("圆弧立柱间距过小或两端过近，连接节点可能重叠。");
            if(p.Closure!=HandrailClosure.None&&(piece.Start-piece.End).Length<2*(300+21.2)+clearance)
                throw new InvalidOperationException("圆弧两端过近，不能生成端部回弯，请关闭端部闭合或增大间距。");
            foreach(double station in plan.Stations)Node(piece.At(station/plan.LengthMm),piece.Direction(station/plan.LengthMm),p);
            plan.Materials=Inventory(plan);plan.Number="围栏-圆弧-类型"+(int)p.Connection;
            return plan;
        }
        internal static List<HandrailPoint> Clean(IList<HandrailPoint> points,bool spatial=false)
        {
            if(points==null||points.Count<2)throw new InvalidOperationException("路径至少需要两个不同顶点。");
            var p=new List<HandrailPoint>();
            foreach(var q in points){if(!Finite(q.X)||!Finite(q.Y)||!Finite(q.Z))throw new InvalidOperationException("路径坐标无效。");
                if(p.Count==0||(q-p[p.Count-1]).Length>Tol)p.Add(q);}
            if(p.Count<2)throw new InvalidOperationException("路径长度必须大于零。");
            if((p[0]-p[p.Count-1]).Length<=Tol)throw new InvalidOperationException("暂不支持闭合围栏路径。");
            for(int i=1;i<p.Count;i++)if((p[i]-p[i-1]).HorizontalLength<=Tol)
                throw new InvalidOperationException("路径含竖直段，无法确定围栏内外侧。");
            for(int i=0;i<p.Count-1;i++)for(int j=i+2;j<p.Count-1;j++)
                if(spatial?SegmentsTouch3d(p[i],p[i+1],p[j],p[j+1]):Intersect(p[i],p[i+1],p[j],p[j+1]))throw new InvalidOperationException("路径存在自交或重叠，请先整理辅助线。");
            return p;
        }
        private static bool Finite(double x){return !double.IsNaN(x)&&!double.IsInfinity(x);}
        private static double PointSegmentDistance(HandrailPoint p,HandrailPoint a,HandrailPoint b)
        {var v=b-a;double t=Math.Max(0,Math.Min(1,HandrailPoint.Dot(p-a,v)/HandrailPoint.Dot(v,v)));return (p-a-v*t).Length;}
        private static bool SegmentsTouch3d(HandrailPoint a,HandrailPoint b,HandrailPoint c,HandrailPoint d)
        {
            if(Math.Min(Math.Min(PointSegmentDistance(a,c,d),PointSegmentDistance(b,c,d)),
                        Math.Min(PointSegmentDistance(c,a,b),PointSegmentDistance(d,a,b)))<=Tol)return true;
            var u=b-a;var v=d-c;var w=a-c;
            double aa=HandrailPoint.Dot(u,u),bb=HandrailPoint.Dot(u,v),cc=HandrailPoint.Dot(v,v),
                   dd=HandrailPoint.Dot(u,w),ee=HandrailPoint.Dot(v,w),denominator=aa*cc-bb*bb;
            if(denominator<=1e-12*aa*cc)return false;
            double s=(bb*ee-cc*dd)/denominator,t=(aa*ee-bb*dd)/denominator;
            return s>=0&&s<=1&&t>=0&&t<=1&&(w+u*s-v*t).Length<=Tol;
        }
        private static double Cross2(HandrailPoint a,HandrailPoint b,HandrailPoint c)
        {return (b.X-a.X)*(c.Y-a.Y)-(b.Y-a.Y)*(c.X-a.X);}
        private static bool On(HandrailPoint p,HandrailPoint a,HandrailPoint b)
        {return Math.Abs(Cross2(a,b,p))<=Tol*Math.Max(1,(b-a).HorizontalLength)&&
            p.X>=Math.Min(a.X,b.X)-Tol&&p.X<=Math.Max(a.X,b.X)+Tol&&
            p.Y>=Math.Min(a.Y,b.Y)-Tol&&p.Y<=Math.Max(a.Y,b.Y)+Tol;}
        private static bool Intersect(HandrailPoint a,HandrailPoint b,HandrailPoint c,HandrailPoint d)
        {return Cross2(a,b,c)*Cross2(a,b,d)<0&&Cross2(c,d,a)*Cross2(c,d,b)<0||On(a,c,d)||On(b,c,d)||On(c,a,b)||On(d,a,b);}
        internal static List<HandrailPoint> OffsetPoints(IList<HandrailPoint> points,int side,double offset,bool spatial=false)
        {
            var p=Clean(points,spatial);var result=new List<HandrailPoint>();
            result.Add(p[0]+(p[1]-p[0]).Normal(side)*offset);
            for(int i=1;i<p.Count-1;i++){
                var incoming=p[i]-p[i-1];var outgoing=p[i+1]-p[i];
                var u=incoming.Horizontal();var v=outgoing.Horizontal();
                double turn=u.X*v.Y-u.Y*v.X;
                var a=p[i]+u.Normal(side)*offset;
                if(Math.Abs(turn)<1e-12){if(HandrailPoint.Dot(u,v)<0)throw new InvalidOperationException("路径含 180° 折返。");result.Add(a);continue;}
                if(!spatial&&(Math.Abs(incoming.Z/incoming.HorizontalLength)>1e-9||Math.Abs(outgoing.Z/outgoing.HorizontalLength)>1e-9))
                    throw new InvalidOperationException("同一折点同时转向和变坡，暂不生成空间弯头。");
                var b=p[i]+v.Normal(side)*offset;var delta=b-a;
                double advance=(delta.X*v.Y-delta.Y*v.X)/turn;
                if(spatial&&Math.Abs(advance)>4*Math.Abs(offset)+Tol)throw new InvalidOperationException("空间路径转角过尖，横向偏移斜接过长。");
                result.Add(a+u*advance);
            }
            result.Add(p[p.Count-1]+(p[p.Count-1]-p[p.Count-2]).Normal(side)*offset);
            return result;
        }
        internal static HandrailPlan Calculate(HandrailParameters parameters,IList<HandrailPoint> vertices,bool spatial=false)
        {
            if(parameters==null)throw new ArgumentNullException("parameters");
            if(parameters.Side!=1&&parameters.Side!=-1)throw new InvalidOperationException("踢脚板侧向应为左侧或右侧。");
            if(!Enum.IsDefined(typeof(HandrailConnection),parameters.Connection)||!Enum.IsDefined(typeof(HandrailClosure),parameters.Closure))
                throw new InvalidOperationException("立柱连接类型或端部闭合方式无效。");
            if(!Finite(parameters.StructureOffsetMm)||parameters.Connection==HandrailConnection.Type2&&parameters.StructureOffsetMm<=83+Tol)
                throw new InvalidOperationException("类型 2 的立柱中心至连接板距离必须大于 83 mm。");
            var raw=Clean(vertices,spatial);if(parameters.Reverse)raw.Reverse();
            var origin=raw[0];raw=raw.Select(q=>q-origin).ToList();
            var plan=BuildPath(OffsetPoints(raw,parameters.Side,HandrailCatalog.PathOffset,spatial),spatial);
            plan.IsSpatialMixed=spatial;
            plan.Origin=origin;
            // 保存参数快照，后续 UI 修改不影响已创建预览的统计。
            plan.Parameters=new HandrailParameters{Connection=parameters.Connection,Closure=parameters.Closure,
                Side=parameters.Side,Reverse=parameters.Reverse,StructureOffsetMm=parameters.StructureOffsetMm,MaxPostSpacingMm=parameters.MaxPostSpacingMm};
            plan.Stations=PostStations(plan.LengthMm,plan.Corners,plan.Parameters.MaxPostSpacingMm);
            plan.Kickplate=spatial?SpatialKickPath(plan.Pieces,parameters.Side):OffsetPieces(plan.Pieces,parameters.Side,HandrailCatalog.KickOffset);
            if(spatial&&plan.Stations.Count>2000)throw new InvalidOperationException("混合路径立柱超过2000根，请拆分路径。");
            // 建模前验证所有节点，避免进入实体创建后才发现坡段压扁过渡无效。
            foreach(double station in plan.Stations){HandrailPoint point,tangent;At(plan.Pieces,station,out point,out tangent);Node(point,tangent,plan.Parameters);}
            plan.Materials=Inventory(plan);
            plan.Number=(spatial?"围栏-混合空间路径-类型":"围栏-类型")+(int)parameters.Connection+"-"+plan.LengthMm.ToString("0.#",System.Globalization.CultureInfo.InvariantCulture);
            return plan;
        }
        internal static HandrailPlan BuildPath(IList<HandrailPoint> points,bool spatial=false)
        {
            var p=Clean(points,spatial);int n=p.Count;
            var arcs=new HandrailPiece[n];var distances=new double[n];var grade=new bool[n];
            for(int i=1;i<n-1;i++){
                var a=p[i]-p[i-1];var b=p[i+1]-p[i];var u=a.Horizontal();var v=b.Horizontal();
                double angle=Math.Acos(Math.Max(-1,Math.Min(1,HandrailPoint.Dot(u,v))));
                if(angle<1e-7){grade[i]=Math.Abs(a.Z/a.HorizontalLength-b.Z/b.HorizontalLength)>1e-9;continue;}
                if(Math.Abs(Math.PI-angle)<1e-5)throw new InvalidOperationException("路径含 180° 折返，无法生成 R140 转角。");
                // 混合圆弧的求值点是曲线逼近顶点，不能把每点都当成需设柱的转角。
                if(spatial&&angle<=Math.PI/12&&Math.Abs(a.Z)<Tol&&Math.Abs(b.Z)<Tol)continue;
                if(Math.Abs(a.Z/a.HorizontalLength)>1e-9||Math.Abs(b.Z/b.HorizontalLength)>1e-9){
                    if(!spatial)throw new InvalidOperationException("同一折点同时转向和变坡，暂不生成空间弯头。");
                    if(angle>Math.PI/12)throw new InvalidOperationException("空间坡段急转超过15°，请用平滑曲线连接。");
                    grade[i]=Math.Abs(a.Z/a.HorizontalLength-b.Z/b.HorizontalLength)>.01;continue;}
                double d=140*Math.Tan(angle/2);if(d>300+Tol)throw new InvalidOperationException("转角过尖，R140 切点距离超过 300 mm。");
                double sign=u.X*v.Y-u.Y*v.X>0?1:-1;
                var start=p[i]-u*d;var center=start+u.Normal(1)*(140*sign);
                arcs[i]=new HandrailPiece{IsArc=true,Start=start,End=p[i]+v*d,Center=center,
                    Radial=(start-center)*(1/140.0),Tangent=u,Angle=angle,Length=140*angle,TurnSign=sign};
                distances[i]=d;
            }
            for(int i=0;i<n-1;i++)if(distances[i]+distances[i+1]>=(p[i+1]-p[i]).HorizontalLength-Tol)
                throw new InvalidOperationException("相邻转角距离过短，无法容纳 R140 圆角。");
            var plan=new HandrailPlan();var current=p[0];double station=0;
            for(int i=0;i<n-1;i++){
                var arc=arcs[i+1];var end=arc==null?p[i+1]:arc.Start;var delta=end-current;
                if(delta.Length>Tol){plan.Pieces.Add(new HandrailPiece{Start=current,End=end,Tangent=delta.Unit(),Length=delta.Length,StartStation=station});station+=delta.Length;}
                if(arc!=null){arc.StartStation=station;plan.Pieces.Add(arc);
                    plan.Corners.Add(new HandrailCorner{Station=station,TangentDistance=distances[i+1],ArcLength=arc.Length});
                    station+=arc.Length;current=arc.End;}
                else{current=end;if(grade[i+1])plan.Corners.Add(new HandrailCorner{GradeBreak=true,Station=station});}
            }
            plan.LengthMm=station;return plan;
        }
        private static List<HandrailPiece> SpatialKickPath(IList<HandrailPiece> pieces,int side)
        {
            var points=new List<HandrailPoint>{pieces[0].Start};
            foreach(var piece in pieces){int count=piece.IsArc?Math.Max(1,(int)Math.Ceiling(piece.Angle/.025)):1;
                for(int i=1;i<=count;i++)points.Add(piece.At(i/(double)count));}
            var shifted=OffsetPoints(points,side,HandrailCatalog.KickOffset,true);
            var result=new List<HandrailPiece>();double station=0;
            for(int i=1;i<shifted.Count;i++){var delta=shifted[i]-shifted[i-1];
                result.Add(new HandrailPiece{Start=shifted[i-1],End=shifted[i],Tangent=delta.Unit(),Length=delta.Length,StartStation=station});station+=delta.Length;}
            return result;
        }
        internal static void At(IList<HandrailPiece> pieces,double station,out HandrailPoint point,out HandrailPoint tangent)
        {
            foreach(var p in pieces)if(station<=p.EndStation+Tol){double f=Math.Max(0,Math.Min(1,(station-p.StartStation)/p.Length));point=p.At(f);tangent=p.Direction(f);return;}
            var last=pieces[pieces.Count-1];point=last.End;tangent=last.Direction(1);
        }
        internal static List<double> ModularSpans(double span,double maxSpacing=2000)
        {
            if(!Finite(maxSpacing)||maxSpacing<300||maxSpacing>2000)throw new InvalidOperationException("立柱最大间距须为 300～2000 mm。");
            if(span<=Tol)return new List<double>();
            int count=Math.Max(1,(int)Math.Ceiling(span/(Math.Floor(maxSpacing/50)*50)-1e-9));
            double step=Math.Floor((span/count+Tol)/50)*50;if(step<=0)return new List<double>{span};
            var lengths=Enumerable.Repeat(step,count).ToList();double remainder=span-step*count;
            int modules=(int)Math.Floor((remainder+Tol)/50);remainder-=modules*50;
            if(remainder<0&&Math.Abs(remainder)<=Tol)remainder=0;
            var order=new List<int>();for(int left=0,right=count-1;left<=right;left++,right--){order.Add(right);if(left!=right)order.Add(left);}
            foreach(int i in order)if(modules>0&&lengths[i]+50<=maxSpacing+Tol){lengths[i]+=50;modules--;}
            if(modules!=0)throw new InvalidOperationException("50 mm 模数余量无法分配。");
            if(remainder>Tol){bool done=false;foreach(int i in order)if(lengths[i]+remainder<=maxSpacing+Tol){lengths[i]+=remainder;done=true;break;}
                if(!done)throw new InvalidOperationException("非模数尾数无法分配。");}
            lengths[order[order.Count-1]]+=span-lengths.Sum();
            if(lengths.Any(x=>x<=Tol||x>maxSpacing+Tol))throw new InvalidOperationException("立柱跨距超出有效范围。");
            return lengths;
        }
        private static List<double> Merge(IEnumerable<double> values,double total)
        {
            var result=new List<double>();foreach(double x in values.Select(v=>Math.Max(0,Math.Min(total,v))).OrderBy(v=>v))
                if(result.Count==0||x-result[result.Count-1]>Tol)result.Add(x);return result;
        }
        internal static List<double> PostStations(double length,IList<HandrailCorner> corners,double maxSpacing=2000)
        {
            var controls=new List<double>{0,length};foreach(var c in corners){if(c.GradeBreak)controls.Add(c.Station);
                else{double extra=Math.Max(0,300-c.TangentDistance);controls.Add(c.Station-extra);controls.Add(c.Station+c.ArcLength+extra);}}
            controls=Merge(controls,length);var stations=new List<double>();
            for(int i=1;i<controls.Count;i++){double current=controls[i-1];stations.Add(current);var spans=ModularSpans(controls[i]-current,maxSpacing);
                for(int j=0;j<spans.Count;j++){current=j==spans.Count-1?controls[i]:current+spans[j];stations.Add(current);}}
            return Merge(stations,length);
        }
        internal static List<HandrailPiece> OffsetPieces(IList<HandrailPiece> pieces,int side,double offset)
        {
            var result=new List<HandrailPiece>();foreach(var p in pieces){
                if(!p.IsArc){var shift=p.Tangent.Normal(side)*offset;result.Add(new HandrailPiece{Start=p.Start+shift,End=p.End+shift,Tangent=p.Tangent,Length=p.Length});}
                else{double radius=p.Radius-p.TurnSign*side*offset;if(radius<=3+Tol)throw new InvalidOperationException("转角内侧半径不足，踢脚板扫掠会自交。");
                    var q=new HandrailPiece{IsArc=true,Center=p.Center,Radial=p.Radial,Tangent=p.Tangent,Angle=p.Angle,Radius=radius,TurnSign=p.TurnSign,Length=radius*p.Angle};
                    q.Start=q.At(0);q.End=q.At(1);result.Add(q);}}
            for(int i=1;i<result.Count;i++)if((result[i].Start-result[i-1].End).Length>Tol)throw new InvalidOperationException("踢脚板偏移路径不连续。");return result;
        }
        internal static HandrailNode Node(HandrailPoint point,HandrailPoint tangent,HandrailParameters p)
        {
            var normal=tangent.Normal(p.Side);var along=tangent.Unit();var shortAxis=HandrailPoint.Cross(normal,along);
            var node=new HandrailNode{Point=point,Tangent=tangent,Normal=normal,PlateLong=along,PlateShort=shortAxis,Bottom=point};
            if(p.Connection==HandrailConnection.Type3){node.Bottom=point+HandrailPoint.Up*10;return node;}
            if(p.Connection==HandrailConnection.Type2){node.ElbowCenter=point+normal*76;node.ElbowEnd=node.ElbowCenter-HandrailPoint.Up*76;
                node.PlateCenter=point+normal*p.StructureOffsetMm-HandrailPoint.Up*76;
                node.TubeEnd=point+normal*(p.StructureOffsetMm-3)-HandrailPoint.Up*76;return node;}
            if(p.Connection==HandrailConnection.Type1){node.PlateCenter=point+normal*(48.3/2+5)-HandrailPoint.Up*76;
                double halfHeight=double.PositiveInfinity;
                if(Math.Abs(along.Z)>1e-12)halfHeight=Math.Min(halfHeight,73/Math.Abs(along.Z));
                if(Math.Abs(shortAxis.Z)>1e-12)halfHeight=Math.Min(halfHeight,37.5/Math.Abs(shortAxis.Z));
                double bottom=node.PlateCenter.Z-halfHeight;if(point.Z-38.5<=bottom+Tol)throw new InvalidOperationException("类型 1 压扁过渡必须在连接板下缘上方结束。");
                var shift=normal*((48.3-16.1)/2);var flat=point+shift;
                node.Bottom=new HandrailPoint(flat.X,flat.Y,bottom);
                node.Sections.Add(new HandrailSection(point,24.15,24.15));
                node.Sections.Add(new HandrailSection(flat-HandrailPoint.Up*38.5,35,8.05));
                node.Sections.Add(new HandrailSection(node.Bottom,35,8.05));}
            return node;
        }
        internal static List<HandrailMaterial> Inventory(HandrailPlan p)
        {
            var items=new List<HandrailMaterial>();int count=p.Stations.Count;
            Action<string,string,string,double,int> add=(code,name,spec,l,q)=>items.Add(new HandrailMaterial{Code=code,Name=name,Specification=spec,LengthMm=l,Quantity=q});
            // 同角色管件采用总中心线长度，一道围栏仅写一个固定 ItemType，避免尺寸进入类型名。
            add("TOP_RAIL","顶部扶手","钢管 φ42.4×3.2",p.LengthMm,1);
            add("KNEE_RAIL","中间横杆","钢管 φ33.7×3.2",p.LengthMm,1);
            add("POST","立柱","钢管 φ48.3×3.2",p.Parameters.Connection==HandrailConnection.Type3?1007:1017,count);
            add("BALL","连接球","实心球 φ76",0,count*2);
            add("KICKPLATE","踢脚板","钢板 130×6",p.Kickplate.Sum(x=>x.Length),1);
            add("BRACKET","踢脚板支架","钢板 6×50",50,count);
            if(p.Parameters.Connection!=HandrailConnection.Type4)add("BASE_PLATE","底部连接板",
                p.Parameters.Connection==HandrailConnection.Type3?"钢板 145×75×10":"钢板 146×75×10",0,count);
            if(p.Parameters.Connection==HandrailConnection.Type1)add("FLATTEN_END","压扁端","钢管 φ48.3×3.2",113.5,count);
            if(p.Parameters.Connection==HandrailConnection.Type2)add("DOWN_BEND","立柱下弯段","钢管 φ48.3×3.2",Math.PI/2*76+p.Parameters.StructureOffsetMm-3-76,count);
            int ends=p.Parameters.Closure==HandrailClosure.None?0:p.Parameters.Closure==HandrailClosure.Both?2:1;
            if(ends>0)add("END_CLOSURE","端部闭合回弯","钢管 φ42.4×3.2",320+177+Math.PI*140,ends);
            return items;
        }
    }
}
