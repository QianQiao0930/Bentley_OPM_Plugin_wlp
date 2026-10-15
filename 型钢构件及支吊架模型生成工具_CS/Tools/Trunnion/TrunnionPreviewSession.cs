using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>耳轴共用暂态所有权及确认事务；配方在成功预览时冻结，确认前重读父构件。</summary>
    internal sealed class TrunnionPreviewSession
    {
        private PipeClampTransientPreview display;
        private readonly List<PipeClampTransientPreview> pending = new List<PipeClampTransientPreview>();
        private string recipeJson;
        private PipeClampSelection source;
        private long modelToken;
        private double modelScale;
        internal bool HasPreview { get { return recipeJson != null; } }
        internal bool LastConfirmedNative { get; private set; }
        internal NativePipeSupportRecipe Recipe { get { return recipeJson == null ? null : NativePipeSupportRecipeCodec.Decode(recipeJson); } }

        internal void Show(NativePipeSupportRecipe recipe, Element cell, PipeClampSelection pipe = null)
        {
            using (cell)
            {
                string json = NativePipeSupportRecipeCodec.Encode(recipe);
                long nextModel = NativeSupportElements.ActiveModelToken();
                double nextScale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
                var binding = Snapshot(pipe);
                var replacement = PipeClampTransientPreview.Create(cell);
                try { ReleaseDisplay(); }
                catch
                {
                    try { replacement.Close(); } catch { pending.Add(replacement); }
                    throw;
                }
                display = replacement; recipeJson = json; source = binding; modelToken = nextModel; modelScale = nextScale;
            }
        }

        internal void Confirm()
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            var recipe = Recipe;
            if (recipe == null) throw new InvalidOperationException("没有可确认的耳轴预览。");
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            NativeSupportData.Finite(scale);
            if (NativeSupportElements.ActiveModelToken() != modelToken || scale <= 0
                || Math.Abs(scale - modelScale) > Math.Max(1e-9, modelScale * 1e-12))
                throw new InvalidOperationException("预览后活动模型或单位已改变，请重新点取并生成预览。");
            LastConfirmedNative = false;
            bool native = recipe.Vertical != null ? NativePipeSupportSource.Eligible(source) : NativeTrunnionSource.Eligible(recipe.Elbow.Selection);
            try
            {
                if (native)
                {
                    var parent = recipe.Vertical != null ? NativePipeSupportSource.Resolve(source, recipe.CenterMm, recipe.Dn)
                        : NativeTrunnionSource.Resolve(recipe.Elbow.Selection, recipe.Elbow.Parameters);
                    NativeTrunnionPlacement.Create(recipe, parent, e => Attach(e, recipe), ReleaseDisplay);
                }
                else ConfirmOrdinary(recipe);
            }
            catch (Exception error)
            {
                try { RestoreDisplay(recipe); }
                catch (Exception restore) { throw new AggregateException("耳轴确认及预览恢复失败，请取消后重新点取。", error, restore); }
                throw;
            }
            LastConfirmedNative = native; recipeJson = null; source = null;
        }

        private void ConfirmOrdinary(NativePipeSupportRecipe recipe)
        {
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("撤销/重做期间不能确认。");
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            TransactionManager.CloseCurrentTransaction(true);
            var mark = TransactionManager.CurrentTransactionPosition;
            try
            {
                using (var cell = BuildWorld(recipe))
                {
                    SupportModelLevel.Use(cell);
                    if (cell.AddToModel() != StatusInt.Success) throw new InvalidOperationException("耳轴写入失败。");
                    Attach(cell, recipe); ReleaseDisplay();
                }
                TransactionManager.CloseCurrentTransaction(true);
            }
            catch (Exception error)
            {
                if (TransactionManager.CancelToPosition(mark, false) != StatusInt.Success)
                    throw new InvalidOperationException("耳轴确认失败且回滚未完成，请检查模型。", error);
                throw;
            }
        }

        private static Element BuildWorld(NativePipeSupportRecipe recipe)
        {
            var cell = NativePipeSupportRecipeGraphics.BuildLocal(recipe);
            try
            {
                double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
                DTransform3d placement, inverse;
                NativePipeSupportSource.PlacementFrame(recipe, scale, out placement, out inverse);
                if (cell.ApplyTransform(new TransformInfo(placement)) != 0) throw new InvalidOperationException("耳轴定位变换失败。");
                return cell;
            }
            catch { cell.Dispose(); throw; }
        }

        private void RestoreDisplay(NativePipeSupportRecipe recipe)
        { if (display == null) using (var cell = BuildWorld(recipe)) display = PipeClampTransientPreview.Create(cell); }

        private void ReleaseDisplay()
        {
            PipeClampTransientPreview.RetryPending();
            for (int i = pending.Count - 1; i >= 0; i--) { pending[i].Close(); pending.RemoveAt(i); }
            if (display == null) return;
            display.Close(); display = null;
        }

        internal void Cancel() { ReleaseDisplay(); recipeJson = null; source = null; }

        private static void Attach(Element element, NativePipeSupportRecipe recipe)
        {
            if (recipe.Vertical != null) { Statistics.AttachVerticalPipeSupport(element, recipe.Vertical); return; }
            var p = recipe.Elbow;
            string pipeSpec = "DN" + p.TrunnionDn + " Ø" + p.TrunnionOdMm.ToString("G") + " × " + p.WallMm.ToString("G") + " mm，" + p.Parameters.Material;
            Statistics.AttachElbowTrunnion(element, p, "TRUNNION", p.Parameters.Trunnion == TrunnionOrientation.Vertical ? "竖直耳轴" : "水平耳轴", pipeSpec, p.TubeLengthMm, true);
            if (p.PlateThicknessMm > 0)
                Statistics.AttachElbowTrunnion(element, p, "PLATE", p.Parameters.Trunnion == TrunnionOrientation.Vertical ? "底板" : "端板", p.Parameters.Plate + " 型，" + p.PlateThicknessMm.ToString("G") + " mm", p.PlateThicknessMm, false);
            if (p.LinerThicknessMm > 0)
                Statistics.AttachElbowTrunnion(element, p, "LINER", "镜面不锈钢覆面", "3 mm", p.LinerThicknessMm, false);
        }

        private static PipeClampSelection Snapshot(PipeClampSelection p)
        {
            return p == null ? null : new PipeClampSelection { ElementId = p.ElementId, IsPipe = p.IsPipe, IsFromReference = p.IsFromReference,
                NativePipeInstanceId = p.NativePipeInstanceId, NativeModelToken = p.NativeModelToken, SourceUorPerMm = p.SourceUorPerMm,
                StartX = p.StartX, StartY = p.StartY, StartZ = p.StartZ, EndX = p.EndX, EndY = p.EndY, EndZ = p.EndZ,
                NominalMm = p.NominalMm, OutsideMm = p.OutsideMm, InsulationMm = p.InsulationMm };
        }
    }
}
