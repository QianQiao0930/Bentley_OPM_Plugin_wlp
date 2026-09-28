using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>One line or arc in a closed steel-section outline.</summary>
    internal sealed class SegmentData
    {
        internal bool IsArc;
        internal double X0, Y0, Xm, Ym, X1, Y1;
    }

    /// <summary>A profile insertion/reference mode and its prebuilt outline.</summary>
    internal sealed class ModeData
    {
        internal string Id;
        internal string Label;
        internal SegmentData[] Segments;

        public override string ToString() { return Label; }
    }

    /// <summary>A catalog specification, including dimensions and insertion modes.</summary>
    internal sealed class ProfileData
    {
        internal string Name;
        internal Dictionary<string, double> Dimensions;
        internal ModeData[] Modes;

        public override string ToString() { return Name; }
    }

    /// <summary>A family in the steel-section catalog.</summary>
    internal sealed class FamilyData
    {
        internal string Id;
        internal string Label;
        internal ProfileData[] Profiles;

        public override string ToString() { return Label; }
    }
}
