using System;
using System.Collections.Generic;

namespace SteelSectionProbe
{
    /// <summary>每个独立 CEL 实例的属性快照。数量恒为一，预览不保存此记录。</summary>
    internal sealed class CelPlacementMetadata
    {
        public string LibraryFileName { get; set; }
        public string CellName { get; set; }
        public string Category { get; set; }
        public string Specification { get; set; }
        public double RotationDegrees { get; set; }

        internal CelPlacementMetadata Copy()
        {
            if (string.IsNullOrWhiteSpace(LibraryFileName) || string.IsNullOrWhiteSpace(CellName))
                throw new InvalidOperationException("请选择有效的 CEL 单元库和单元。");
            if (double.IsNaN(RotationDegrees) || double.IsInfinity(RotationDegrees))
                throw new InvalidOperationException("绕 Z 角度必须是有限数字。");
            return new CelPlacementMetadata
            {
                LibraryFileName = LibraryFileName.Trim(), CellName = CellName.Trim(),
                Category = string.IsNullOrWhiteSpace(Category) ? "CEL 构件" : Category.Trim(),
                Specification = (Specification ?? "").Trim(), RotationDegrees = RotationDegrees
            };
        }
    }

    internal sealed class CelPlacementResult
    {
        public string ModelName { get; set; }
        public string ElementId { get; set; }
        public string CellName { get; set; }
    }

    internal sealed class CelComponentRecord
    {
        public string ModelName { get; set; }
        public string ElementId { get; set; }
        public string LibraryFileName { get; set; }
        public string CellName { get; set; }
        public string Category { get; set; }
        public string Specification { get; set; }
        public int Quantity { get; set; }
        public int Version { get; set; }
        public double RotationDegrees { get; set; }
    }

    internal sealed class CelComponentSummary
    {
        public string LibraryFileName { get; set; }
        public string CellName { get; set; }
        public string Category { get; set; }
        public string Specification { get; set; }
        public int Quantity { get; set; }
    }

    internal sealed class CelStatisticsSnapshot
    {
        public string FileName { get; set; }
        public bool AllModels { get; set; }
        public DateTime ReadAt { get; set; }
        public List<CelComponentRecord> Rows { get; set; } = new List<CelComponentRecord>();
        public List<CelComponentSummary> Summary { get; set; } = new List<CelComponentSummary>();
        public int InstanceCount { get { return Rows.Count; } }
        public int TotalQuantity { get; set; }
    }
}
