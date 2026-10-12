using System;
using System.Globalization;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class Q2SupportCalculator
    {
        internal static Q2SupportPlan Calculate(int type,string item,int smallDn,int bigDn,double length,
            bool mirror,bool guide,string pipe,double? outside=null,double? insulation=null)
        {
            if(type<1||type>4)throw new InvalidOperationException("Q2 类型须为1～4。");
            if(!Q2SupportCatalog.SmallDns.Contains(smallDn))throw new InvalidOperationException("Q2小管管径须为DN15～150。");
            if(bigDn<=smallDn)throw new InvalidOperationException("大管管径须大于小管。");
            double load=Q2SupportCatalog.Load(item,length);
            var big=A1ClampCalculator.Calculate(bigDn,false,null,0,pipe);
            var small=A1ClampCalculator.Calculate(smallDn,false,null,0,pipe);
            if(guide&&type==4)big.LegSpacingMm=big.Row.OutsideMm+big.Row.Bolt+6;
            if(guide&&type>=3)small.LegSpacingMm=small.Row.OutsideMm+small.Row.Bolt+6;
            if(insulation.HasValue&&insulation.Value!=0)throw new InvalidOperationException("Q2 请选择不保温的支撑大管。");
            if(outside.HasValue&&(double.IsNaN(outside.Value)||Math.Abs(outside.Value-big.Row.OutsideMm)>2))
                throw new InvalidOperationException("大管外径与A1管卡不匹配。");
            string name=Q1SupportCatalog.ProfileName(item);
            var profile=ProfileLookup.Profile(RuntimeData.Families,"equal_angle",name);
            if(profile==null)throw new InvalidOperationException("型钢目录缺少 "+name);
            double size=profile.Dimensions["B"],t=profile.Dimensions["t"],r=big.Row.OutsideMm/2;
            if(length<=(big.LegSpacingMm??big.Row.C)/2+small.Row.OutsideMm/2+2)
                throw new InvalidOperationException("L太小，小管与大管管卡安装区域重叠。");
            bool vertical=type==4;
            double top=vertical?size/2:-r-2;
            double cy=vertical?-r-(guide?3:2):size/2;
            double sy=type>=3?cy+small.Row.OutsideMm/2+(guide?3:2):0;
            var plan=new Q2SupportPlan{Type=type,BigDn=bigDn,SmallDn=smallDn,Subitem=item,
                LMm=length,LoadKn=load,SizeMm=size,ThicknessMm=t,Mirrored=mirror,Guide=guide,
                BigVertical=vertical,ProfileName=name,Section=Q1SupportCatalog.Section(item),PipeNumber=pipe??"",
                CornerYmm=cy,TopZmm=top,SmallYmm=sy,SmallZmm=type>=3?top-size/2:top+small.Row.OutsideMm/2,
                BigClamp=big,SmallClamp=type>=3?small:null,
                SmallStationsMm=type==1?new[]{-length,length}:new[]{length},
                SmallBlockMm=type>=3?Q2SupportCatalog.Block(smallDn):null};
            double end=length+(type<=2?150:(small.LegSpacingMm??small.Row.C)/2+50);
            plan.StartMm=type==1?-end:-(big.LegSpacingMm??big.Row.C)/2-50;
            plan.LengthMm=end-plan.StartMm;
            Mount(big,t,vertical,guide,vertical?r+(guide?3:2):r+2);
            if(plan.SmallClamp!=null)Mount(small,t,true,guide,small.Row.OutsideMm/2+(guide?3:2));
            plan.Number="Q2-"+type+"-"+item+"-DN"+bigDn+"-DN"+smallDn+"-"+length.ToString("0.###",CultureInfo.InvariantCulture);
            plan.Specification="类型 "+type+" · "+plan.Section+" · L="+length.ToString("0.###")+" mm · "+load.ToString("0.###")+" kN"+
                (type>=3?(guide?" · 立管承重/导向G":" · 立管承重/固定A"):"")+(mirror?" · 镜像":"");
            return plan;
        }
        private static void Mount(A1ClampPlan p,double t,bool vertical,bool guide,double near)
        {
            // 立管固定A：每腿两颗螺母同在外侧；导向G：每腿一内一外，管侧留3mm。
            if(vertical&&!guide){p.NutLow1Mm=near+t;p.NutCenterMm=p.NutLow1Mm+p.NutHeightMm;p.NutLow2Mm=p.NutCenterMm;}
            else{p.NutCenterMm=near;p.NutLow1Mm=near-p.NutHeightMm;p.NutLow2Mm=near+t;}
            double tip=p.NutLow2Mm+p.NutHeightMm+Math.Max(3,p.Row.Bolt/2.0);
            if(p.NutLow1Mm<=0)throw new InvalidOperationException("管卡螺母安装净空不足。");
            p.StraightLegMm=tip;p.BoltLengthMm=Math.PI*(p.LegSpacingMm??p.Row.C)/2+2*tip;
            p.BoltSpecification="M"+p.Row.Bolt+"（C="+(p.LegSpacingMm??p.Row.C).ToString("0.###")+"，D="+tip.ToString("0.###")+"，展开长 "+p.BoltLengthMm.ToString("0.###")+" mm）";
        }
        internal static void Axes(double[] axis,bool vertical,bool mirror,out double[] x,out double[] y,out double[] z,double angleDeg=0)
        {
            double norm=Math.Sqrt(axis[0]*axis[0]+axis[1]*axis[1]+axis[2]*axis[2]);
            if(double.IsNaN(norm)||double.IsInfinity(norm)||norm<1e-9)throw new InvalidOperationException("管轴无效。");
            if(vertical)
            {
                if(Math.Abs(axis[2])/norm<Math.Cos(5*Math.PI/180))throw new InvalidOperationException("Q2类型4须点取立管（偏离竖直不超过5°）。");
                double sign=axis[2]<0?-1:1;
                A1ClampCalculator.RadialFrame(new[]{sign*axis[0],sign*axis[1],sign*axis[2]},out x,out y,out z);
                if(double.IsNaN(angleDeg)||double.IsInfinity(angleDeg))throw new InvalidOperationException("布置角度无效。");
                double a=angleDeg*Math.PI/180,c=Math.Cos(a),s=Math.Sin(a);
                var oldX=x;var oldY=y;x=new double[3];y=new double[3];
                for(int i=0;i<3;i++){x[i]=c*oldX[i]+s*oldY[i];y[i]=-s*oldX[i]+c*oldY[i];}
                if(mirror)for(int i=0;i<3;i++)x[i]=-x[i];
            }
            else
            {
                if(Math.Abs(axis[2])/norm>Math.Sin(5*Math.PI/180))throw new InvalidOperationException("Q2类型1～3须点取水平大管（坡度不超过5°）。");
                double[] up,side,along;
                A1ClampCalculator.RadialFrame(axis,out up,out side,out along);
                y=along;z=up;x=side;
                if(mirror)for(int i=0;i<3;i++)x[i]=-x[i];
            }
        }
    }
}
