using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    internal static class ComponentPropertyCalculator
    {
        private static readonly Dictionary<int, double> PipeOutsideDiameters = new Dictionary<int, double>
        {
            {15,21.3},{20,26.9},{25,33.7},{32,42.4},{40,48.3},{50,60.3},
            {65,76.1},{80,88.9},{100,114.3},{125,139.7},{150,168.3},
            {200,219.1},{250,273.0},{300,323.9},{350,355.6},{400,406.4},
            {450,457.0},{500,508.0},{600,610.0},{700,711.0},{800,813.0},
            {900,914.0},{1000,1016.0},{1200,1219.0}
        };

        internal static double LengthScale(double? rawLength, double? geometryMm, string unit)
        {
            if (unit == "mm") return 1;
            if (unit == "m") return 1000;
            if (rawLength.HasValue && rawLength.Value > 0 && geometryMm.HasValue && geometryMm.Value > 0)
            {
                double mmError = Math.Abs(rawLength.Value - geometryMm.Value) / geometryMm.Value;
                double mError = Math.Abs(rawLength.Value * 1000 - geometryMm.Value) / geometryMm.Value;
                if (Math.Min(mmError, mError) <= 0.05) return mError < mmError ? 1000 : 1;
            }
            return rawLength.HasValue && rawLength.Value < 1 ? 1000 : 1;
        }

        internal static double? Number(IDictionary<string, string> properties, string name)
        {
            string value;
            double result;
            if (!properties.TryGetValue(name, out value)) return null;
            if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out result))
                if (!double.TryParse(value, NumberStyles.Float, CultureInfo.CurrentCulture, out result)) return null;
            return double.IsNaN(result) || double.IsInfinity(result) ? (double?)null : result;
        }

        internal static int? NearestDn(double? outsideDiameterMm)
        {
            if (!outsideDiameterMm.HasValue || outsideDiameterMm.Value <= 0) return null;
            int best = 0;
            double error = double.MaxValue;
            foreach (var pair in PipeOutsideDiameters)
            {
                double current = Math.Abs(outsideDiameterMm.Value - pair.Value) / pair.Value;
                if (current < error) { error = current; best = pair.Key; }
            }
            return error <= 0.03 ? (int?)best : null;
        }

        internal static string Orientation(ComponentSnapshot snapshot)
        {
            if (!snapshot.StartX.HasValue || !snapshot.EndX.HasValue) return "—";
            double dx = snapshot.EndX.Value - snapshot.StartX.Value;
            double dy = snapshot.EndY.Value - snapshot.StartY.Value;
            double dz = snapshot.EndZ.Value - snapshot.StartZ.Value;
            double horizontal = Math.Sqrt(dx * dx + dy * dy);
            if (horizontal < 0.01 && Math.Abs(dz) < 0.01) return "零长度";
            if (horizontal < 0.01) return "竖直";
            if (Math.Abs(dz) < 0.01) return "水平";
            return "倾斜，坡度 " + (dz / horizontal * 100).ToString("F2", CultureInfo.InvariantCulture) + "%";
        }
    }
}
