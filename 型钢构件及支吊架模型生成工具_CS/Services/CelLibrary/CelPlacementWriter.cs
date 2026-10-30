using System;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>每次左键一个独立事务：新根单元和附加项共同成功或共同回滚。</summary>
    internal static class CelPlacementWriter
    {
        private static bool writing;

        internal static CelPlacementResult Place(Func<DPoint3d, Com.CellElement> createElement, CelPlacementMetadata source, DPoint3d pointUor)
        {
            if (writing) throw new InvalidOperationException("正在放置 CEL 构件，请稍后操作。");
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (createElement == null || source == null) throw new InvalidOperationException("请先选择 CEL 单元。");
            var metadata = source.Copy();
            ValidatePoint(pointUor);
            var model = GetWritableModel();
            var file = Session.Instance.GetActiveDgnFile();
            writing = true;
            try
            {
                // The factory must stay offline. No ItemType is created during dynamics or panel preview.
                Com.CellElement element = createElement(pointUor);
                {
                    ValidateContext(model, file);
                    if (element == null || !element.IsValid || !element.IsCellElement() || !element.IsNew ||
                        !string.Equals(element.Name, metadata.CellName, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidOperationException("CEL 工厂必须返回所选单元的离线普通单元。");
                    if (!TransactionManager.IsActive) TransactionManager.Activate();
                    if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销记录。");
                    TransactionManager.CloseCurrentTransaction(true);
                    var mark = TransactionManager.CurrentTransactionPosition;
                    ulong id = 0;
                    var comModel = Utilities.ComApp.ActiveModelReference;
                    var previousLast = comModel.GetLastValidGraphicalElement();
                    ulong previousLastId = previousLast == null ? 0 : checked((ulong)previousLast.ID64);
                    try
                    {
                        ValidateContext(model, file);
                        // COM creates the orphan safely; native conversion only occurs after persistence.
                        // AddElement is inside the same transaction as the ItemType write.
                        comModel.AddElement(element);
                        CelLibraryLog.Write("added", "cell=" + metadata.CellName + "; wrapper=" + DescribeWrapper(element));
                        // AddElement may leave the original orphan wrapper's IsNew flag unchanged.
                        // Persistence is established by rereading the actual model, never by that flag.
                        id = ResolveAddedId(element, comModel, previousLastId);
                        CelLibraryLog.Write("resolve", "model=" + model.GetModelInfo().Name + "; newId=" + id + "; previousLastId=" + previousLastId);
                        using (var persisted = model.FindElementById(new ElementId(ref id)))
                        {
                            if (!CelComponentStore.IsRootCell(persisted) || (ulong)persisted.ElementId != id)
                                throw new InvalidOperationException("放置后无法重读 CEL 根单元。");
                            CelComponentStore.Attach(persisted, metadata);
                        }
                        using (var reread = model.FindElementById(new ElementId(ref id)))
                            CelComponentStore.ValidatePersisted(reread, model.GetModelInfo().Name, metadata);
                        ValidateContext(model, file);
                        TransactionManager.CloseCurrentTransaction(true);
                        CelLibraryLog.Write("committed", "cell=" + metadata.CellName + "; id=" + id);
                        return new CelPlacementResult { ModelName = model.GetModelInfo().Name,
                            ElementId = id.ToString(CultureInfo.InvariantCulture), CellName = metadata.CellName };
                    }
                    catch (Exception error)
                    {
                        CelLibraryLog.Write("failed", "cell=" + metadata.CellName + "; id=" + id + "; " + error);
                        Exception identityError = null;
                        // Rollback must run even when the COM wrapper becomes unreadable after AddElement.
                        if (id == 0)
                        {
                            try { id = ResolveAddedId(element, comModel, previousLastId); }
                            catch (Exception ex) { identityError = ex; }
                        }
                        try
                        {
                            if (!ReferenceEquals(file, Session.Instance.GetActiveDgnFile()) ||
                                !ReferenceEquals(model, Session.Instance.GetActiveDgnModel()))
                                throw new InvalidOperationException("活动文档已切换，无法对其他文档执行本次回滚，请检查原模型。");
                            var rollback = TransactionManager.CancelToPosition(mark, false);
                            if (rollback != StatusInt.Success) throw new InvalidOperationException("回滚状态：" + rollback);
                            if (id != 0)
                            using (var remaining = model.FindElementById(new ElementId(ref id)))
                                if (remaining != null && remaining.IsValid && !remaining.IsDeleted && (ulong)remaining.ElementId == id)
                                    throw new InvalidOperationException("回滚后仍存在本次新建单元，元素 ID：" + id);
                            if (identityError != null)
                                throw new InvalidOperationException("已执行回滚，但无法读取新单元身份以核对删除结果。", identityError);
                        }
                        catch (Exception rollbackError)
                        { CelLibraryLog.Write("rollback-unverified", rollbackError.ToString()); throw new AggregateException("CEL 放置失败且回滚未完成，请检查模型。", error, rollbackError); }
                        CelLibraryLog.Write("rolled-back", "id=" + id);
                        throw new InvalidOperationException("CEL 放置失败，已回滚本次写入：" + error.Message, error);
                    }
                }
            }
            finally { writing = false; }
        }

        private static string DescribeWrapper(Com.CellElement element)
        {
            string id, isNew;
            try { id = element.ID64.ToString(CultureInfo.InvariantCulture); } catch (Exception ex) { id = ex.GetType().Name; }
            try { isNew = element.IsNew.ToString(); } catch (Exception ex) { isNew = ex.GetType().Name; }
            return "ID64=" + id + ",IsNew=" + isNew;
        }

        private static ulong ResolveAddedId(Com.CellElement element, Com.ModelReference model, ulong previousLastId)
        {
            ulong id = 0;
            try { id = checked((ulong)element.ID64); } catch { }
            if (id != 0) return id;
            // Some COM wrappers remain detached after AddElement copied their descriptor.
            // Only accept a changed last root with the expected name and insertion point.
            // This synchronous host-thread operation does not pump messages or scan the full model.
            var last = model.GetLastValidGraphicalElement();
            if (last != null && last.IsCellElement())
            {
                id = checked((ulong)last.ID64);
                var cell = last.AsCellElement();
                var actual = cell.Origin; var expected = element.Origin;
                double tolerance = 0.1 / model.UORsPerMasterUnit;
                if (id != 0 && id != previousLastId && string.Equals(cell.Name, element.Name, StringComparison.OrdinalIgnoreCase) &&
                    Math.Abs(actual.X - expected.X) <= tolerance && Math.Abs(actual.Y - expected.Y) <= tolerance &&
                    Math.Abs(actual.Z - expected.Z) <= tolerance) return id;
            }
            throw new InvalidOperationException("添加 CEL 后无法取得可重读的新根单元 ID，已停止本次放置。");
        }

        internal static DgnModel GetWritableModel()
        {
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销或重做，请稍后操作。");
            var model = Session.Instance.GetActiveDgnModel();
            var file = Session.Instance.GetActiveDgnFile();
            if (model == null || file == null || !model.Is3d || model.IsReadOnly || file.IsReadOnly)
                throw new InvalidOperationException("请打开可写的三维活动模型。");
            return model;
        }

        internal static void ValidateContext(DgnModel model, DgnFile file)
        {
            if (!ReferenceEquals(model, Session.Instance.GetActiveDgnModel()) || !ReferenceEquals(file, Session.Instance.GetActiveDgnFile()))
                throw new InvalidOperationException("活动文档已改变，请重新开始放置。");
            GetWritableModel();
            var app = Utilities.ComApp;
            var comModel = app == null || !app.HasActiveModelReference ? null : app.ActiveModelReference;
            if (comModel == null || !app.HasActiveDesignFile || !comModel.Is3D ||
                !string.Equals(comModel.Name, model.GetModelInfo().Name, StringComparison.Ordinal) ||
                !string.Equals(System.IO.Path.GetFullPath(app.ActiveDesignFile.FullName), System.IO.Path.GetFullPath(file.GetFileName()), StringComparison.OrdinalIgnoreCase) ||
                comModel.UORsPerMasterUnit != model.GetModelInfo().UorPerMaster)
                throw new InvalidOperationException("COM 与活动模型身份或单位不一致，请重新开始放置。");
        }

        internal static void ValidatePoint(DPoint3d point)
        {
            if (double.IsNaN(point.X) || double.IsInfinity(point.X) || double.IsNaN(point.Y) ||
                double.IsInfinity(point.Y) || double.IsNaN(point.Z) || double.IsInfinity(point.Z))
                throw new InvalidOperationException("放置坐标必须是有限数字。");
        }
    }
}
