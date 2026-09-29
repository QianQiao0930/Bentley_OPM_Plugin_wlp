using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    internal static class PadPlateStraightReader
    {
        internal static PipeClampSelection Read(DgnModelRef modelRef,ulong id,
            double clickX,double clickY,double clickZ,out PadPlateHvacDuct duct)
        {
            var line=PipeClampReader.Read(modelRef,id,clickX,clickY,clickZ);
            var snapshot=ComponentPropertyReader.Read(modelRef,id);
            duct=PadPlateHvacCatalog.Resolve(snapshot.AllProperties);
            return line;
        }
    }
}
