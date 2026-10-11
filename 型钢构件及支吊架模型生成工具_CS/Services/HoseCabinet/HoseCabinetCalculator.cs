using System;
using System.Linq;
using System.Text.RegularExpressions;

namespace SteelSectionProbe
{
    /// <summary>
    /// 保留原型号映射与成组净距，增加实际卷盘边界及非有限尺寸校验。
    /// </summary>
    internal static class HoseCabinetCalculator
    {
        internal const double WallMm = 1.5;
        internal const double ReelRadiusMm = 190;
        internal const string ItemTypeName = "LightHoseCabinet_CSHARP";
        internal const string LegacyPrefix = "LightHoseCabinet";

        internal static HoseCabinetPlan Calculate(HoseCabinetParameters parameters)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException(nameof(parameters));
            }
            foreach (double dimension in new[] { parameters.WidthMm, parameters.DepthMm,
                parameters.HeightMm, parameters.LowerHeightMm })
            {
                if (!Finite(dimension) || dimension <= 0 || dimension > 10000)
                {
                    throw new InvalidOperationException("柜体尺寸应为 0～10000 mm 内的正数。");
                }
            }
            if (!Finite(parameters.HeadingDegrees))
            {
                throw new InvalidOperationException("旋转角度必须为有限数字。");
            }
            if (parameters.LowerHeightMm <= 3 || parameters.LowerHeightMm >= parameters.HeightMm - 3)
            {
                throw new InvalidOperationException("隔板高度必须位于柜体内部。");
            }
            if (parameters.LowerHeightMm < 80 || parameters.HeightMm - parameters.LowerHeightMm < 170)
            {
                throw new InvalidOperationException("下部高度至少 80 mm，上部高度至少 170 mm，才能布置观察窗、把手及标识。");
            }
            if (parameters.WidthMm < 200 || parameters.DepthMm <= 3)
            {
                throw new InvalidOperationException("柜宽至少 200 mm，进深须大于 3 mm。");
            }
            if (parameters.ExtinguisherQuantity < 0 || parameters.ExtinguisherQuantity > 50)
            {
                throw new InvalidOperationException("灭火器数量应为 0～50 的整数。");
            }
            if (string.IsNullOrWhiteSpace(parameters.ExtinguisherModel) || parameters.ExtinguisherModel.Length > 100)
            {
                throw new InvalidOperationException("请输入不超过 100 字的灭火器型号。");
            }

            var plan = new HoseCabinetPlan
            {
                Parameters = parameters,
                ReelCenterXmm = -parameters.WidthMm / 2 + 200,
                ReelCenterZmm = parameters.HeightMm - 200,
                ReelFrontYmm = parameters.DepthMm - 125
            };
            // 原校验只比较卷盘直径，遗漏固定中心位置、柜壁厚度及盘宽。
            if (parameters.WithEquipment && (parameters.WidthMm < 391.5 ||
                plan.ReelFrontYmm < 10.5 ||
                plan.ReelCenterZmm - ReelRadiusMm < parameters.LowerHeightMm + WallMm))
            {
                throw new InvalidOperationException("柜体空间不足以容纳 P380 卷盘，请增加宽度、进深或上部高度。");
            }

            if (parameters.ExtinguisherQuantity == 0)
            {
                return plan;
            }
            int capacity = ParseCapacity(parameters.ExtinguisherModel);
            var ordered = FireCabinetCatalog.Recipes.OrderBy(recipe => Math.Abs(recipe.Capacity - capacity))
                .ThenByDescending(recipe => recipe.Capacity);
            FireExtinguisherRecipe single = ordered.FirstOrDefault(recipe => Fits(recipe, parameters, 1));
            if (single == null || !Fits(single, parameters, parameters.ExtinguisherQuantity))
            {
                throw new InvalidOperationException("所选灭火器型号或数量无法放入下部储物区。");
            }
            plan.Interior = ordered.First(recipe => Fits(recipe, parameters, parameters.ExtinguisherQuantity));
            double diameter = plan.Interior.BodyDiameterMm;
            double span = Span(plan.Interior, parameters.ExtinguisherQuantity);
            double first = -parameters.WidthMm / 2 + WallMm +
                (parameters.WidthMm - 2 * WallMm - span) / 2 + diameter / 2;
            for (int index = 0; index < parameters.ExtinguisherQuantity; index++)
            {
                plan.BottleCentersMm.Add(first + index * (diameter + NeighborGap(plan.Interior)));
            }
            return plan;
        }

        internal static int ParseCapacity(string model)
        {
            MatchCollection numbers = Regex.Matches(model ?? "", "[0-9]+");
            for (int index = numbers.Count - 1; index >= 0; index--)
            {
                int capacity;
                if (int.TryParse(numbers[index].Value, out capacity) && capacity > 0 && capacity <= 20)
                {
                    return capacity;
                }
            }
            return 4;
        }

        internal static double Overhang(FireExtinguisherRecipe recipe)
        {
            return recipe.HoseLengthMm > 0 ? 33 * recipe.BodyDiameterMm / 130 + 9 :
                Math.Max(0, 43 * recipe.BodyDiameterMm / 130 - recipe.BodyDiameterMm / 2);
        }

        internal static double NeighborGap(FireExtinguisherRecipe recipe)
        {
            return Math.Max(Overhang(recipe) + 2, 25);
        }

        internal static double Span(FireExtinguisherRecipe recipe, int count)
        {
            return count * recipe.BodyDiameterMm + (count - 1) * NeighborGap(recipe) + Overhang(recipe);
        }

        private static bool Fits(FireExtinguisherRecipe recipe, HoseCabinetParameters parameters, int count)
        {
            return recipe.BodyDiameterMm / 2 + 2 <= (parameters.DepthMm - 3) / 2 &&
                recipe.TotalHeightMm <= parameters.LowerHeightMm - WallMm - 2 &&
                Span(recipe, count) <= parameters.WidthMm - 3 - 4;
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }
    }
}
