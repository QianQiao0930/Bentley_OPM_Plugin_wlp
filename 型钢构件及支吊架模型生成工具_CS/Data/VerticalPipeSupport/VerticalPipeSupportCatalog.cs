using System;
using System.Collections.Generic;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class VerticalPipeSupportCatalog
    {
        internal static readonly int[] F10Dns={15,20,25,32,40,50};
        internal static readonly int[] TrunnionDns={50,65,80,90,100,125,150,200,250,300,350,400,450,500,550,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200};
        internal static readonly Dictionary<int,double> Od=new Dictionary<int,double> {
            {15,21.3},{20,26.7},{25,33.4},{32,42.2},{40,48.3},{50,60.3},
            {65,73},{80,88.9},{90,101.6},{100,114.3},{125,141.3},{150,168.3},
            {200,219.1},{250,273},{300,323.9},{350,355.6},{400,406.4},
            {450,457.2},{500,508},{550,558.8},{600,609.6},{650,660.4},
            {700,711.2},{750,762},{800,812.8},{850,863.6},{900,914.4},
            {950,965.2},{1000,1016},{1050,1066.8},{1100,1117.6},{1150,1168.4},{1200,1219.2} };
        internal static readonly Dictionary<int,double> StdWall=new Dictionary<int,double> {
            {50,3.91},{65,5.16},{80,5.49},{90,5.74},{100,6.02},{125,6.55},
            {150,7.11},{200,8.18},{250,9.27},{300,9.53},{350,9.53},{400,9.53},
            {450,9.53},{500,9.53},{550,9.53},{600,9.53} };
        private static readonly int[,] Candidates={
            {50,100,50},{80,150,80},{100,200,100},{150,300,150},
            {250,350,200},{300,500,250},{350,600,300},{400,700,350},
            {450,800,400},{500,900,450},{550,1000,500},{650,1200,600}};
        internal static int[] TrunnionCandidates(int dn)
        {
            var result=new SortedSet<int>();
            for(int i=0;i<Candidates.GetLength(0);i++)
                if(dn>=Candidates[i,0]&&dn<=Candidates[i,1]) result.Add(Candidates[i,2]);
            return result.ToArray();
        }
        internal static int MatchDn(double nominal,VerticalPipeSupportKind kind)
        {
            var choices=kind==VerticalPipeSupportKind.F10?F10Dns:TrunnionDns;
            int nearest=choices.OrderBy(n=>Math.Abs(n-nominal)).First();
            return Math.Abs(nearest-nominal)<=Math.Max(3,nominal*0.15)?nearest:0;
        }
        internal static string SupportType(VerticalPipeSupportKind kind)
        {
            switch(kind)
            {
                case VerticalPipeSupportKind.F6:
                case VerticalPipeSupportKind.F7: return "F6_F7-[立管的耳轴]";
                default: return "F10-[小管径立管耳板]";
            }
        }
        internal static string Nps(int dn)
        {
            int[] keys={15,20,25,32,40,50,65,80,90,100,125,150,200,250,300,350,400,450,500,550,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200};
            string[] names={"1/2\"","3/4\"","1\"","1 1/4\"","1 1/2\"","2\"","2 1/2\"","3\"","3 1/2\"","4\"","5\"","6\"","8\"","10\"","12\"","14\"","16\"","18\"","20\"","22\"","24\"","26\"","28\"","30\"","32\"","34\"","36\"","38\"","40\"","42\"","44\"","46\"","48\""};
            int index=Array.IndexOf(keys,dn);
            if(index<0) throw new ArgumentOutOfRangeException("dn");
            return names[index];
        }
    }
}
