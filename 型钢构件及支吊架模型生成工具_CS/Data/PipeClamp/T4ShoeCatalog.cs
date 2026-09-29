using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>T4 高温隔热限位管托表 1 的一行。尺寸单位 mm，荷载单位 kN。</summary>
    internal sealed class T4ShoeRow
    {
        internal int Dn;
        internal string Nps;
        internal double OutsideMm;
        internal string Bolt;
        /// <summary>耳板 (宽, 高, 厚)。</summary>
        internal double EarWidthMm,EarHeightMm,EarThicknessMm;
        /// <summary>螺栓中心线到管夹外圆的距离 C。</summary>
        internal double BoltCenterCMm;
        /// <summary>耳板焊缝腰高 k。</summary>
        internal double WeldLegKMm;
        /// <summary>承重板之间的间隙 J。</summary>
        internal double PlateGapJMm;
        /// <summary>底板厚 T1、腹板 / 上下板厚 T2、承重板厚 T3。</summary>
        internal double T1Mm,T2Mm,T3Mm;
        /// <summary>允许荷载 (垂直, 横向, 轴向)。</summary>
        internal double VerticalLoadKn,LateralLoadKn,AxialLoadKn;

        internal double BoltDiameterMm
        {
            get
            {
                double value;
                return T4ShoeCatalog.BoltDiametersMm.TryGetValue(Bolt,out value)?value:0.0;
            }
        }
    }

    /// <summary>
    /// T4 高温隔热限位管托（图集 T4）的表 1、表 2、保温厚度→高度表与全部建模常量。
    /// 纯数据，不引用 Bentley API。来源：<c>管道支吊架/模块/保温管夹/保温管夹_几何.py</c>。
    /// </summary>
    internal static class T4ShoeCatalog
    {
        internal const string SupportType="T4-[高温隔热限位管托]";
        internal const string SupportCode="INSULATED_PIPE_CLAMP";
        internal const string CellName="INSULATED_PIPE_CLAMP";

        internal const int DnMin=15,DnMax=600;
        internal const double MinShoeLengthMm=300.0;
        internal const double MinInsulationMm=1.0;
        internal const double MinHeightMm=1.0;
        /// <summary>长 L 超过该值时管夹底座加盖中间横向支撑。</summary>
        internal const double MiddleRibLengthMm=600.0;
        /// <summary>管夹对开方位角（°）：0 = 正上方（+Z），45 = 图上 45° 螺栓线。</summary>
        internal const double DefaultSplitAngleDeg=45.0;
        internal const double DefaultClampWidthMm=75.0;
        /// <summary>螺栓在两侧承重板之外的长度。</summary>
        internal const double BoltExtraMm=25.0;

        internal const int DefaultDn=200;
        internal const double DefaultInsulationMm=50.0;
        internal const double DefaultLengthMm=300.0;

        /// <summary>首 / 尾耳板中心到管夹轴向端部的距离。</summary>
        internal const double EarEndOffsetMm=75.0;
        /// <summary>0 = 自动（L≤600 两组，L&gt;600 三组）。</summary>
        internal const int EarGroupCount=0;
        internal const double SupportEndOffsetMm=75.0;
        internal const double SupportSideInsetMm=10.0;
        internal const double SupportOverlapMm=1.0;
        internal const double EarSetbackMm=10.0;
        internal const double EarRootOverlapMm=1.0;
        /// <summary>螺栓通孔相对螺杆直径的单边余量（M20→22）。</summary>
        internal const double HoleClearanceMm=2.0;
        /// <summary>45° 贯穿切割体两端伸出外圆之外的余量。</summary>
        internal const double CutExtraLengthMm=20.0;
        /// <summary>布尔贯穿余量，避免共面失败。</summary>
        internal const double ThroughMarginMm=5.0;

        internal const double HexAcrossFlatsRatio=1.5;
        internal const double BoltHeadHeightRatio=0.625;
        internal const double NutHeightRatio=0.8;
        internal const double WasherOdRatio=1.85;
        internal const double WasherThicknessMm=3.0;
        internal const double BoltTipExtraMm=4.0;

        /// <summary>管夹 / 底座颜色索引。</summary>
        internal const uint ClampColor=3,BoltColor=7;
        /// <summary>可选管道本体颜色索引（Python 用 RGB(148,148,148)，此处用索引近似）。</summary>
        internal const uint PipeColor=7;
        /// <summary>可选保温层颜色索引（Python 用 RGB(245,200,90)，此处用索引近似）。</summary>
        internal const uint InsulationColor=4;

        internal static readonly Dictionary<string,double> BoltDiametersMm=new Dictionary<string,double>{
            {"M10",10.0},{"M12",12.0},{"M16",16.0},{"M20",20.0},{"M24",24.0},{"M30",30.0}
        };

        private static readonly T4ShoeRow[] Rows={
            // 表 1 详图 B（2″ 及以下）：图中给出的 T1/T2/T3、螺栓与荷载；
            // OD 沿用本工程 E1GuideCatalog 的同 DN 钢管数据；耳板为 40×40×12；
            // C、k、J 等未在该局部表图列出的尺寸暂沿用 DN80 的规格。
            Make(15,"1/2\"",21.3,"M12",40,40,12,25,6,25,8,8,6,10,2,5),
            Make(20,"3/4\"",26.7,"M12",40,40,12,25,6,25,8,8,6,10,2,5),
            Make(25,"1\"",33.4,"M12",40,40,12,25,6,25,8,8,6,10,2,5),
            Make(40,"1 1/2\"",48.3,"M12",40,40,12,25,6,25,8,8,6,30,6,10),
            Make(50,"2\"",60.3,"M12",40,40,12,25,6,25,8,8,6,30,6,10),
            Make(80,"3\"",88.9,"M12",40,40,16,25,6,25,10,8,6,40,8,30),
            Make(100,"4\"",114.3,"M12",40,40,16,25,6,25,10,8,6,40,8,30),
            Make(125,"5\"",141.3,"M16",50,50,20,30,6,25,10,8,10,70,15,60),
            Make(150,"6\"",168.3,"M16",50,50,20,30,6,25,10,8,10,70,15,60),
            Make(200,"8\"",219.1,"M20",60,60,20,35,8,30,12,12,12,150,30,80),
            Make(250,"10\"",273.0,"M20",60,60,20,35,8,30,12,12,12,150,30,80),
            Make(300,"12\"",323.9,"M20",60,60,20,35,8,30,12,12,12,150,30,80),
            Make(350,"14\"",355.6,"M20",60,60,20,35,8,30,12,12,12,200,40,100),
            Make(400,"16\"",406.4,"M20",60,60,20,35,8,30,12,12,12,200,40,100),
            Make(450,"18\"",457.2,"M24",70,70,25,40,10,40,14,12,14,300,50,120),
            Make(500,"20\"",508.0,"M24",70,70,25,40,10,40,14,12,14,300,50,120),
            Make(550,"22\"",558.8,"M24",70,70,25,40,10,40,14,12,14,300,50,120),
            Make(600,"24\"",609.6,"M24",70,70,25,40,10,40,14,12,14,300,50,120)
        };

        private static T4ShoeRow Make(int dn,string nps,double od,string bolt,
            double earW,double earH,double earT,double c,double k,double j,
            double t1,double t2,double t3,double vertical,double lateral,double axial)
        {
            return new T4ShoeRow {
                Dn=dn,Nps=nps,OutsideMm=od,Bolt=bolt,
                EarWidthMm=earW,EarHeightMm=earH,EarThicknessMm=earT,
                BoltCenterCMm=c,WeldLegKMm=k,PlateGapJMm=j,
                T1Mm=t1,T2Mm=t2,T3Mm=t3,
                VerticalLoadKn=vertical,LateralLoadKn=lateral,AxialLoadKn=axial };
        }

        /// <summary>表 2：(隔热层外径 D 上限, 底板宽度 W)。</summary>
        private static readonly double[,] BaseWidthTable={
            {200.0,100.0},{300.0,150.0},{400.0,200.0},{500.0,250.0},{600.0,300.0},
            {800.0,400.0},{1000.0,500.0},{1200.0,600.0},{1400.0,700.0},{1600.0,800.0}
        };

        /// <summary>保温厚度 B → H（管道不含保温底部 → 管托底面）。</summary>
        private static readonly double[,] InsulationHeightTable={
            {75.0,150.0},{125.0,200.0},{175.0,250.0},{225.0,300.0},{275.0,350.0}
        };

        internal static T4ShoeRow[] All { get { return Rows; } }
        internal static int[] DnChoices { get { return Rows.Select(x=>x.Dn).ToArray(); } }

        internal static T4ShoeRow Require(int dn)
        {
            var row=Rows.FirstOrDefault(x=>x.Dn==dn);
            if(row==null)
                throw new InvalidOperationException("管径 DN"+dn+" 超出本次范围 DN"+DnMin+"~"+DnMax+"。");
            return row;
        }

        internal static double Outside(int dn) { return Require(dn).OutsideMm; }
        internal static double BoltDiameterMm(int dn) { return Require(dn).BoltDiameterMm; }
        /// <summary>DN15~600 均为 4 颗螺栓（表 1）。</summary>
        internal static int BoltCount(int dn) { Require(dn); return 4; }

        /// <summary>详图 B：2″ 及以下仅用底板和中央纵向腹板支撑。</summary>
        internal static bool UsesSimpleBase(int dn) { Require(dn); return dn<=50; }

        internal static string DnLabel(int dn)
        {
            var row=Require(dn);
            return "DN"+dn+"  |  "+row.Nps+"  |  OD "+
                row.OutsideMm.ToString("0.0",CultureInfo.InvariantCulture);
        }

        /// <summary>
        /// 把管道公称直径（mm）匹配到表 1 的 DN；匹配不上返回 null。
        /// 与 Python <c>T4-[高温隔热限位管托].py</c> 的 <c>_match_dn</c> 一致：只比公称直径数值
        /// （容差 max(5, 15%)），不拿外径比。
        /// </summary>
        internal static int? MatchDn(double? nominalMm)
        {
            if(!nominalMm.HasValue) return null;
            double value=nominalMm.Value;
            if(double.IsNaN(value) || double.IsInfinity(value) || value<=0.0) return null;
            int best=Rows[0].Dn;
            double error=double.MaxValue;
            foreach(var row in Rows)
            {
                double e=Math.Abs(row.Dn-value);
                if(e<error) { error=e; best=row.Dn; }
            }
            return error<=Math.Max(5.0,0.15*value)?(int?)best:null;
        }

        /// <summary>按表 2 由保温层外径 D 取底板宽度 W；超出表上限时报错。</summary>
        internal static double BaseWidthForInsulationOd(double insulationOdMm)
        {
            for(int i=0;i<BaseWidthTable.GetLength(0);i++)
                if(insulationOdMm<=BaseWidthTable[i,0]) return BaseWidthTable[i,1];
            throw new InvalidOperationException("保温层外径 D="+
                insulationOdMm.ToString("0.0",CultureInfo.InvariantCulture)+
                " mm 超出表 2 上限 "+
                BaseWidthTable[BaseWidthTable.GetLength(0)-1,0].ToString("0",CultureInfo.InvariantCulture)+" mm。");
        }

        /// <summary>按保温厚度 B 查表得到 H；超出表上限时报错。</summary>
        internal static double HeightForInsulation(double insulationMm)
        {
            for(int i=0;i<InsulationHeightTable.GetLength(0);i++)
                if(insulationMm<=InsulationHeightTable[i,0]) return InsulationHeightTable[i,1];
            throw new InvalidOperationException("保温厚度 B="+
                insulationMm.ToString("0.0",CultureInfo.InvariantCulture)+
                " mm 超出表上限 "+
                InsulationHeightTable[InsulationHeightTable.GetLength(0)-1,0].ToString("0",CultureInfo.InvariantCulture)+" mm。");
        }

        /// <summary>管架编号：<c>名称-管径-温度代码-H-L-材料代码-F</c>；名称为空则返回空串。</summary>
        internal static string BuildNumber(string name,int dn,string temperatureCode,
            double heightMm,double lengthMm,string materialCode,string fCode)
        {
            string label=(name??"").Trim();
            if(label.Length==0) return "";
            return label+"-"+dn.ToString(CultureInfo.InvariantCulture)+"-"+
                (temperatureCode??"").Trim()+"-"+
                RoundHalfUp(heightMm).ToString(CultureInfo.InvariantCulture)+"-"+
                RoundHalfUp(lengthMm).ToString(CultureInfo.InvariantCulture)+"-"+
                (materialCode??"").Trim()+"-"+(fCode??"").Trim();
        }

        internal static int RoundHalfUp(double value)
        { return (int)Math.Floor(value+0.5); }
    }
}
