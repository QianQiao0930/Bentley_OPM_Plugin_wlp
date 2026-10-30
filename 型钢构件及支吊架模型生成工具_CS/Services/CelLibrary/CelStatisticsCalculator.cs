using System;
using System.Collections.Generic;
using System.Linq;

namespace SteelSectionProbe
{
    internal static class CelStatisticsCalculator
    {
        internal static CelStatisticsSnapshot Summarize(IEnumerable<CelComponentRecord> records, string fileName, bool allModels)
        {
            var rows = records.ToList();
            if (rows.Any(row => row == null || row.Quantity != 1 || row.Version != 1 || string.IsNullOrWhiteSpace(row.CellName)))
                throw new InvalidOperationException("CEL 构件记录无效，请检查附加项。");
            return new CelStatisticsSnapshot
            {
                FileName = fileName, AllModels = allModels, ReadAt = DateTime.Now, Rows = rows,
                TotalQuantity = rows.Count,
                Summary = rows.GroupBy(row => new { row.LibraryFileName, row.CellName, row.Category, row.Specification })
                    .Select(group => new CelComponentSummary { LibraryFileName = group.Key.LibraryFileName,
                        CellName = group.Key.CellName, Category = group.Key.Category,
                        Specification = group.Key.Specification, Quantity = group.Count() })
                    .OrderBy(row => row.CellName, StringComparer.Ordinal).ThenBy(row => row.Specification, StringComparer.Ordinal).ToList()
            };
        }
    }
}
