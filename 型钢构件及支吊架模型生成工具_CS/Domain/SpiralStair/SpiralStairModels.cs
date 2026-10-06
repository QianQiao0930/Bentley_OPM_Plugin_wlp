using System.Collections.Generic;
namespace SteelSectionProbe
{
    internal sealed class SpiralStairParameters
    {
        internal double TankDiameterMm=20000,StartZmm=0,EndZmm=20000,LandingIntervalMm=10000;
        internal double RiserMm=200,TreadDepthMm=250,ClearWidthMm=700,WallGapMm=0;
        internal double LandingLengthMm=1000,TopLengthMm=1000,StartAngleDegrees=0;
        internal int Direction=1;
        internal bool InnerRailing;
        internal double MaxPostSpacingMm=2000,StructureOffsetMm=120;
        internal HandrailConnection Connection=HandrailConnection.Type2;
        internal bool RequiresInnerRailing {get{return InnerRailing||WallGapMm>100;}}
        internal SpiralStairParameters Snapshot(){return (SpiralStairParameters)MemberwiseClone();}
    }
    internal sealed class SpiralStairBeam
    {
        internal string Name;
        internal List<HandrailPoint> Points=new List<HandrailPoint>();
        internal List<List<HandrailPoint>> Profiles=new List<List<HandrailPoint>>();
        internal int ReturnStart=-1;
    }
    internal sealed class SpiralStairPlate
    {
        internal string Name;
        internal List<HandrailPoint> Corners;
        internal double ThicknessMm;
    }
    internal sealed class SpiralStairPlan
    {
        internal SpiralStairParameters Parameters;
        internal double InnerRadiusMm,OuterRadiusMm,SlopeDegrees;
        internal List<int> FlightCounts=new List<int>();
        internal List<SpiralStairBeam> Beams=new List<SpiralStairBeam>();
        internal List<SpiralStairPlate> Plates=new List<SpiralStairPlate>();
        internal List<List<HandrailPoint>> RailingPaths=new List<List<HandrailPoint>>();
        internal int TreadCount,RestPlatformCount;
    }
}
