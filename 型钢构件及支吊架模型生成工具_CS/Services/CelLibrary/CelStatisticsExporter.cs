using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    internal static class CelStatisticsExporter
    {
        internal static void WriteJson(string path, CelStatisticsSnapshot snapshot)
        {
            if (snapshot == null) throw new ArgumentNullException("snapshot");
            File.WriteAllText(path, new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(new
            { itemTypeLibrary = CelComponentStore.LibraryName, snapshot.FileName, snapshot.AllModels,
                snapshot.ReadAt, snapshot.InstanceCount, snapshot.TotalQuantity, snapshot.Summary, snapshot.Rows }), new UTF8Encoding(false));
        }

        internal static void WriteCsv(string path, CelStatisticsSnapshot snapshot)
        {
            if (snapshot == null) throw new ArgumentNullException("snapshot");
            using (var writer = new StreamWriter(path, false, new UTF8Encoding(true)))
            {
                writer.WriteLine("模型,元素ID,来源单元库,单元名称,构件类别,规格型号,数量,绕Z角度(°),数据版本");
                foreach (var row in snapshot.Rows)
                    writer.WriteLine(string.Join(",", new[] { row.ModelName, row.ElementId, row.LibraryFileName,
                        row.CellName, row.Category, row.Specification, row.Quantity.ToString(CultureInfo.InvariantCulture),
                        row.RotationDegrees.ToString("R", CultureInfo.InvariantCulture), row.Version.ToString(CultureInfo.InvariantCulture) }.Select(Csv)));
            }
        }

        private static string Csv(string value)
        {
            value = value ?? "";
            // Prevent exported library/Cell names from becoming executable spreadsheet formulas.
            string first = value.TrimStart();
            if (first.Length > 0 && "=+-@".IndexOf(first[0]) >= 0) value = "'" + value;
            return "\"" + value.Replace("\"", "\"\"") + "\"";
        }
    }
}
