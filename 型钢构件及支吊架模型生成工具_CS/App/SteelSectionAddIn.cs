using System;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    [AddInAttribute(MdlTaskID = "SteelSectionProbe")]
    public sealed class SteelSectionAddIn : AddIn
    {
        internal static SteelSectionAddIn Instance;

        private SteelSectionAddIn(IntPtr descriptor) : base(descriptor)
        {
            Instance = this;
        }

        protected override int Run(string[] args) { return 0; }
    }
}
