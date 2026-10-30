using System;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>
    /// Creates an orphan ordinary cell through Bentley's library placement API.
    /// It never adds geometry to the model. TrueScale handles source/destination units once.
    /// </summary>
    internal static class CelLibraryGeometry
    {
        private static bool creating;

        internal static Com.CellElement CreatePreview(CelLibraryEntry entry, double rotationDegrees)
        {
            return Create(entry, DPoint3d.Zero, rotationDegrees);
        }

        /// <param name="pointUor">Insertion point in the active model's UOR coordinates.</param>
        internal static Com.CellElement Create(CelLibraryEntry entry, DPoint3d pointUor, double rotationDegrees)
        {
            if (entry == null) throw new ArgumentNullException("entry");
            if (!entry.Is3D) throw new InvalidOperationException("此功能仅放置三维 CEL 单元。");
            if (!CelLibraryReader.IsFinite(rotationDegrees) || !CelLibraryReader.IsFinite(pointUor.X)
                || !CelLibraryReader.IsFinite(pointUor.Y) || !CelLibraryReader.IsFinite(pointUor.Z))
                throw new InvalidOperationException("放置点或绕 Z 角度无效。");
            string libraryPath = CelLibraryReader.ValidatePath(entry.LibraryPath);
            if (!Utilities.IsMicroStationMainThread) throw new InvalidOperationException("请在 OPM 主线程创建 CEL 单元。");
            if (creating) throw new InvalidOperationException("正在读取单元，请稍后重试。");
            var model = Session.Instance.GetActiveDgnModel();
            var app = Utilities.ComApp;
            if (model == null || !model.Is3d || app == null || !app.HasActiveModelReference || !app.ActiveModelReference.Is3D)
                throw new InvalidOperationException("请先激活三维模型。");
            double uorPerMaster = app.ActiveModelReference.UORsPerMasterUnit;
            if (!CelLibraryReader.IsPositiveFinite(uorPerMaster)) throw new InvalidOperationException("活动模型主单位无效。");

            creating = true;
            bool hadLibrary = false;
            string previousLibrary = null;
            bool restoreRequired = false;
            Com.CellElement result = null;
            Exception failure = null;
            try
            {
                hadLibrary = app.IsCellLibraryAttached;
                if (hadLibrary)
                {
                    var previous = app.AttachedCellLibrary;
                    if (previous == null || string.IsNullOrWhiteSpace(previous.FullName))
                        throw new InvalidOperationException("无法读取原附加单元库，未更改单元库设置。");
                    previousLibrary = previous.FullName;
                }
                if (!hadLibrary || !CelLibraryReader.SamePath(previousLibrary, libraryPath))
                {
                    // Set this before Attach, because a failing COM call can still have changed host state.
                    restoreRequired = true;
                    app.AttachCellLibrary(libraryPath, Com.MsdConversionMode.Never);
                    RequireAttachedLibrary(app, libraryPath);
                }

                var origin = new Com.Point3d { X = pointUor.X / uorPerMaster,
                    Y = pointUor.Y / uorPerMaster, Z = pointUor.Z / uorPerMaster };
                var scale = new Com.Point3d { X = 1, Y = 1, Z = 1 };
                // Supplying a matrix avoids the active angle, ACS and AccuDraw rotation settings.
                var rotation = app.Matrix3dFromAxisAndRotationAngle(2, (rotationDegrees % 360.0) * Math.PI / 180.0);
                result = app.CreateCellElement2(entry.Name, ref origin, ref scale, true, ref rotation);
                if (result == null || !result.IsValid || !result.IsCellElement() || !result.IsNew
                    || !string.Equals(result.Name, entry.Name, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("未能从所选库创建有效的离线普通单元“" + entry.Name + "”。");
                var actualOrigin = result.Origin;
                double tolerance = 0.1 / uorPerMaster;
                if (Math.Abs(actualOrigin.X - origin.X) > tolerance || Math.Abs(actualOrigin.Y - origin.Y) > tolerance
                    || Math.Abs(actualOrigin.Z - origin.Z) > tolerance)
                    throw new InvalidOperationException("CEL 插入原点校验失败，已停止放置。");
            }
            catch (Exception ex) { failure = ex; }
            finally
            {
                if (restoreRequired)
                {
                    try
                    {
                        if (hadLibrary)
                        {
                            app.AttachCellLibrary(previousLibrary, Com.MsdConversionMode.Never);
                            RequireAttachedLibrary(app, previousLibrary);
                        }
                        else
                        {
                            app.DetachCellLibrary();
                            if (app.IsCellLibraryAttached) throw new InvalidOperationException("原状态应为未附加任何单元库。");
                        }
                    }
                    catch (Exception restoreError)
                    {
                        failure = failure == null
                            ? (Exception)new InvalidOperationException("单元已读取，但原附加单元库恢复失败，请检查宿主单元库设置。", restoreError)
                            : new AggregateException("单元读取失败，且原附加单元库恢复失败，请检查宿主单元库设置。", failure, restoreError);
                    }
                }
                creating = false;
            }
            if (failure != null) throw new InvalidOperationException("创建 CEL 单元失败：" + failure.Message, failure);
            return result;
        }

        private static void RequireAttachedLibrary(Com.Application app, string path)
        {
            if (!app.IsCellLibraryAttached || app.AttachedCellLibrary == null
                || !CelLibraryReader.SamePath(app.AttachedCellLibrary.FullName, path))
                throw new InvalidOperationException("宿主实际附加的单元库与指定文件不一致。");
        }
    }
}
