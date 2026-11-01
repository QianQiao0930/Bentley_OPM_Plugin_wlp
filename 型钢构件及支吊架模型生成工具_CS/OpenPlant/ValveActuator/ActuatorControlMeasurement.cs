using System;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;

namespace SteelSectionProbe
{
    internal static class ActuatorControlMeasurement
    {
        internal static ActuatorControlLayout Read(CelLibraryEntry frozenEntry)
        {
            ActuatorCelGraphics.RequireContext();
            var model = Session.Instance.GetActiveDgnModel();
            double mmPerMasterUnit = Utilities.ComApp.ActiveModelReference.UORsPerMasterUnit
                / (model.GetModelInfo().UorPerMeter / 1000.0);
            // Use the same true-scale orphan factory as the existing CEL preview.
            // This reads the immutable snapshot, never adds an element or recentres it.
            var cell = CelLibraryGeometry.Create(frozenEntry, DPoint3d.Zero, 0);
            var range = cell.Range;
            if (!ReferenceEquals(model, Session.Instance.GetActiveDgnModel()))
                throw new InvalidOperationException("活动模型已变化，请重新开始放置。");
            return ActuatorControlLayout.FromBounds(range.Low.X, range.Low.Y, range.Low.Z,
                range.High.X, range.High.Y, range.High.Z, mmPerMasterUnit);
        }
    }
}
