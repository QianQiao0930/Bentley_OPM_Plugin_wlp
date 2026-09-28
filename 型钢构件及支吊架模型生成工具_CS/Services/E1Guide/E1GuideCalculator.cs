using System;
using System.Globalization;
namespace SteelSectionProbe
{
    internal static class E1GuideCalculator
    {
        internal static E1GuidePlan Calculate(int dn,string itemKey,bool stainless,string material,
            double sx,double sy,double sz,double ex,double ey,double ez,
            double clickX,double clickY,double clickZ,string pipeNumber,ulong sourceId,bool isAuxiliaryLine)
        {
            double dx=ex-sx,dy=ey-sy,dz=ez-sz;
            double horizontal=Math.Sqrt(dx*dx+dy*dy);
            if(horizontal<1e-6)throw new InvalidOperationException("请选择有明确轴线的管道或直线段。");
            if(Math.Abs(dz)>horizontal*Math.Tan(30*Math.PI/180))
                throw new InvalidOperationException("E1 导向架仅适用于坡度不超过 30° 的直线段。");
            var item=string.IsNullOrEmpty(itemKey)?E1GuideCatalog.AutomaticItem(dn):E1GuideCatalog.Item(itemKey);
            double od=E1GuideCatalog.Outside(dn);
            double ux=dx/horizontal,uy=dy/horizontal;
            double t=((clickX-sx)*dx+(clickY-sy)*dy+(clickZ-sz)*dz)/
                (dx*dx+dy*dy+dz*dz);
            t=Math.Max(0,Math.Min(1,t));
            double height=od<88.9?50:Math.Floor(od/2+50+0.5);
            return new E1GuidePlan { Item=item,Dn=dn,OutsideMm=od,HeightMm=height,
                FaceMm=od/2+3+(stainless?item.LinerThicknessMm:0),
                CenterXmm=sx+t*dx,CenterYmm=sy+t*dy,
                CenterZmm=sz+t*dz,PipeX=ux,PipeY=uy,AwayX=-uy,AwayY=ux,
                Stainless=stainless,Material=string.IsNullOrWhiteSpace(material)?"Q235B":material.Trim(),
                Number="E1-"+item.Key+"-"+height.ToString("0",CultureInfo.InvariantCulture)+(stainless?"-S":""),
                PipeNumber=pipeNumber??"",SourceId=sourceId,IsAuxiliaryLine=isAuxiliaryLine };
        }
    }
}
