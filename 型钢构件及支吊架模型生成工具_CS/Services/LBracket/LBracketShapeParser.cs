using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>将两条直线规范化为立杆端、拐点和横担端；不依赖 Bentley。</summary>
    internal static class LBracketShapeParser
    {
        internal static LBracketSelection Parse(IList<LBracketPoint[]> segments)
        {
            if(segments==null||segments.Count!=2||segments[0]==null||segments[1]==null||
                segments[0].Length!=2||segments[1].Length!=2)
                throw new InvalidOperationException("请选择由一竖一横两段直线组成的 L 形折线。");
            LBracketPoint corner=new LBracketPoint(),first=new LBracketPoint(),second=new LBracketPoint();
            bool found=false;
            for(int i=0;i<2&&!found;i++)for(int j=0;j<2&&!found;j++)
                if(Distance(segments[0][i],segments[1][j])<=0.5)
                {corner=Mid(segments[0][i],segments[1][j]);first=segments[0][1-i];
                    second=segments[1][1-j];found=true;}
            if(!found)throw new InvalidOperationException("L 形折线的两段没有共用拐点。");
            bool firstVertical=Vertical(corner,first),secondVertical=Vertical(corner,second);
            bool firstHorizontal=Horizontal(corner,first),secondHorizontal=Horizontal(corner,second);
            LBracketPoint post,arm;
            if(firstVertical&&secondHorizontal){post=first;arm=second;}
            else if(secondVertical&&firstHorizontal){post=second;arm=first;}
            else throw new InvalidOperationException("L 形折线须一段竖直、一段水平，偏角均不超过 5°。");
            double h=Math.Abs(post.Z-corner.Z);
            double dx=arm.X-corner.X,dy=arm.Y-corner.Y,l=Math.Sqrt(dx*dx+dy*dy);
            if(h<150||l<150)throw new InvalidOperationException("H 和 L 均须不小于 150 mm。");
            return new LBracketSelection {Corner=corner,PostEnd=post,ArmEnd=arm,
                HeightMm=h,LengthMm=l,RunX=dx/l,RunY=dy/l};
        }
        private static bool Vertical(LBracketPoint a,LBracketPoint b)
        {double xy=Math.Sqrt((a.X-b.X)*(a.X-b.X)+(a.Y-b.Y)*(a.Y-b.Y));
            return Math.Abs(a.Z-b.Z)>1e-9&&Math.Atan2(xy,Math.Abs(a.Z-b.Z))<=5*Math.PI/180;}
        private static bool Horizontal(LBracketPoint a,LBracketPoint b)
        {double xy=Math.Sqrt((a.X-b.X)*(a.X-b.X)+(a.Y-b.Y)*(a.Y-b.Y));
            return xy>1e-9&&Math.Atan2(Math.Abs(a.Z-b.Z),xy)<=5*Math.PI/180;}
        private static double Distance(LBracketPoint a,LBracketPoint b)
        {double x=a.X-b.X,y=a.Y-b.Y,z=a.Z-b.Z;return Math.Sqrt(x*x+y*y+z*z);}
        private static LBracketPoint Mid(LBracketPoint a,LBracketPoint b)
        {return new LBracketPoint((a.X+b.X)/2,(a.Y+b.Y)/2,(a.Z+b.Z)/2);}
    }
}
