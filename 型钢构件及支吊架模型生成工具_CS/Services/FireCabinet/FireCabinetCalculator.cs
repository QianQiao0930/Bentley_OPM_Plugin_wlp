using System;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>
    /// 保留原 Python 的最小合格箱型及就近外观选型规则。
    /// </summary>
    internal static class FireCabinetCalculator
    {
        internal static FireCabinetPlan Calculate(FireCabinetParameters parameters)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException(nameof(parameters));
            }

            if (double.IsNaN(parameters.HeadingDegrees) || double.IsInfinity(parameters.HeadingDegrees))
            {
                throw new InvalidOperationException("放置角度必须为有限数字。");
            }

            FireCabinetPreset box = FireCabinetCatalog.EligibleBoxes(parameters.ExtinguisherType,
                parameters.Capacity).FirstOrDefault(item => item.Key == parameters.BoxKey);
            if (box == null)
            {
                throw new InvalidOperationException("所选箱型不满足灭火器类型及容量要求。");
            }

            FireExtinguisherRecipe interior = FireCabinetCatalog.Recipes
                .OrderBy(item => Math.Abs(item.Capacity - parameters.Capacity))
                .ThenByDescending(item => item.Capacity).FirstOrDefault(item => Fits(item, box));
            string unit = FireCabinetCatalog.Unit(parameters.ExtinguisherType);
            return new FireCabinetPlan
            {
                Parameters = parameters,
                Box = box,
                Interior = interior,
                CapacityUnit = unit,
                ExtinguisherLabel = parameters.ExtinguisherType + " " + parameters.Capacity + unit,
                HalfSeparationMm = interior == null ? 0 :
                    (interior.BodyDiameterMm + FireCabinetCatalog.InteriorGapMm) / 2
            };
        }

        private static bool Fits(FireExtinguisherRecipe recipe, FireCabinetPreset box)
        {
            double radius = recipe.BodyDiameterMm / 2;
            double scale = recipe.BodyDiameterMm / 130;
            double reach = recipe.HoseLengthMm > 0 ? radius + 33 * scale + 9 : Math.Max(radius, 43 * scale);
            double spread = (recipe.BodyDiameterMm + FireCabinetCatalog.InteriorGapMm) / 2 + reach;
            double halfWidth = (box.WidthMm - 2 * FireCabinetCatalog.WallThicknessMm) / 2 - FireCabinetCatalog.InteriorClearanceMm;
            double halfDepth = (box.DepthMm - 2 * FireCabinetCatalog.WallThicknessMm) / 2;
            double clearHeight = box.HeightMm - box.LidHeightMm - FireCabinetCatalog.WallThicknessMm - FireCabinetCatalog.InteriorClearanceMm;
            return spread <= halfWidth && radius + FireCabinetCatalog.InteriorClearanceMm <= halfDepth &&
                recipe.TotalHeightMm <= clearHeight;
        }
    }
}
