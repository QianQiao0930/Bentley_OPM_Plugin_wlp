using System;
using System.Collections.Generic;
using System.Globalization;
namespace SteelSectionProbe
{
    internal static class MagneticGaugeCalculator
    {
        internal static MagneticGaugePlan Calculate(MagneticGaugeParameters input)
        {
            if(input==null)throw new ArgumentNullException("input");
            double l=input.ConnectionSpacingMm;
            if(double.IsNaN(l)||double.IsInfinity(l)||l<MagneticGaugeCatalog.MinSpacingMm||l>MagneticGaugeCatalog.MaxSpacingMm)
                throw new InvalidOperationException("上下接口中心距L1须在350～6000 mm之间。");
            if(double.IsNaN(input.HeadingDegrees)||double.IsInfinity(input.HeadingDegrees))throw new InvalidOperationException("旋转角必须是有限数字。");
            var parameters=new MagneticGaugeParameters{ConnectionSpacingMm=l,HeadingDegrees=input.HeadingDegrees%360};
            var parts=new List<MagneticGaugePart>();
            Cylinder(0,0,-85,0,0,l+85,30);
            foreach(double z in new[]{-105,l+85})
            {
                Cylinder(0,0,z,0,0,z+10,55);Cylinder(0,0,z+10,0,0,z+12,50,MagneticGaugeColor.Dark);Cylinder(0,0,z+12,0,0,z+20,55);
                for(int i=0;i<6;i++){double a=2*Math.PI*i/6,x=44*Math.Cos(a),y=44*Math.Sin(a);Cylinder(x,y,z-4,x,y,z+25,4,MagneticGaugeColor.Dark);Cylinder(x,y,z+20,x,y,z+26,6);}
            }
            foreach(double z in new[]{0,l})
            {
                Cylinder(-260,0,z,-22,0,z,13.5);
                foreach(double x in new[]{-224d,-108})
                {
                    Cylinder(x,0,z,x+10,0,z,46);Cylinder(x+10,0,z,x+12,0,z,43,MagneticGaugeColor.Dark);Cylinder(x+12,0,z,x+22,0,z,46);
                    for(int i=0;i<4;i++){double a=Math.PI/4+i*Math.PI/2,y=35*Math.Cos(a),dz=35*Math.Sin(a);Cylinder(x-4,y,z+dz,x+26,y,z+dz,4,MagneticGaugeColor.Dark);Cylinder(x+22,y,z+dz,x+28,y,z+dz,6);}
                }
                Cylinder(-202,0,z,-108,0,z,24);Cylinder(-155,0,z,-155,0,z+37,18);Cylinder(-155,0,z+37,-155,0,z+45,23);Cylinder(-155,0,z+45,-155,0,z+77,5,MagneticGaugeColor.Dark);
                Wheel(-155,z+80,30);
            }
            foreach(double z in new[]{30,l-30}){Cylinder(0,0,z-5,0,0,z+5,32,MagneticGaugeColor.Dark);Box(-22,-39,z-5,44,18,10);}
            Box(-25,-44,-12,65,8,l+24,MagneticGaugeColor.Dark);Box(-25,-49,-12,4,5,l+24);Box(21,-49,-12,4,5,l+24);Box(-21,-49,-12,42,5,12);Box(-21,-49,l,42,5,12);
            int flips=2*Math.Max(10,(int)Math.Ceiling(l/MagneticGaugeCatalog.FlipReferencePitchMm));double pitch=l/flips;
            for(int i=0;i<flips;i++)Box(-20,-49,i*pitch+.4,40,5,pitch-.8,i<flips/2?MagneticGaugeColor.Red:MagneticGaugeColor.White);
            Box(26,-45,0,13,1,l,MagneticGaugeColor.White);
            int ticks=(int)Math.Floor(l/10)+1;
            for(int i=0;i<ticks;i++)Box(27,-46,Math.Min(i*10,l-.8),i%5==0?11:6,1,.8,MagneticGaugeColor.Dark);
            Cylinder(0,0,-128,0,0,-105,9);Box(-13,-13,-155,26,26,27);Cylinder(0,0,-180,0,0,-155,7);Cylinder(13,0,-142,38,0,-142,4,MagneticGaugeColor.Dark);Cylinder(38,-18,-142,38,18,-142,3,MagneticGaugeColor.Dark);
            return new MagneticGaugePlan{Parameters=parameters,Parts=parts.ToArray(),FlipCount=flips,FlipPitchMm=pitch,TickCount=ticks,
                CellName=MagneticGaugeCatalog.CellPrefix+l.ToString("G",CultureInfo.InvariantCulture)};

            void Cylinder(double ax,double ay,double az,double bx,double by,double bz,double r,MagneticGaugeColor color=MagneticGaugeColor.Steel)
            {parts.Add(new MagneticGaugePart{Kind=MagneticGaugeKind.Cylinder,Start=new MagneticGaugePoint(ax,ay,az),End=new MagneticGaugePoint(bx,by,bz),RadiusMm=r,Color=color});}
            void Box(double x,double y,double z,double dx,double dy,double dz,MagneticGaugeColor color=MagneticGaugeColor.Steel)
            {parts.Add(new MagneticGaugePart{Kind=MagneticGaugeKind.Box,Start=new MagneticGaugePoint(x,y,z),Size=new MagneticGaugePoint(dx,dy,dz),Color=color});}
            void Wheel(double x,double z,double radius)
            {
                parts.Add(new MagneticGaugePart{Kind=MagneticGaugeKind.Torus,Start=new MagneticGaugePoint(x,0,z),RadiusMm=radius,TubeRadiusMm=3.5,Color=MagneticGaugeColor.Dark});
                Cylinder(x-radius,0,z,x+radius,0,z,2.5,MagneticGaugeColor.Dark);Cylinder(x,-radius,z,x,radius,z,2.5,MagneticGaugeColor.Dark);
            }
        }
    }
}
