namespace SteelSectionProbe
{
    /// <summary>Per-element experiment data; independent of the production material-list schema.</summary>
    internal sealed class A1NativeTrialRecord
    {
        public int Version = 1;
        public string PipeInstanceId = "", SupportInstanceId = "", NativeClass = "UBOLT_GUIDE", Tag = "";
        public double StationMm, AngleDeg, OriginalLengthMm;
        public int Dn;
    }

    internal sealed class A1NativeTrialPosition
    {
        internal double X, Y, Z, Ux, Uy, StationMm, LengthMm, AngleDeg;
    }
}
