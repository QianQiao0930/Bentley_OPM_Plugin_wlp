namespace SteelSectionProbe
{
    public sealed partial class NativePipeSupportComponent : Bentley.Building.Mechanical.ComponentLibrary.Supports.Supports
    {
        private static void SaveTrace(string trace) { }
        internal NativePipeSupportRecipe RecipeForCheck { get { return recipe; } }
    }
}
