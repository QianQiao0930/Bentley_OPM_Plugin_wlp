using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>持续光标预览；左键一次放置一套，右键结束。动态单元始终离线。</summary>
    internal sealed class CelPlacementTool : DgnPrimitiveTool
    {
        private static CelPlacementTool active;
        private Func<DPoint3d, Com.CellElement> factory;
        private CelPlacementMetadata metadata;
        private Com.CellElement prototype;
        private Com.TransientElementContainer display;
        private static readonly System.Collections.Generic.List<CelPlacementTool> Pending = new System.Collections.Generic.List<CelPlacementTool>();
        private DPoint3d prototypeAt;
        private DgnModel model;
        private DgnFile file;
        private bool oldSnap, oldLocate, disposed, endedNotified, captureRestored;
        private string lastError;

        private CelPlacementTool() : base(0, 0) { }
        internal static bool IsActive { get { return active != null; } }
        internal static bool NeedsCleanup { get { return active != null || Pending.Count != 0; } }
        internal static event Action<CelPlacementResult> Placed;
        internal static event Action<string> Failed;
        internal static event Action Ended;

        internal static void Begin(Func<DPoint3d, Com.CellElement> createElement, CelPlacementMetadata source)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (createElement == null || source == null) throw new InvalidOperationException("请先选择 CEL 单元。");
            var options = source.Copy();
            RetryPending();
            var target = CelPlacementWriter.GetWritableModel();
            var targetFile = Session.Instance.GetActiveDgnFile();
            ClearSelection();
            if (active != null)
            {
                CelPlacementWriter.ValidateContext(active.model, active.file);
                active.ClearPrototype();
                active.factory = createElement; active.metadata = options; active.lastError = null;
                AccuSnap.SnapEnabled = true; AccuSnap.LocateEnabled = true;
                Prompt();
                return;
            }
            var tool = new CelPlacementTool { factory = createElement, metadata = options, model = target, file = targetFile,
                oldSnap = AccuSnap.SnapEnabled, oldLocate = AccuSnap.LocateEnabled };
            active = tool;
            try
            {
                tool.InstallTool();
                if (!ReferenceEquals(active, tool)) throw new InvalidOperationException("CEL 放置工具未成功安装。");
                AccuSnap.SnapEnabled = true; AccuSnap.LocateEnabled = true;
            }
            catch
            {
                if (ReferenceEquals(active, tool)) active = null;
                tool.Release();
                throw;
            }
        }

        internal static void End()
        {
            RetryPending();
            var tool = active;
            if (tool == null) return;
            active = null;
            try { tool.ExitTool(); }
            finally
            {
                try { tool.Release(); }
                finally { tool.NotifyEnded(); }
            }
        }

        internal static void InvalidatePrototype()
        { if (active != null) active.ClearPrototype(); }

        private static void ClearSelection()
        {
            SelectionSetManager.EmptyAll();
            if (SelectionSetManager.IsActive() && SelectionSetManager.NumSelected() != 0)
                throw new InvalidOperationException("无法清空旧选择，请先取消选择后再开始放置。");
        }

        protected override bool OnInstall()
        {
            ClearSelection();
            return base.OnInstall();
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            ClearSelection();
            BeginDynamics();
            Prompt();
        }

        private static void Prompt()
        { NotificationManager.OutputPrompt("移动光标预览 CEL 构件；中心轴固定向上，绕 Z 角度按面板输入；左键放置一套，右键结束。"); }

        protected override void OnDynamicFrame(DgnButtonEvent ev)
        {
            if (!ReferenceEquals(active, this) || factory == null) return;
            try
            {
                if (!LicenseService.IsActivated) throw new InvalidOperationException("授权已失效，请先激活软件。");
                CelPlacementWriter.ValidateContext(model, file);
                CelPlacementWriter.ValidatePoint(ev.Point);
                if (prototype == null)
                {
                    prototype = factory(ev.Point);
                    if (prototype == null || !prototype.IsValid || !prototype.IsCellElement() || !prototype.IsNew)
                        throw new InvalidOperationException("CEL 动态预览必须是离线普通单元。");
                    prototypeAt = ev.Point;
                }
                else
                {
                    double unit = model.GetModelInfo().UorPerMaster;
                    var delta = new Com.Point3d { X = (ev.Point.X - prototypeAt.X) / unit,
                        Y = (ev.Point.Y - prototypeAt.Y) / unit, Z = (ev.Point.Z - prototypeAt.Z) / unit };
                    prototype.Move(ref delta);
                    prototypeAt = ev.Point;
                }
                ClearDisplay();
                display = Utilities.ComApp.CreateTransientElementContainer1(prototype,
                    Com.MsdTransientFlags.Overlay | Com.MsdTransientFlags.DontIncludeInFit,
                    Com.MsdViewMask.AllViews, Com.MsdDrawingMode.Normal);
                if (display == null) throw new InvalidOperationException("无法创建 CEL 光标暂态预览。");
                lastError = null;
            }
            catch (Exception ex)
            {
                try { ClearPrototype(); }
                catch (Exception cleanup) { ReportFailure("CEL 预览及暂态清理失败：" + ex.Message + "；" + cleanup.Message); return; }
                ReportFailure("CEL 预览失败：" + ex.Message);
            }
        }

        protected override bool OnDataButton(DgnButtonEvent ev)
        {
            if (!ReferenceEquals(active, this)) return true;
            CelPlacementResult result;
            bool paused = false;
            string displayWarning = null;
            try
            {
                CelPlacementWriter.ValidateContext(model, file);
                ClearDisplay();
                EndDynamics(); paused = true;
                result = CelPlacementWriter.Place(factory, metadata, ev.Point);
                // Commit and redraw in normal display mode; dynamics otherwise defer the new graphics
                // until the placement tool exits. Refresh failures must never undo a committed cell.
                try
                {
                    foreach (Com.View view in Utilities.ComApp.ActiveDesignFile.Views)
                        if (view.IsOpen) view.Redraw();
                }
                catch (Exception ex)
                {
                    CelLibraryLog.Write("display-refresh-failed", "id=" + result.ElementId + "; " + ex);
                    displayWarning = "构件已放置，视图刷新失败：" + ex.Message;
                }
            }
            catch (Exception ex) { ReportFailure(ex.Message); return true; }
            finally
            {
                if (paused && ReferenceEquals(active, this))
                    try { BeginDynamics(); }
                    catch (Exception ex)
                    {
                        CelLibraryLog.Write("dynamics-resume-failed", ex.ToString());
                        displayWarning = "恢复连续放置预览失败，请结束后重试：" + ex.Message;
                    }
            }
            // User callbacks occur after a completed transaction; a UI exception cannot turn success into a write failure.
            try { NotificationManager.OutputPrompt("已放置“" + result.CellName + "”；左键继续放置，右键结束。"); } catch { }
            var placed = Placed;
            if (placed != null)
                foreach (Action<CelPlacementResult> handler in placed.GetInvocationList())
                    try { handler(result); } catch (Exception ex) { ReportFailure("构件已放置，界面通知失败：" + ex.Message); }
            if (displayWarning != null) ReportFailure(displayWarning);
            return true;
        }

        protected override bool OnResetButton(DgnButtonEvent ev)
        { if (ReferenceEquals(active, this)) TryEndFromHost(); return true; }
        protected override void OnRestartTool()
        { if (ReferenceEquals(active, this)) TryEndFromHost(); }
        private void TryEndFromHost()
        {
            try { End(); }
            catch (Exception ex) { ReportFailure("结束 CEL 放置失败，请点击结束重试：" + ex.Message); }
        }
        protected override void OnCleanup()
        {
            bool current = ReferenceEquals(active, this);
            if (current) active = null;
            Exception failure = null;
            try { Release(); }
            catch (Exception ex) { failure = ex; }
            finally { base.OnCleanup(); }
            if (current) NotifyEnded();
            if (failure != null) ReportFailure("CEL 暂态清理失败，请点击结束重试：" + failure.Message);
        }

        private void NotifyEnded()
        {
            if (endedNotified) return;
            endedNotified = true;
            var ended = Ended;
            if (ended != null)
                foreach (Action handler in ended.GetInvocationList())
                    try { handler(); } catch (Exception ex) { ReportFailure("放置已结束，界面通知失败：" + ex.Message); }
        }

        private void ReportFailure(string message)
        {
            try { NotificationManager.OutputPrompt(message); } catch { }
            if (lastError == message) return;
            lastError = message;
            var failed = Failed;
            if (failed != null)
                foreach (Action<string> handler in failed.GetInvocationList())
                    try { handler(message); } catch { }
        }
        private void ClearDisplay()
        {
            if (display == null) return;
            display.Reset();
            display = null;
        }
        private void ClearPrototype()
        {
            ClearDisplay();
            // Orphan COM geometry has never entered the model; release our reference without
            // FinalReleaseComObject, which could invalidate a host-owned shared RCW.
            prototype = null;
        }
        private void Release()
        {
            if (disposed) return;
            try
            {
                ClearPrototype();
                disposed = true;
                Pending.Remove(this);
                factory = null; metadata = null; model = null; file = null;
            }
            catch
            {
                if (!Pending.Contains(this)) Pending.Add(this);
                throw;
            }
            finally
            {
                // A delayed cleanup of a retired tool must not overwrite the new tool's capture state.
                if (!captureRestored && (active == null || ReferenceEquals(active, this)))
                { AccuSnap.SnapEnabled = oldSnap; AccuSnap.LocateEnabled = oldLocate; captureRestored = true; }
            }
        }
        private static void RetryPending()
        {
            for (int index = Pending.Count - 1; index >= 0; index--) Pending[index].Release();
        }
    }
}
