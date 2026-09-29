using System;
using System.Globalization;

namespace SteelSectionProbe
{
    internal sealed class A22ClampRow
    {
        internal double MaximumA,AllowableLoadKn,C,E,T,W;
        internal int BoltDiameterMm;
    }

    /// <summary>A22 保冷管用 2 螺栓管夹的表 1、表 2。尺寸 mm，荷载 kN。</summary>
    internal static class A22ClampCatalog
    {
        internal const string SupportType="A22-[保冷管用2螺栓管夹]";
        internal const string SupportCode="A22_COLD_2BOLT_CLAMP";
        internal const string CellName="A22_COLD_2BOLT_CLAMP";
        internal const int DefaultDn=100;
        internal const double DefaultColdThicknessMm=50.0;
        internal const double ThroughMarginMm=5.0;
        internal const double JoinOverlapMm=1.0;
        internal const double HexAcrossFlatsRatio=1.5;
        internal const double BoltHeadHeightRatio=0.625;
        internal const double NutHeightRatio=0.8;
        internal const double WasherOdRatio=1.85;
        internal const double WasherThicknessMm=3.0;
        internal const double BoltTipExtraMm=4.0;
        internal const uint BodyColor=3,BoltColor=7;

        // A 上限、允许荷载、C、E、T、W、螺栓直径；E 对应 A2 图里的 D。
        private static readonly A22ClampRow[] Rows={
            Row(100,2,20,20,6,65,12),
            Row(150,2.7,20,20,6,75,12),
            Row(200,3.6,30,25,6,75,16),
            Row(225,4.2,30,25,10,100,16),
            Row(250,7,30,30,10,100,20),
            Row(350,10,30,40,10,100,24),
            Row(400,14,30,40,12,100,24),
            Row(450,20,40,45,12,100,30),
            Row(550,28,40,55,12,125,36),
            Row(700,34,40,55,16,125,36),
            Row(900,45,50,65,25,150,42),
            Row(1050,60,50,75,25,150,48),
            Row(1400,72,60,85,25,150,56)
        };

        private static A22ClampRow Row(double maximumA,double load,double c,double e,
            double t,double w,int bolt)
        { return new A22ClampRow {MaximumA=maximumA,AllowableLoadKn=load,C=c,E=e,T=t,W=w,
            BoltDiameterMm=bolt}; }

        internal static A22ClampRow[] All { get { return Rows; } }

        internal static A22ClampRow ForA(double a)
        {
            if(double.IsNaN(a) || double.IsInfinity(a) || a<=0.0)
                throw new InvalidOperationException("A 必须是大于 0 的有限尺寸。");
            foreach(var row in Rows) if(a<=row.MaximumA) return row;
            throw new InvalidOperationException("计算内径 A="+a.ToString("0.#",CultureInfo.InvariantCulture)+
                " mm 超出 A22 表 1 上限 1400 mm。");
        }

        internal static double BearingPlateThickness(int dn)
        {
            if(Array.IndexOf(E1GuideCatalog.Dns,dn)<0)
                throw new InvalidOperationException("A22 不支持公称直径 DN"+dn+"。");
            if(dn<=100) return 6.0;
            if(dn<=150) return 8.0;
            if(dn<=400) return 10.0;
            return 12.0;
        }

        internal static int? MatchDn(double? nominalMm)
        {
            if(!nominalMm.HasValue || double.IsNaN(nominalMm.Value) ||
                double.IsInfinity(nominalMm.Value) || nominalMm.Value<=0.0) return null;
            int best=0;double error=double.MaxValue;
            foreach(int dn in E1GuideCatalog.Dns)
            {
                double difference=Math.Abs(dn-nominalMm.Value);
                if(difference<error) { error=difference;best=dn; }
            }
            return error<=Math.Max(5.0,0.15*nominalMm.Value)?(int?)best:null;
        }
    }
}
