using System;
using System.IO;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int assertions, scenarios;
        private static string libraryPath, oldLibraryPath;
        private static void Main()
        {
            libraryPath = Path.Combine(Path.GetTempPath(), "CelLibraryIoCheck-" + Guid.NewGuid().ToString("N") + ".cel");
            oldLibraryPath = Path.Combine(Path.GetTempPath(), "CelLibraryIoCheck-old-" + Guid.NewGuid().ToString("N") + ".cel");
            File.WriteAllText(libraryPath, "fake only");
            File.WriteAllText(oldLibraryPath, "fake only");
            try
            {
                var app = Reset();
                app.Library.Models.Add(new Com.ModelReference { Name = "B", Description = "B型", GlobalOrigin = new Com.Point3d { X = 12, Y = -5, Z = 8 } });
                app.Library.Models.Add(new Com.ModelReference { Name = "A", CellType = Com.MsdCellType.Point });
                app.Library.Models.Add(new Com.ModelReference { Name = "2D", Is3D = false });
                app.Library.Models.Add(new Com.ModelReference { Name = "not-cell", CanBePlacedAsCell = false });
                app.Library.Models.Add(new Com.ModelReference { Name = "menu", CellType = Com.MsdCellType.Menu });
                var catalog = CelLibraryReader.Read(libraryPath);
                Check(catalog.Count == 2 && catalog.SkippedModelCount == 3, "only placeable 3D cells counted");
                Check(catalog.Entries[0].Name == "A" && catalog.Entries[0].IsPointCell, "names sorted; point cell retained");
                Check(catalog.Entries[1].SourceOriginX == 12 && catalog.Entries[1].UorPerMasterUnit == 1000, "source origin and units retained");
                Check(app.OpenReadOnly && app.Library.Closed && app.AttachCalls == 0, "enumeration read-only; no global attachment");
                scenarios++;

                app = Reset(); app.Library.Models.Add(new Com.ModelReference()); app.Library.Models.Add(new Com.ModelReference());
                Expect(() => CelLibraryReader.Read(libraryPath), "duplicate names rejected"); Check(app.Library.Closed, "failure closes read-only file"); scenarios++;
                app = Reset(); app.Library.Models.Add(new Com.ModelReference { UORsPerMasterUnit = double.NaN });
                Expect(() => CelLibraryReader.Read(libraryPath), "bad source unit rejected"); scenarios++;
                app = Reset(); app.Library.FailClose = true;
                Expect(() => CelLibraryReader.Read(libraryPath), "close failure reported"); scenarios++;
                app = Reset(); app.ActiveDesignFile.FullName = libraryPath; app.ActiveDesignFile.Models.Add(new Com.ModelReference());
                Check(CelLibraryReader.Read(libraryPath).Count == 1 && !app.ActiveDesignFile.Closed && app.OpenCalls == 0, "never closes active CEL document"); scenarios++;
                app = Reset(); app.FailOpen = true;
                Expect(() => CelLibraryReader.Read(libraryPath), "open failure reported"); scenarios++;

                app = Reset(); var entry = Entry();
                var cell = CelLibraryGeometry.Create(entry, new DPoint3d(123456, -50000, 20000), 450);
                Check(cell.IsNew && cell.IsValid && app.CreateCalls == 1, "orphan cell returned once");
                Near(app.CreatedOrigin.X, 12.3456, "UOR to master conversion"); Near(app.CreatedOrigin.Y, -5, "negative coordinate retained");
                Check(app.UsedTrueScale && app.CreatedScale.X == 1 && app.CreatedScale.Y == 1 && app.CreatedScale.Z == 1, "TrueScale once; no second scale");
                Check(app.CreatedRotation.Axis == 2, "world Z only"); Near(app.CreatedRotation.Radians, Math.PI / 2, "degree angle normalized");
                Check(!app.IsCellLibraryAttached && app.AttachCalls == 1 && app.DetachCalls == 1, "empty original library state restored"); scenarios++;

                app = Reset(); app.AttachedCellLibrary = new Com.CellLibrary { FullName = oldLibraryPath };
                CelLibraryGeometry.CreatePreview(entry, -90);
                Check(app.AttachedCellLibrary.FullName == oldLibraryPath && app.AttachCalls == 2, "original library restored");
                Near(app.CreatedOrigin.Z, 0, "preview at zero"); Near(app.CreatedRotation.Radians, -Math.PI / 2, "negative angle retained"); scenarios++;

                app = Reset(); app.AttachedCellLibrary = new Com.CellLibrary { FullName = libraryPath };
                CelLibraryGeometry.CreatePreview(entry, 0); Check(app.AttachCalls == 0 && app.DetachCalls == 0, "already selected library untouched"); scenarios++;
                app = Reset(); app.AttachedCellLibrary = new Com.CellLibrary { FullName = oldLibraryPath }; app.FailCreate = true;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "create failure reported"); Check(app.AttachedCellLibrary.FullName == oldLibraryPath, "create failure restores original"); scenarios++;
                app = Reset(); app.FailAttachAfterChangePath = libraryPath;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "partial attach failure reported"); Check(!app.IsCellLibraryAttached && app.CreateCalls == 0, "partial attach restores empty state before returning"); scenarios++;
                app = Reset(); app.FailDetach = true;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "restore failure never returns success"); scenarios++;
                app = Reset(); app.AttachedCellLibrary = new Com.CellLibrary { FullName = oldLibraryPath }; app.FailAttachPath = oldLibraryPath;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "old-library restore failure reported"); scenarios++;
                app = Reset(); app.ReturnWrongOrigin = true;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "wrong CEL insertion point rejected"); Check(!app.IsCellLibraryAttached, "origin failure restores library"); scenarios++;
                app = Reset(); Expect(() => CelLibraryGeometry.CreatePreview(entry, double.PositiveInfinity), "invalid angle rejected"); Check(app.AttachCalls == 0, "invalid angle does not attach"); scenarios++;
                app = Reset(); Session.Instance.Model.Is3d = false;
                Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "2D destination rejected"); Check(app.AttachCalls == 0, "2D destination never attaches"); scenarios++;
                app = Reset(); Utilities.IsMicroStationMainThread = false;
                Expect(() => CelLibraryReader.Read(libraryPath), "background read forbidden"); Expect(() => CelLibraryGeometry.CreatePreview(entry, 0), "background creation forbidden"); Check(app.AttachCalls == 0 && app.OpenCalls == 0, "background calls do not enter COM"); scenarios++;
                app = Reset(); Expect(() => CelLibraryReader.Read(libraryPath + ".missing"), "non-CEL rejected"); Expect(() => CelLibraryReader.Read(Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N") + ".cel")), "missing file rejected"); scenarios++;
                Console.WriteLine("CEL library IO: " + scenarios + " scenarios, " + assertions + " assertions passed. No Bentley host was launched; native geometry/TrueScale rendering require host acceptance.");
            }
            finally { File.Delete(libraryPath); File.Delete(oldLibraryPath); }
        }
        private static CelLibraryEntry Entry() { return new CelLibraryEntry(libraryPath, "盘管", "盘管说明", true, false, 0, 0, 0, "mm", 1000); }
        private static Com.Application Reset()
        {
            var app = new Com.Application(); app.ActiveDesignFile.FullName = libraryPath + ".dgn"; Utilities.ComApp = app;
            Utilities.IsMicroStationMainThread = true; Session.Instance.Model = new FakeModel(); return app;
        }
        private static void Near(double actual, double expected, string message) { Check(Math.Abs(actual - expected) < 1e-9, message); }
        private static void Check(bool condition, string message) { assertions++; if (!condition) throw new InvalidOperationException(message); }
        private static void Expect(Action action, string message)
        { assertions++; try { action(); } catch (Exception) { return; } throw new InvalidOperationException(message); }
    }
}
