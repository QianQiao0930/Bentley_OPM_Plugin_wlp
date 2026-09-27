using System;

namespace SteelSectionProbe
{
    internal static class TankManholeCatalog
    {
        internal static TankManholeSize For(int dn,int pressure)
        {
            TankManholeSize size;
            switch(dn)
            {
                case 450: size=new TankManholeSize { NominalDn=450,NominalInches=18,
                    BoreMm=450,NeckOutsideMm=480,FlangeOutsideMm=700,FlangeThicknessMm=45,
                    BoltCircleMm=610,BoltCount=16,BoltDiameterMm=20,CoverThicknessMm=45 }; break;
                case 500: size=new TankManholeSize { NominalDn=500,NominalInches=20,
                    BoreMm=500,NeckOutsideMm=530,FlangeOutsideMm=770,FlangeThicknessMm=50,
                    BoltCircleMm=675,BoltCount=20,BoltDiameterMm=20,CoverThicknessMm=50 }; break;
                case 600: size=new TankManholeSize { NominalDn=600,NominalInches=24,
                    BoreMm=600,NeckOutsideMm=635,FlangeOutsideMm=890,FlangeThicknessMm=55,
                    BoltCircleMm=790,BoltCount=20,BoltDiameterMm=24,CoverThicknessMm=55 }; break;
                default: throw new InvalidOperationException("人孔公称尺寸仅支持 DN450、DN500、DN600。");
            }
            int index=pressure==150?0:pressure==300?1:pressure==600?2:-1;
            if(index<0) throw new InvalidOperationException("压力等级仅支持 ASA 150、300、600 lbs。");
            double[] diameters=dn==450?new[]{35.0,45.0,50.0}:
                dn==500?new[]{40.0,50.0,60.0}:new[]{45.0,55.0,65.0};
            size.DavitDiameterMm=diameters[index];
            return size;
        }
    }
}
