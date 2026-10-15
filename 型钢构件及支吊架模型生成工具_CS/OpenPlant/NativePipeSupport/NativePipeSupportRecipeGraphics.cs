using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class NativePipeSupportRecipeGraphics
    {
        internal static Element BuildLocal(NativePipeSupportRecipe recipe)
        {
            recipe.Validate();
            var model = Session.Instance.GetActiveDgnModel();
            double scale = model.GetModelInfo().UorPerMeter / 1000.0;
            NativeSupportData.Finite(scale);
            if (scale <= 0 || !model.Is3d) throw new InvalidOperationException("原生管夹需要有效三维模型单位。");
            var center = new DPoint3d(recipe.CenterMm[0] * scale, recipe.CenterMm[1] * scale, recipe.CenterMm[2] * scale);
            var axis = new DVector3d(recipe.Axis[0], recipe.Axis[1], recipe.Axis[2]);
            IList<Element> parts;
            switch (recipe.Code)
            {
                case "A1": parts = A1ClampBuilder.Build(recipe.A1, center, axis); break;
                case "U3": parts = U3ClampBuilder.Build(recipe.U3, center, axis); break;
                case "A2": parts = A2ClampBuilder.Build(recipe.A2, center, axis); break;
                case "A22": case "A24": parts = A22ClampBuilder.Build(recipe.A22, center, axis); break;
                case "E1": parts = E1GuideBuilder.Build(recipe.E1); break;
                case "K1": parts = K1LimitBuilder.Build(recipe.K1, center, axis); break;
                case "T4": case "L2": parts = T4ShoeBuilder.Build(recipe.Shoe, recipe.Boolean, center, axis, recipe.BuildPipe, recipe.BuildInsulation); break;
                case "F6": case "F7": case "F10": parts = VerticalPipeSupportBuilder.Build(recipe.Vertical, center, axis); break;
                case "F2": case "F2-HE": case "F4": case "F5": parts = ElbowTrunnionBuilder.Build(recipe.Elbow); break;
                default: throw new InvalidOperationException("未登记的原生管夹建模器。");
            }
            if (parts == null || parts.Count == 0) throw new InvalidOperationException("原生管夹未生成实体。");
            var cell = new CellHeaderElement(model, recipe.CellName, DPoint3d.Zero, DMatrix3d.Identity, parts);
            try
            {
                DTransform3d placement, inverse;
                NativePipeSupportSource.PlacementFrame(recipe, scale, out placement, out inverse);
                if (cell.ApplyTransform(new TransformInfo(inverse)) != 0) throw new InvalidOperationException("原生管夹局部几何转换失败。");
                return cell;
            }
            catch { cell.Dispose(); throw; }
        }
    }
}
