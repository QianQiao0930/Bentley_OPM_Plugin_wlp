using System;
namespace SteelSectionProbe
{
    internal sealed class HandrailBuildStep
    {
        internal readonly string Name;
        internal readonly Action Run;
        internal HandrailBuildStep(string name,Action run){Name=name;Run=run;}
    }
}
