namespace SteelSectionProbe
{
    internal enum PadPlateKind { Y2, Elbow }
    internal sealed class PadPlateParameters
    {
        internal PadPlateKind Kind;
        internal int FallbackDn=100;
        internal double LengthMm=300,AlphaDeg=120,CoverageDeg=75;
        internal string Material="C1";
        internal bool VentHole=true,AutoMultiplier=true;
        internal double Multiplier=1.5;
    }
    internal sealed class PadPlateElbow
    {
        internal bool IsDuct;
        internal int? Dn;
        internal double OutsideMm,CenterToEndMm;
        internal string SizeLabel,PipeNumber;
        internal VectorMm Origin,AxisX,AxisZ;
    }

    internal sealed class PadPlateHvacDuct
    {
        internal double OutsideMm;
        internal string SizeLabel;
    }
    internal sealed class PadPlatePlan
    {
        internal PadPlateKind Kind;
        internal int? Dn;
        internal double OutsideMm,ThicknessMm,InnerRadiusMm,OuterRadiusMm;
        internal double LengthMm,AlphaDeg,CoverageDeg,Multiplier,BendRadiusMm,ArcLengthMm;
        internal bool VentHole;
        internal string Material,PadMaterial,Number,Specification,PipeNumber,CellName,SupportType;
        internal VectorMm Center,Axis,Origin,AxisX,AxisZ;
        internal double ComponentLengthMm { get { return Kind==PadPlateKind.Y2?LengthMm:ArcLengthMm; } }
    }
}
