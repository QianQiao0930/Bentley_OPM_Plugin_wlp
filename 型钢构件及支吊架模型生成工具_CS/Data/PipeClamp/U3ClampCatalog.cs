using System.Linq;

namespace SteelSectionProbe
{
    internal static class U3ClampCatalog
    {
        internal const string SupportType = "U3-[带承重块的U形螺栓]";
        internal const string CellName = "U3_BEARING_U_BOLT";
        internal static readonly A1ClampRow[] Rows = A1ClampCatalog.All.Where(x => x.Dn <= 150).ToArray();
    }
}
