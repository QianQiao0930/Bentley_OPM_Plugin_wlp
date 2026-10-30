using System;
using System.Collections.Generic;
using System.IO;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>Read-only enumeration. No library is attached and no model is activated here.</summary>
    internal static class CelLibraryReader
    {
        internal static string DefaultLibraryPath
        {
            get { return Path.Combine(Path.GetDirectoryName(typeof(CelLibraryReader).Assembly.Location), "地面冲洗水盘管.cel"); }
        }

        internal static string ValidatePath(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) throw new InvalidOperationException("请选择 CEL 单元库。");
            var fullPath = Path.GetFullPath(path.Trim());
            if (!string.Equals(Path.GetExtension(fullPath), ".cel", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("请选择扩展名为 .cel 的单元库文件。");
            if (!File.Exists(fullPath)) throw new FileNotFoundException("找不到单元库，请将 CEL 与 DLL 放在同一目录，或浏览选择其他库。", fullPath);
            return fullPath;
        }

        internal static CelLibraryCatalog Read(string path)
        {
            string fullPath = ValidatePath(path);
            if (!Utilities.IsMicroStationMainThread) throw new InvalidOperationException("请在 OPM 主线程读取单元库。");
            var app = Utilities.ComApp;
            if (app == null) throw new InvalidOperationException("无法连接 OPM 单元库接口。");

            Com.DesignFile library = null;
            bool ownsFile = false;
            Exception readError = null;
            CelLibraryCatalog catalog = null;
            try
            {
                // Never close the active document when it happens to be the requested CEL.
                if (app.HasActiveDesignFile && SamePath(app.ActiveDesignFile.FullName, fullPath))
                    library = app.ActiveDesignFile;
                else
                {
                    library = app.OpenDesignFileForProgram(fullPath, true);
                    ownsFile = true;
                }
                if (library == null) throw new InvalidOperationException("无法以只读方式打开 CEL 单元库。");
                var entries = new List<CelLibraryEntry>();
                int skipped = 0;
                var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (Com.ModelReference model in library.Models)
                {
                    if (!model.Is3D || !model.CanBePlacedAsCell
                        || (model.CellType != Com.MsdCellType.Graphic && model.CellType != Com.MsdCellType.Point))
                    {
                        skipped++;
                        continue;
                    }
                    string name = model.Name;
                    if (string.IsNullOrWhiteSpace(name) || !names.Add(name))
                        throw new InvalidOperationException("单元库存在空名称或重名单元，不能可靠识别放置内容。");
                    double uorPerMaster = model.UORsPerMasterUnit;
                    if (!IsPositiveFinite(uorPerMaster))
                        throw new InvalidOperationException("单元“" + name + "”的源库单位无效。");
                    var origin = model.GlobalOrigin;
                    if (!IsFinite(origin.X) || !IsFinite(origin.Y) || !IsFinite(origin.Z))
                        throw new InvalidOperationException("单元“" + name + "”的源库原点无效。");
                    entries.Add(new CelLibraryEntry(fullPath, name, model.Description, true,
                        model.CellType == Com.MsdCellType.Point, origin.X, origin.Y, origin.Z,
                        model.get_MasterUnit().Label, uorPerMaster));
                }
                entries.Sort((left, right) => StringComparer.CurrentCultureIgnoreCase.Compare(left.Name, right.Name));
                catalog = new CelLibraryCatalog(fullPath, entries, skipped);
            }
            catch (Exception ex) { readError = ex; }
            finally
            {
                if (ownsFile && library != null)
                {
                    try { library.Close(); }
                    catch (Exception closeError)
                    {
                        readError = readError == null
                            ? (Exception)new InvalidOperationException("单元库读取完成，但只读文件未能关闭。", closeError)
                            : new AggregateException("单元库读取及关闭均失败。", readError, closeError);
                    }
                }
            }
            if (readError != null) throw new InvalidOperationException("读取 CEL 单元库失败：" + readError.Message, readError);
            return catalog;
        }

        internal static bool SamePath(string left, string right)
        {
            return string.Equals(Path.GetFullPath(left), Path.GetFullPath(right), StringComparison.OrdinalIgnoreCase);
        }

        internal static bool IsFinite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
        internal static bool IsPositiveFinite(double value) { return IsFinite(value) && value > 0; }
    }
}
