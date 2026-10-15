using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal sealed class VerticalPipeSupportPreviewSession
    {
        private readonly TrunnionPreviewSession session = new TrunnionPreviewSession();
        internal bool HasPreview { get { return session.HasPreview; } }
        internal bool LastConfirmedNative { get { return session.LastConfirmedNative; } }
        /// <summary>正式预览与沿轴滑动共用原Builder，不写模型。</summary>
        internal static Element CreateCell(VerticalPipeSupportPlan next, DPoint3d center, DVector3d axis)
        {
            return new CellHeaderElement(Session.Instance.GetActiveDgnModel(), "VERTICAL_PIPE_SUPPORT",
                DPoint3d.Zero, DMatrix3d.Identity, VerticalPipeSupportBuilder.Build(next, center, axis));
        }
        internal void Show(VerticalPipeSupportPlan next, DPoint3d center, DVector3d axis, PipeClampSelection source = null)
        {
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            var recipe = new NativePipeSupportRecipe { Code = next.Kind.ToString(), CellName = "VERTICAL_PIPE_SUPPORT",
                CenterMm = new[] { center.X / scale, center.Y / scale, center.Z / scale },
                Axis = new[] { axis.X, axis.Y, axis.Z }, Vertical = next };
            session.Show(recipe, CreateCell(next, center, axis), source);
        }
        internal void Confirm() { session.Confirm(); }
        internal void Cancel() { session.Cancel(); }
    }
}
