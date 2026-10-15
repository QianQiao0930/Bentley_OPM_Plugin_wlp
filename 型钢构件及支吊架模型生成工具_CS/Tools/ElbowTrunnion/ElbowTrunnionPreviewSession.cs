using System;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class ElbowTrunnionPreviewSession
    {
        private readonly TrunnionPreviewSession session = new TrunnionPreviewSession();
        internal bool HasPreview { get { return session.HasPreview; } }
        internal bool LastConfirmedNative { get { return session.LastConfirmedNative; } }
        internal ElbowTrunnionPlan CurrentPlan { get { return session.Recipe?.Elbow; } }

        internal void Regenerate(ElbowTrunnionPlan plan)
        {
            var f = plan.Selection.Frame;
            // 标准90°弯头的圆弧中点，ISO支撑点落在弯头中心线上；不按直管轴段投影。
            var center = f.ArcCenter + (f.AxisX - f.AxisZ) * ((f.RunLengthMm + f.OutletLengthMm) / (2 * Math.Sqrt(2)));
            var recipe = new NativePipeSupportRecipe { Code = NativePipeSupportRecipe.TrunnionCode(plan.Parameters),
                CellName = plan.SupportCode, CenterMm = new[] { center.X, center.Y, center.Z },
                Axis = new[] { f.AxisX.X, f.AxisX.Y, f.AxisX.Z }, Elbow = plan };
            var cell = new CellHeaderElement(Session.Instance.GetActiveDgnModel(), plan.SupportCode,
                DPoint3d.Zero, DMatrix3d.Identity, ElbowTrunnionBuilder.Build(plan));
            session.Show(recipe, cell);
        }
        internal void Confirm() { session.Confirm(); }
        internal void Cancel() { session.Cancel(); }
    }
}
