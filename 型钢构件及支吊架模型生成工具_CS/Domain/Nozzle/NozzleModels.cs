using System;
namespace SteelSectionProbe
{
    internal sealed class NozzleParameters
    {
        internal string Rating="CL150";
        internal string PipeSchedule="Ia_Sch10";
        internal int NominalDn=100;
        internal double TotalLengthMm=200;
        internal double? WallOverrideMm;
        internal string Axis="+Z";
        internal bool DrawBoltHoles;
    }
    internal sealed class NozzleSize
    {
        internal int NominalDn,BoltCount;
        internal string Rating,PipeSchedule,BoltSize;
        internal double PipeOutsideMm,PipeWallMm,FlangeOutsideMm,FlangeThicknessMm;
        internal double BoltCircleMm,BoltHoleMm,RaisedFaceOutsideMm,RaisedFaceHeightMm;
    }
    internal sealed class NozzlePlan
    {
        internal NozzleParameters Parameters;
        internal NozzleSize Size;
        internal double WallMm,PipeLengthMm,BoreRadiusMm;
    }
}
