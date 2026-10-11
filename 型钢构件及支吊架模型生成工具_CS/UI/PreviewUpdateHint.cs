using System.Windows.Controls;
namespace SteelSectionProbe
{
    internal static class PreviewUpdateHint
    {
        internal static void Set(Button button, bool pending)
        {
            if (button == null) return;
            button.Content = pending ? "更新预览 ●" : "更新预览";
        }
    }
}
