using System;
using System.Globalization;
namespace SteelSectionProbe
{
    internal static class Q1SupportCalculator
    {
        internal static Q1SupportPlan Calculate(int type,int smallDn,int bigDn,double heightMm,
            bool mirrored,string pipeNumber,double? outsideMm=null,double? insulationMm=null)
        {
            if(type<1||type>4)throw new InvalidOperationException("Q1 类型须为 1～4。");
            if(double.IsNaN(heightMm)||double.IsInfinity(heightMm)||heightMm<=0||heightMm>1000)
                throw new InvalidOperationException("中心间距 H 须大于 0 且不超过 1000 mm。");
            string item=Q1SupportCatalog.Subitem(smallDn);
            if(bigDn<=smallDn)throw new InvalidOperationException("支撑大管的公称直径须大于被支撑小管。");
            if(insulationMm.HasValue&&(double.IsNaN(insulationMm.Value)||double.IsInfinity(insulationMm.Value)||insulationMm.Value<0||insulationMm.Value>0))
                throw new InvalidOperationException("Q1 适用于不保温管，请选择无保温的支撑管。");
            var big=A1ClampCalculator.Calculate(bigDn,false,null,0,pipeNumber);
            var small=A1ClampCalculator.Calculate(smallDn,false,null,0,pipeNumber);
            if(outsideMm.HasValue&&(double.IsNaN(outsideMm.Value)||double.IsInfinity(outsideMm.Value)||outsideMm.Value<=0||
                Math.Abs(outsideMm.Value-big.Row.OutsideMm)>2))
                throw new InvalidOperationException("大管实际外径与 A1 标准管卡不匹配。");
            string profileName=Q1SupportCatalog.ProfileName(item);
            var profile=ProfileLookup.Profile(RuntimeData.Families,"equal_angle",profileName);
            if(profile==null)throw new InvalidOperationException("型钢目录缺少 "+profileName+"。");
            double size=profile.Dimensions["B"],thickness=profile.Dimensions["t"];
            double sy=(type==1||type==4?-1:1)*heightMm;
            // 图纸端距从最外侧管卡腿中心量起，各 50 mm。
            double low=Math.Min(-big.Row.C/2.0,sy-small.Row.C/2.0)-50;
            double high=Math.Max(big.Row.C/2.0,sy+small.Row.C/2.0)+50;
            if(heightMm<=(big.Row.OutsideMm+small.Row.OutsideMm)/2+Math.Max(big.Row.Bolt,small.Row.Bolt))
                throw new InvalidOperationException("H 太小，两管及管卡无法留出安装间隙。");
            bool parallel=type>=3;
            // Q1 按贴管安装面定位，不沿用独立 A1 管卡直腿中部的螺母站位。
            double gap=Q1SupportCatalog.PipeWallGapMm;
            big.NutCenterMm=big.Row.OutsideMm/2+gap+thickness/2;
            small.NutCenterMm=small.Row.OutsideMm/2+gap+thickness/2;
            double cornerZ=big.NutCenterMm-thickness/2,cornerX=-size/2;
            double sx=parallel?0:cornerX+thickness/2-small.NutCenterMm;
            double sz=parallel?big.NutCenterMm-small.NutCenterMm:cornerZ+size/2;
            double padThickness=parallel?small.NutCenterMm-thickness/2-small.Row.OutsideMm/2:0;
            MountGap(big,thickness);MountGap(small,thickness);
            string number="Q1-"+type+"-"+item+"-DN"+bigDn+"-DN"+smallDn+"-"+heightMm.ToString("0.###",CultureInfo.InvariantCulture);
            return new Q1SupportPlan{Type=type,SmallDn=smallDn,BigDn=bigDn,HeightMm=heightMm,
                Mirrored=mirrored,
                LowMm=low,LengthMm=high-low,SizeMm=size,ThicknessMm=thickness,LoadKn=Q1SupportCatalog.Load(item),
                SmallXmm=sx,SmallYmm=sy,SmallZmm=sz,CornerXmm=cornerX,CornerZmm=cornerZ,Parallel=parallel,
                PadThicknessMm=padThickness,PadSizeMm=2*small.Row.Bolt,Subitem=item,ProfileName=profileName,
                Section=Q1SupportCatalog.Section(item),Number=number,PipeNumber=pipeNumber??"",BigClamp=big,SmallClamp=small,
                Specification="类型 "+type+" · "+Q1SupportCatalog.Section(item)+" · 大管 DN"+bigDn+" / 小管 DN"+smallDn+
                    " · H="+heightMm.ToString("0.###",CultureInfo.InvariantCulture)+" mm"+(mirrored?" · 镜像":"")};
        }
        internal static void Axes(double[] axis,bool mirrored,out double[] x,out double[] y,out double[] z)
        {
            A1ClampCalculator.RadialFrame(axis,out y,out z,out x);
            if(mirrored)for(int i=0;i<3;i++)z[i]=-z[i];
        }
        private static void MountGap(A1ClampPlan clamp,double thickness)
        {
            double nearFace=clamp.NutCenterMm-thickness/2;
            clamp.NutCenterMm=nearFace;
            clamp.NutLow1Mm=nearFace-clamp.NutHeightMm;
            clamp.NutLow2Mm=nearFace+thickness;
            double tip=clamp.NutLow2Mm+clamp.NutHeightMm+Math.Max(3,clamp.Row.Bolt/2.0);
            if(clamp.NutLow1Mm<=0||tip>clamp.Row.D)
                throw new InvalidOperationException("Q1 管卡无法满足贴管安装的螺母及直腿净空。");
            clamp.StraightLegMm=tip;
            clamp.BoltLengthMm=Math.PI*clamp.Row.C/2+2*tip;
            clamp.BoltSpecification="M"+clamp.Row.Bolt+"（C="+clamp.Row.C+"，直腿 D="+
                tip.ToString("0.###",CultureInfo.InvariantCulture)+"，展开长 "+
                clamp.BoltLengthMm.ToString("0.###",CultureInfo.InvariantCulture)+" mm）";
        }
    }
}
