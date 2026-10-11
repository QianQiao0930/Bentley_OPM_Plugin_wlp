using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    internal static class HoseCabinetStatistics
    {
        internal static void Attach(Element element, HoseCabinetPlan plan)
        {
            FireComponentStore.Attach(element, HoseCabinetCalculator.ItemTypeName,
                HoseCabinetStatisticsCalculator.Metadata(plan));
        }

        internal static HoseCabinetSnapshot Read()
        {
            var template = HoseCabinetStatisticsCalculator.Metadata(
                HoseCabinetCalculator.Calculate(new HoseCabinetParameters()));
            return HoseCabinetStatisticsCalculator.Summarize(
                FireComponentStore.Read(HoseCabinetCalculator.LegacyPrefix, template, "CabinetQuantity"));
        }
    }
}
