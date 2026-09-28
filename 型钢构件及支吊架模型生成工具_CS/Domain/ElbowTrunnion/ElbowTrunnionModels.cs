using System;

namespace SteelSectionProbe
{
    internal enum ElbowOrientation { Vertical, Horizontal }
    internal enum TrunnionOrientation { Vertical, Horizontal }
    internal enum PipeNamingUnit { Metric, Imperial }

    internal struct VectorMm
    {
        internal readonly double X, Y, Z;
        internal VectorMm(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static VectorMm operator +(VectorMm a, VectorMm b) { return new VectorMm(a.X + b.X, a.Y + b.Y, a.Z + b.Z); }
        public static VectorMm operator -(VectorMm a, VectorMm b) { return new VectorMm(a.X - b.X, a.Y - b.Y, a.Z - b.Z); }
        public static VectorMm operator *(VectorMm a, double n) { return new VectorMm(a.X * n, a.Y * n, a.Z * n); }
        internal double Dot(VectorMm b) { return X * b.X + Y * b.Y + Z * b.Z; }
        internal double Length { get { return Math.Sqrt(Dot(this)); } }
        internal VectorMm Unit()
        {
            double length = Length;
            if (length < 1e-9 || double.IsNaN(length) || double.IsInfinity(length))
                throw new InvalidOperationException("弯头方向为零向量或无效。");
            return this * (1.0 / length);
        }
    }

    internal sealed class ElbowFrame
    {
        internal VectorMm AxisX, AxisZ, Origin, RunPort, OutletPort, ArcCenter;
        internal VectorMm HorizontalPort, VerticalPort, HorizontalDirection, SupportAxis;
        internal bool VerticalEndUp;
        internal double RunLengthMm, OutletLengthMm;
    }

    internal sealed class ElbowTrunnionParameters
    {
        internal ElbowOrientation Elbow;
        internal TrunnionOrientation Trunnion;
        internal double ExtentMm = 1000;
        internal char Plate = 'A';
        internal bool Hollow = true;
        internal bool Ptfe = false;
        internal bool BottomFlat;
        internal bool OutletSide;
        internal string Material = "C1";
        internal PipeNamingUnit NamingUnit = PipeNamingUnit.Metric;
        internal double? WallOverrideMm = null;
    }

    internal sealed class ElbowTrunnionSelection
    {
        internal ulong ElementId = 0;
        internal string ClassName = "", PipeNumber = "";
        internal int MainDn;
        internal double OutsideDiameterMm;
        internal ElbowFrame Frame;
    }

    internal sealed class ElbowTrunnionPlan
    {
        internal ElbowTrunnionParameters Parameters;
        internal ElbowTrunnionSelection Selection;
        internal int TrunnionDn;
        internal double TrunnionOdMm, WallMm, PlateSizeMm, PlateThicknessMm, LinerThicknessMm;
        internal VectorMm TubeStartMm, TubeEndMm, PlateStartMm, PlateEndMm, LinerStartMm, LinerEndMm;
        internal VectorMm Direction, VentStartMm, VentEndMm;
        internal string SupportCode, AssemblyTag;
        internal double TubeLengthMm { get { return (TubeEndMm - TubeStartMm).Length; } }
    }
}


