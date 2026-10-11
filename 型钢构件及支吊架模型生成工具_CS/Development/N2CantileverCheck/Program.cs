using System;
namespace SteelSectionProbe
{
    internal enum G2MountFace {Wall,FloorTop,CeilingBottom}
    internal static class Program
    {
        private static int checks;
        private static void Equal(double a,double b,string label){checks++;if(double.IsNaN(a)||Math.Abs(a-b)>1e-8)throw new Exception(label+": "+a+" != "+b);}
        private static void True(bool v,string label){checks++;if(!v)throw new Exception(label);}
        private static void Reject(Action a,string label){checks++;try{a();}catch(InvalidOperationException){return;}throw new Exception(label+" should fail");}
        private static void Main()
        {
            double[,] loads={{7.2,3.6,1.8},{10,4.8,2},{24,12,4.8},{40,20,10}};
            string[] names={"L75x75x7","L100x100x10","12.6","16a"};
            for(int n=0;n<4;n++)
            {
                var v=N2CantileverCatalog.Require((char)('A'+n));
                True(v.ProfileA==names[n]&&v.ProfileB==names[n],"table profiles");
                Equal(v.MinimumL2Mm,n==3?390:310,"minimum L2");Equal(v.PlateType,n==3?2:1,"N8 type");
                foreach(double arm in new[]{1.0,250,250.01,500,500.01,750})
                    Equal(N2CantileverCatalog.AllowableLoad(v,arm),loads[n,arm<=250?0:arm<=500?1:2],"load band");
                Reject(()=>N2CantileverCatalog.AllowableLoad(v,750.01),"no extrapolation");
                foreach(int type in new[]{1,2})
                {
                    var p=new N2CantileverParameters{Type=type,Subtype=v.Key,PreweldMm=100,L2Mm=400,ShoeHeightMm=30};
                    var plan=N2CantileverCalculator.Calculate(p,1500);
                    double root=Math.Sqrt(1000000-40000)+100;
                    Equal(plan.RootMm,root,"curved equipment root");
                    Equal(plan.L1Mm,1500-root-(type==1?130:0),"type formula");
                    Equal(plan.OuterBFaceMm,type==1?1370:1650,"outer web face");
                    Equal(plan.ACutMm,type==1?plan.L1Mm+50:plan.L1Mm+150+plan.BWidthMm+50,"50 mm overhang");
                    Equal(plan.BLengthMm,400-plan.AWidthMm,"B fits inside A webs");
                    Equal(plan.BCount,type==1?1:2,"B count");Equal(plan.BTopOffsetMm,0,"top flush");
                    foreach(bool memberB in new[]{false,true})
                    {
                        var mode=N2CantileverCatalog.Mode(v,memberB);double minY=double.MaxValue,maxY=double.MinValue,minX=double.MaxValue;
                        foreach(var seg in mode.Segments){minY=Math.Min(minY,Math.Min(seg.Y0,seg.Y1));maxY=Math.Max(maxY,Math.Max(seg.Y0,seg.Y1));minX=Math.Min(minX,Math.Min(seg.X0,seg.X1));}
                        Equal(minY,0,"profile top at zero with down axis");Equal(minX,0,"web reference face");Equal(maxY,plan.AHeightMm,"profile height");
                    }
                    True(plan.Number.Split('-').Length==(type==1?5:6),"number omission");
                    p.ShowPreweld=true;True(N2CantileverCalculator.Calculate(p,1500).Parameters.ShowPreweld,"transparent placeholder");
                    p.PreweldMm=2*N8Catalog.Resolve(v.PlateType,"N",0,G2MountFace.Wall).T;
                    Reject(()=>N2CantileverCalculator.Calculate(p,1500),"placeholder tube must have positive length");
                    p.ShowPreweld=false;p.L2Mm=v.MinimumL2Mm-0.1;Reject(()=>N2CantileverCalculator.Calculate(p,1500),"minimum spacing");
                }
            }
            var param=new N2CantileverParameters{Type=2,PreweldMm=100,L4Mm=0};
            var one=N2CantileverCalculator.Calculate(param,1500);Equal(one.BCount,1,"omit inner B");True(one.Number.EndsWith("-150-0"),"L4 zero preserved");
            param.L4Mm=100;True(N2CantileverCalculator.Calculate(param,1500).Number.EndsWith("-150-100"),"unequal L4 explicit");
            param.L4Mm=150;True(N2CantileverCalculator.Calculate(param,1500).Number.EndsWith("-150"),"equal L4 omitted");
            param.PipeOdMm=double.NaN;param.ShoeHeightMm=-100;True(N2CantileverCalculator.Calculate(param,1500)!=null,"type2 ignores hidden S");
            param.Type=1;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"type1 invalid pipe");
            param.PipeOdMm=200;param.ShoeHeightMm=0;param.L3Mm=double.NaN;param.L4Mm=-1;True(N2CantileverCalculator.Calculate(param,1500)!=null,"type1 ignores hidden offsets");
            param.Type=3;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"type3 unavailable");param.Type=4;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"type4 unavailable");
            param.Type=2;param.L3Mm=150;param.L4Mm=500;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"inner B crosses root");
            param.L4Mm=0;param.L2Mm=1000.1;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"L2 max");
            param.L2Mm=1000;param.EquipmentOdMm=1000;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"invalid chord");
            param.EquipmentOdMm=2000;param.PreweldMm=500;Reject(()=>N2CantileverCalculator.Calculate(param,1200),"negative L1");
            param.PreweldMm=double.NaN;Reject(()=>N2CantileverCalculator.Calculate(param,1500),"nonfinite D");
            var f=N2CantileverCalculator.Frame(10,20,30,310,420,30,false);Equal(f.LengthMm,500,"rotated frame");var pt=f.Point(500,50,-80);
            Equal(pt[0],270,"frame X");Equal(pt[1],450,"frame Y");Equal(pt[2],-50,"frame Z");
            var reversed=N2CantileverCalculator.Frame(10,20,30,310,420,30,true);var end=reversed.Point(500,0,0);Equal(end[0],10,"reverse X");Equal(end[1],20,"reverse Y");
            Reject(()=>N2CantileverCalculator.Frame(0,0,0,10,0,2,false),"sloped baseline");Reject(()=>N2CantileverCalculator.Frame(0,0,0,0,0,0,false),"zero baseline");
            Reject(()=>N2CantileverCalculator.Frame(double.NaN,0,0,10,0,0,false),"nonfinite coordinates");
            Console.WriteLine("N2CantileverCheck: "+checks+" checks passed.");
        }
    }
}
