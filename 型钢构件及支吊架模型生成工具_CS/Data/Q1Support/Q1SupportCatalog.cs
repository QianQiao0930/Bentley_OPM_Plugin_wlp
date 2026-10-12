using System;
using System.Linq;
namespace SteelSectionProbe
{
    internal static class Q1SupportCatalog
    {
        internal const string SupportType="Q1-[大管用角钢支撑小管(1/2\"~4\"，不保温管)]";
        internal const string CellName="Q1_ANGLE_SMALL_PIPE_SUPPORT";
        // 图纸未注明安装净隙，建模保留 2 mm，避免管壁与角钢穿插。
        internal const double PipeWallGapMm=2;
        internal static readonly int[] SmallDns={15,20,25,32,40,50,65,80,90,100};
        internal static string Subitem(int dn)
        {
            if(!SmallDns.Contains(dn))throw new InvalidOperationException("小管管径须为 DN15～100（1/2″～4″）。");
            return dn<=25?"A":dn<=50?"B":"C";
        }
        internal static string ProfileName(string item)
        {return item=="A"?"L50x50x6":item=="B"?"L75x75x7":"L100x100x10";}
        internal static string Section(string item)
        {return item=="A"?"∠50×6":item=="B"?"∠75×7":"∠100×10";}
        internal static double Load(string item){return item=="A"?.6:item=="B"?1.6:3;}
        internal static ModeData Mode(Q1SupportPlan plan)
        {return ProfileLookup.Mode(RuntimeData.Families,"equal_angle",plan.ProfileName,"outer_corner");}
    }
}
