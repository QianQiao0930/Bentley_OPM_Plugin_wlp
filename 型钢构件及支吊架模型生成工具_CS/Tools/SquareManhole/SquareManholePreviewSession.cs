using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
namespace SteelSectionProbe
{
    internal sealed class SquareManholePreviewSession
    {
        private readonly PreviewElementOwnership ownership = new PreviewElementOwnership("方形人孔");
        internal string WriteElapsed { get; private set; }
        internal bool HasPreview {get{return ownership.HasPreview;}}
        internal void Regenerate(SquareManholePlan plan,DPoint3d origin)
        {
            ownership.Invalidate();
            var replacement=SquareManholeBuilder.Build(plan,origin);
            string elapsed;
            var status=WriteDuration.Measure(replacement.AddToModel,out elapsed);
            if(status!=StatusInt.Success)throw new InvalidOperationException("方形人孔预览写入失败："+status);
            ownership.ReplaceWrittenElement(replacement);
            WriteElapsed=elapsed;
        }
        internal void Confirm()
        {
            ownership.Confirm(null);
        }
        internal void Cancel(){ownership.Cancel();}
    }
}
