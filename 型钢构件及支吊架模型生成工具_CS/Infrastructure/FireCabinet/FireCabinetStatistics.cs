using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>
    /// 灭火器箱的消防附加项契约，共用消防库读写边界。
    /// </summary>
    internal static class FireCabinetStatistics
    {
        internal static void Attach(Element element, FireCabinetPlan plan, int interiorModelCount)
        {
            FireComponentStore.Attach(element, FireCabinetCatalog.ItemTypeName,
                FireCabinetStatisticsCalculator.Metadata(plan, interiorModelCount));
        }

        internal static FireCabinetSnapshot Read()
        {
            var template = FireCabinetStatisticsCalculator.Metadata(
                FireCabinetCalculator.Calculate(new FireCabinetParameters()), 0);
            return FireCabinetStatisticsCalculator.Summarize(
                FireComponentStore.Read(FireCabinetCatalog.LegacyItemPrefix, template, "BoxQuantity"));
        }
    }
}
