using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>G2 混凝土锚板表 1 的一个子项。全部尺寸单位为毫米，荷载单位为 kN。</summary>
    internal sealed class G2AnchorItem
    {
        internal string Key;
        /// <summary>锚栓公称直径 M。</summary>
        internal double BoltDiameterMm;
        /// <summary>锚栓总长 L。</summary>
        internal double BoltLengthMm;
        /// <summary>要求的最小有效埋深 h_ef。</summary>
        internal double RequiredEmbedmentMm;
        internal double TensionKn;
        internal double ShearKn;
        /// <summary>锚板螺栓孔孔径 G。</summary>
        internal double HoleDiameterMm;
        /// <summary>锚板厚度 T。</summary>
        internal double PlateThicknessMm;
        /// <summary>螺栓孔中心距下限 MIN.S。</summary>
        internal double MinSpacingMm;
        /// <summary>混凝土边缘距离下限 MIN.C。</summary>
        internal double MinEdgeDistanceMm;
        /// <summary>混凝土厚度下限 MIN.h。</summary>
        internal double MinThicknessMm;
        /// <summary>螺母对边距（标准值近似，仅用于成形）。</summary>
        internal double NutAcrossFlatsMm;
        internal double NutHeightMm;
        internal double WasherOutsideMm;
        internal double WasherThicknessMm;
    }

    /// <summary>
    /// G2 混凝土锚板 + 膨胀锚栓的表 1 子项、安装面选项与建模常量。
    /// 纯数据，不引用 Bentley API，可被纯计算检查工程直接链接。
    /// </summary>
    internal static class G2AnchorCatalog
    {
        /// <summary>板边距：锚板边长 = S + 2×50，对应详图 (S+100)×(S+100)。</summary>
        internal const double PlateMarginMm=50.0;
        /// <summary>膨胀套管外径系数与占埋深比例。</summary>
        internal const double SleeveDiameterFactor=1.7;
        internal const double SleeveEmbedFraction=0.55;
        /// <summary>螺杆外端超出螺母外端面的长度（露出的丝头）；锚栓总长 L 不变。</summary>
        internal const double BoltProtrusionMm=5.0;
        /// <summary>切割刀具体伸出锚板两侧的余量，避免与板面共面。</summary>
        internal const double CutterExtensionMm=2.0;

        internal const string CellName="CONCRETE_ANCHOR_PLATE";
        internal const string FeatureCode="G2_ANCHOR_PLATE";
        internal const string SupportType="G2-[混凝土锚板（膨胀螺栓）]";
        internal const string DefaultSubtypeKey="A";
        internal const double DefaultHeadingDegrees=0.0;

        internal const uint PlateColor=3,BoltColor=7,NutColor=2,SleeveColor=4;

        private static readonly G2AnchorItem[] Items={
            Make("A", 8.0,  80.0,  55.0,  8.0,  8.0, 10.0, 10.0,  75.0,  75.0, 110.0, 13.0,  6.5, 16.0, 1.6),
            Make("B", 12.0, 120.0, 90.0, 17.0, 23.0, 14.0, 12.0, 100.0, 100.0, 180.0, 19.0, 10.0, 24.0, 2.5),
            Make("C", 16.0, 140.0, 100.0,24.0, 40.0, 18.0, 16.0, 125.0, 150.0, 200.0, 24.0, 13.0, 30.0, 3.0),
            Make("D", 20.0, 180.0, 125.0,33.0, 68.0, 22.0, 20.0, 150.0, 200.0, 250.0, 30.0, 16.0, 37.0, 3.0)
        };

        private static G2AnchorItem Make(string key,double boltDia,double boltLength,
            double embedment,double tension,double shear,double holeDia,double plateThickness,
            double minSpacing,double minEdge,double minThickness,double nutAcrossFlats,
            double nutHeight,double washerOutside,double washerThickness)
        {
            return new G2AnchorItem {
                Key=key,BoltDiameterMm=boltDia,BoltLengthMm=boltLength,
                RequiredEmbedmentMm=embedment,TensionKn=tension,ShearKn=shear,
                HoleDiameterMm=holeDia,PlateThicknessMm=plateThickness,
                MinSpacingMm=minSpacing,MinEdgeDistanceMm=minEdge,
                MinThicknessMm=minThickness,NutAcrossFlatsMm=nutAcrossFlats,
                NutHeightMm=nutHeight,WasherOutsideMm=washerOutside,
                WasherThicknessMm=washerThickness };
        }

        internal static IList<G2AnchorItem> All { get { return Items; } }

        internal static G2AnchorItem Find(string key)
        {
            if(!string.IsNullOrEmpty(key))
                foreach(var item in Items) if(string.Equals(item.Key,key,StringComparison.OrdinalIgnoreCase)) return item;
            return null;
        }

        internal static G2AnchorItem Require(string key)
        {
            var item=Find(key);
            if(item==null) throw new InvalidOperationException("G2 子项只支持 A / B / C / D。");
            return item;
        }

        internal static bool IsKnownKey(string key) { return Find(key)!=null; }
    }
}
