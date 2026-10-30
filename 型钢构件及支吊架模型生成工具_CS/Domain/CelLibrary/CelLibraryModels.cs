using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace SteelSectionProbe
{
    /// <summary>A value-only snapshot of a placeable model in a CEL library.</summary>
    internal sealed class CelLibraryEntry
    {
        public string LibraryPath { get; private set; }
        public string SourceLibraryPath { get { return LibraryPath; } }
        public string Name { get; private set; }
        public string Description { get; private set; }
        public string DisplayName { get { return string.IsNullOrWhiteSpace(Description) ? Name : Name + " · " + Description; } }
        public override string ToString() { return DisplayName; }
        public bool Is3D { get; private set; }
        public bool IsPointCell { get; private set; }
        /// <summary>Source library coordinates, in source master units (COM convention).</summary>
        public double SourceOriginX { get; private set; }
        public double SourceOriginY { get; private set; }
        public double SourceOriginZ { get; private set; }
        public string MasterUnitLabel { get; private set; }
        public double UorPerMasterUnit { get; private set; }
        public string UnitText { get { return string.IsNullOrWhiteSpace(MasterUnitLabel) ? "源库主单位" : MasterUnitLabel; } }

        internal CelLibraryEntry(string libraryPath, string name, string description, bool is3D, bool isPointCell,
            double originX, double originY, double originZ, string masterUnitLabel, double uorPerMasterUnit)
        {
            if (string.IsNullOrWhiteSpace(libraryPath)) throw new ArgumentException("单元库路径不能为空。", "libraryPath");
            if (string.IsNullOrWhiteSpace(name)) throw new ArgumentException("单元名称不能为空。", "name");
            LibraryPath = libraryPath;
            Name = name;
            Description = description ?? string.Empty;
            Is3D = is3D;
            IsPointCell = isPointCell;
            SourceOriginX = originX;
            SourceOriginY = originY;
            SourceOriginZ = originZ;
            MasterUnitLabel = masterUnitLabel ?? string.Empty;
            UorPerMasterUnit = uorPerMasterUnit;
        }
    }

    internal sealed class CelLibraryCatalog
    {
        public string LibraryPath { get; private set; }
        public IReadOnlyList<CelLibraryEntry> Entries { get; private set; }
        public int Count { get { return Entries.Count; } }
        public int SkippedModelCount { get; private set; }

        internal CelLibraryCatalog(string libraryPath, IList<CelLibraryEntry> entries, int skippedModelCount)
        {
            LibraryPath = libraryPath;
            Entries = new ReadOnlyCollection<CelLibraryEntry>(new List<CelLibraryEntry>(entries));
            SkippedModelCount = skippedModelCount;
        }
    }
}
