using System;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int count;
        private static void Near(double a,double b,string label)
        {count++;if(double.IsNaN(a)||Math.Abs(a-b)>1e-7)throw new Exception(label+": "+a+" != "+b);}
        private static void Reject(Action action,string label)
        {count++;try{action();}catch(InvalidOperationException){return;}throw new Exception(label);}
        private static void Main()
        {
            foreach(bool reverse in new[]{false,true})
            {
                var a=reverse?new[]{0.0,0,1000}:new[]{0.0,0,0};
                var b=reverse?new[]{0.0,0,0}:new[]{0.0,0,1000};
                var origin=new[]{0.0,0,400};
                var p=AxisPlacementCalculator.Shift(origin,a,b,125,true);
                Near(p[2],525,"vertical positive upward independent of endpoints");
                Near(AxisPlacementCalculator.Offset(origin,p,a,b),125,"offset roundtrip");
                Near(AxisPlacementCalculator.Shift(origin,a,b,-999,false)[2],0,"lower clamp");
                Near(AxisPlacementCalculator.Shift(origin,a,b,999,false)[2],1000,"upper clamp");
                Reject(()=>AxisPlacementCalculator.Shift(origin,a,b,601,true),"reject numeric overflow");
                Reject(()=>AxisPlacementCalculator.Shift(origin,a,b,-401,true),"reject numeric underflow");
            }
            for(int degrees=0;degrees<360;degrees+=15)
            {
                double angle=degrees*Math.PI/180;
                foreach(double slope in new[]{0.0,0.02,-0.02,0.5,-0.5})
                {
                    var a=new[]{20.0,30,40};var b=new[]{a[0]+1000*Math.Cos(angle),a[1]+1000*Math.Sin(angle),a[2]+1000*slope};
                    var origin=new[]{(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2};
                    var u=AxisPlacementCalculator.Unit(a,b);
                    Near(u[0]*u[0]+u[1]*u[1]+u[2]*u[2],1,"unit axis");
                    foreach(double offset in new[]{-100.0,0,175.25})
                    {
                        var p=AxisPlacementCalculator.Shift(origin,a,b,offset,true);
                        Near(p[0],origin[0]+u[0]*offset,"rotated X");Near(p[1],origin[1]+u[1]*offset,"rotated Y");Near(p[2],origin[2]+u[2]*offset,"rotated Z");
                        Near(AxisPlacementCalculator.Offset(origin,p,a,b),offset,"rotated roundtrip");
                    }
                }
            }
            var start=new[]{0.0,0,0};var end=new[]{1000.0,0,0};var click=new[]{400.0,25,30};
            var unchanged=AxisPlacementCalculator.Shift(click,start,end,0,true);
            Near(unchanged[0],400,"A1 no initial jump X");Near(unchanged[1],25,"A1 preserves transverse click Y");Near(unchanged[2],30,"A1 preserves transverse click Z");
            var shifted=AxisPlacementCalculator.Shift(click,start,end,125,true);
            Near(shifted[0],525,"horizontal displacement");Near(shifted[1],25,"horizontal retains Y");Near(shifted[2],30,"horizontal retains Z");
            Near(AxisPlacementCalculator.Offset(click,new[]{700.0,400,500},start,end),300,"off-axis reference projects in model coordinates");
            var repeated=AxisPlacementCalculator.Shift(click,start,end,AxisPlacementCalculator.Offset(click,shifted,start,end)+50,true);
            Near(repeated[0],575,"repeated slide cumulative offset");
            Reject(()=>AxisPlacementCalculator.Unit(start,start),"zero axis");
            Reject(()=>AxisPlacementCalculator.Unit(new[]{double.NaN,0,0},end),"invalid axis");
            Reject(()=>AxisPlacementCalculator.Shift(click,start,end,double.PositiveInfinity,true),"infinite input");
            Reject(()=>AxisPlacementCalculator.Shift(click,start,end,double.NaN,true),"NaN input");
            Reject(()=>AxisPlacementCalculator.Offset(click,new[]{double.NaN,0,0},start,end),"invalid event coordinate");
            Console.WriteLine("AxisPlacementCheck: "+count+" checks passed.");
        }
    }
}
