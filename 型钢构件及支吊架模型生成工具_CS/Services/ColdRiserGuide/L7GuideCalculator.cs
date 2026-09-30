using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class L7GuideCalculator
    {
        internal static L7GuidePlan Calculate(int dn,double outside,double cold,double length,
            double angle,string pipeNumber)
        {return Calculate(dn,outside,cold,length,angle,pipeNumber,
            L7GuideCatalog.DefaultBearingLengthMm);}

        internal static L7GuidePlan Calculate(int dn,double outside,double cold,double length,
            double angle,string pipeNumber,double bearingLength)
        {return Calculate(L7GuideKind.Type1,dn,outside,cold,length,angle,pipeNumber,
            bearingLength);}

        internal static L7GuidePlan Calculate(L7GuideKind kind,int dn,double outside,
            double cold,double length,double angle,string pipeNumber,double bearingLength)
        {return Calculate(ColdRiserGuideSeries.L7,kind,dn,outside,cold,length,angle,pipeNumber,bearingLength,"C1");}

        internal static L7GuidePlan Calculate(ColdRiserGuideSeries series,L7GuideKind kind,int dn,
            double outside,double cold,double length,double angle,string pipeNumber,double bearingLength,string materialCode)
        {
            if(!Enum.IsDefined(typeof(ColdRiserGuideSeries),series)||!Enum.IsDefined(typeof(L7GuideKind),kind))
                throw new InvalidOperationException("导向架系列或类型无效。");
            string code=series.ToString();
            double load=L7GuideCatalog.AllowableLoad(dn);
            string material=L7GuideCatalog.Material(materialCode);
            if(dn<15||dn>150)
                throw new InvalidOperationException(code+" 仅适用于 DN15～DN150（1/2\"～6\"）。");
            if((series==ColdRiserGuideSeries.L8 || kind==L7GuideKind.Type1) && (double.IsNaN(length)||double.IsInfinity(length)))
                throw new InvalidOperationException("构件 A 长度 L 无效。");
            if(double.IsNaN(angle)||double.IsInfinity(angle))
                throw new InvalidOperationException("安装方位角无效。");
            bool type2=series==ColdRiserGuideSeries.L7 && kind==L7GuideKind.Type2;
            bool equipment=series==ColdRiserGuideSeries.L8 && kind==L7GuideKind.Type2;
            N8Plan connection=null;
            var clamp=A22ClampCalculator.Calculate(dn,outside,cold,type2?"A24":"A22",type2);
            var bearing=T4ShoeCalculator.BuildLayout(new T4ShoeParameters {
                Dn=dn,InsulationMm=cold,LengthMm=bearingLength,Name=code});
            // 使用读取到的真实外径；T4 表只决定板厚、耳板、孔位与螺栓规格。
            bearing.OutsideMm=outside;
            bearing.PipeRadiusMm=outside/2;
            bearing.InsulationRadiusMm=outside/2+cold;
            bearing.InsulationOdMm=2*bearing.InsulationRadiusMm;
            bearing.ClampOuterRadiusMm=bearing.InsulationRadiusMm+bearing.T3Mm;
            bearing.ShoeBottomZMm=-(bearing.PipeRadiusMm+bearing.HeightMm);
            bearing.BaseTopZMm=bearing.ShoeBottomZMm+bearing.T1Mm;
            bearing.TopPlateTopZMm=-bearing.ClampOuterRadiusMm;
            var bearingBoolean=T4ShoeCalculator.BuildBearingBooleanLayout(bearing);
            string family="",profile="",label="";
            double l=0,start=0;
            if(!type2)
            {
                if(equipment) {
                    int plateType=L7GuideCatalog.EquipmentMember(clamp.A,out family,out profile,out label);
                    connection=N8Catalog.Resolve(plateType,"N",0,G2MountFace.Wall);
                }
                else L7GuideCatalog.Member(clamp.A,out family,out profile,out label);
                l=Math.Max(L7GuideCatalog.MinLengthMm,
                    Math.Min(L7GuideCatalog.MaxLengthMm,length));
                start=clamp.OuterRadiusMm-2;
                if(l-start-(connection==null?0:connection.T)<20)
                    throw new InvalidOperationException("管夹外径及保冷厚度过大，当前 L 容不下构件 A；请减小保冷厚度或增大 L。");
            }
            double normalized=(angle%360+360)%360;
            string number="L7-"+(type2?"2":"1")+"-DN"+dn.ToString(CultureInfo.InvariantCulture)+"-"+
                cold.ToString("0.#",CultureInfo.InvariantCulture)+"-"+
                (type2?bearingLength:l).ToString("0.#",CultureInfo.InvariantCulture);
            if(series==ColdRiserGuideSeries.L8)
                number=code+"-"+(kind==L7GuideKind.Type2?"2":"1")+"-DN"+dn+"-"+
                    cold.ToString("0.#",CultureInfo.InvariantCulture)+"-"+
                    bearingLength.ToString("0.#",CultureInfo.InvariantCulture)+"-"+materialCode+"-"+
                    l.ToString("0.#",CultureInfo.InvariantCulture);
            return new L7GuidePlan {Series=series,Connection=connection,AllowableLoadKn=load,
                MaterialCode=materialCode,Kind=kind,Clamp=clamp,Bearing=bearing,
                BearingBoolean=bearingBoolean,LengthMm=l,AngleDeg=normalized,
                BearingLengthMm=bearingLength,
                MemberStartMm=start,MemberLengthMm=type2?0:l-start-(connection==null?0:connection.T),MemberFamily=family,
                MemberProfile=profile,MemberLabel=label,Number=number,
                Specification="DN"+dn+" / 保冷 "+cold.ToString("0.#",CultureInfo.InvariantCulture)+
                    " / "+clamp.Code+" A="+clamp.A.ToString("0.#",CultureInfo.InvariantCulture)+
                    " / 夹板长 "+bearingLength.ToString("0.#",CultureInfo.InvariantCulture)+
                    (type2?" / 四螺栓，无构件A":
                        " / 构件A "+label+" / "+(series==ColdRiserGuideSeries.L8?"L1":"L")+"="+l.ToString("0.#",CultureInfo.InvariantCulture))+
                    (series==ColdRiserGuideSeries.L8?" / 材料 "+materialCode+"："+material+" / 允许荷载 "+load.ToString("0.##",CultureInfo.InvariantCulture)+" kN":"")+
                    (equipment?" / "+connection.Number:""),
                PipeNumber=pipeNumber??""};
        }
    }
}
