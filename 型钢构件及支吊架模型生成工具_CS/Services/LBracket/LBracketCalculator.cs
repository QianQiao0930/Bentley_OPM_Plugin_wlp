using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class LBracketCalculator
    {
        internal static LBracketPlan Calculate(LBracketParameters p,LBracketSelection s)
        {
            if(p==null||s==null)throw new InvalidOperationException("请先选择 L 形辅助线。");
            var v=LBracketCatalog.Require(p.Variant);
            if(p.Type<1||p.Type>4)throw new InvalidOperationException("类型应为 1～4。");
            if(p.Variant>='E'&&(p.Type==2||p.Type==4))
                throw new InvalidOperationException("子项 "+p.Variant+" 仅允许类型 1 或 3。");
            if(!Finite(s.HeightMm)||s.HeightMm<150||!Finite(s.LengthMm)||s.LengthMm<150)
                throw new InvalidOperationException("立杆高 H 和横担长 L 均须不小于 150 mm。");
            bool hanger=p.Type>=3;
            if(hanger?s.PostEnd.Z<=s.Corner.Z:s.PostEnd.Z>=s.Corner.Z)
                throw new InvalidOperationException(hanger?"类型 3/4 要求立杆在拐点上方。":"类型 1/2 要求立杆在拐点下方。");
            if(!Finite(p.WidthMm)||p.WidthMm<=0)
                throw new InvalidOperationException("B 应为正数。");
            if(s.HeightMm>v.MaxHeightMm+1)
                throw new InvalidOperationException("H 当前 "+F(s.HeightMm)+" mm，标准上限 "+F(v.MaxHeightMm)+" mm。");
            if(p.WidthMm>v.MaxWidthMm)
                throw new InvalidOperationException("B 当前 "+F(p.WidthMm)+" mm，标准上限 "+F(v.MaxWidthMm)+" mm。");
            double postCut,armCut;
            if(v.Family=="equal_angle")
            {postCut=hanger?s.HeightMm+v.HeightMm:s.HeightMm-v.ThicknessMm;
                armCut=s.LengthMm+v.CentroidMm+15;}
            else if(v.Family=="parallel_channel")
            {postCut=hanger?s.HeightMm+v.HeightMm:s.HeightMm-v.ThicknessMm;
                armCut=s.LengthMm+v.HeightMm/2+15;}
            else
            {postCut=hanger?s.HeightMm:s.HeightMm-v.HeightMm;
                armCut=s.LengthMm+v.HeightMm/2+15;}
            if(postCut<=0)throw new InvalidOperationException("立杆下料长度不足，请增大 H。");
            var plan=new LBracketPlan {Parameters=p,Selection=s,Variant=v,
                PostCutLengthMm=postCut,ArmCutLengthMm=armCut,
                Specification=v.Specification+" 立杆 + 横担"};
            string name=(p.Name??"").Trim();
            plan.Number=name.Length==0?"":name+"-"+p.Type+"-"+p.Variant+"-"+
                Round(s.HeightMm)+"-"+Round(s.LengthMm);
            int h=-1,b=-1;
            for(int i=0;i<v.HeightColumns.Length;i++)
                if(v.HeightColumns[i]<=s.HeightMm+1)h=i;
            for(int i=0;i<v.WidthColumns.Length;i++)
                if(p.WidthMm<=v.WidthColumns[i]){b=i;break;}
            if(h>=0&&b>=0)
            {plan.UsedHeightMm=v.HeightColumns[h];plan.UsedWidthMm=v.WidthColumns[b];
                plan.AllowableLoadKn=v.Loads[h][b];}
            return plan;
        }
        private static bool Finite(double v){return !double.IsNaN(v)&&!double.IsInfinity(v);}
        private static string F(double v){return v.ToString("0.#",CultureInfo.InvariantCulture);}
        private static int Round(double v){return (int)Math.Floor(v+0.5);}
    }
}
