namespace SteelSectionProbe
{
    internal enum VerticalPipeSupportKind { F6, F7, F10 }

    internal sealed class VerticalPipeSupportParameters
    {
        internal VerticalPipeSupportKind Kind;
        internal int PipeDn;
        internal int TrunnionDn;
        internal double LengthMm=500;
        internal double WallMm;
        internal string EndType="A";
        internal string Material="C1";
        internal double AzimuthDegrees;
        internal bool BuildPad;
        internal double PadThicknessMm=5;
        internal string F10Length="1";
        internal string F10Height="A";
        internal bool F10Fixed=true;
    }

    internal sealed class VerticalPipeSupportPlan
    {
        internal VerticalPipeSupportKind Kind;
        internal int PipeDn,TrunnionDn;
        internal double PipeOd,TrunnionOd,WallMm,LengthMm,EndPlateThicknessMm,
            PadThicknessMm,PadWidthMm,EarHeightMm,EarWidthMm,AzimuthDegrees;
        internal string EndType,Material,Number,Specification,PipeNumber;
        internal bool Fixed;
        internal int Count { get { return Kind==VerticalPipeSupportKind.F6?1:2; } }
    }
}
