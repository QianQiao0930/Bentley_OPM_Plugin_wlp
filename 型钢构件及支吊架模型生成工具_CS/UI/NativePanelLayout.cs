using System.Windows;
using System.Windows.Controls;

namespace SteelSectionProbe
{
    /// <summary>Remove only the redundant window caption; preserve module headers and actions.</summary>
    internal static class NativePanelLayout
    {
        internal static void Apply(FrameworkElement view)
        {
            var page = view as UserControl;
            var grid = page == null ? null : page.Content as Grid;
            if (grid == null || grid.RowDefinitions.Count == 0) return;
            string tag = page.Tag as string;
            if (tag == "home" || tag == "q-support-v4")
            {
                HideCaption(grid);
            }
            else if (tag == "prototype-v4")
            {
                foreach (UIElement child in grid.Children)
                {
                    var chrome = child as UserControl;
                    if (chrome == null || Grid.GetRow(chrome) != 0) continue;
                    var chromeGrid = chrome.Content as Grid;
                    if (chromeGrid == null) continue;
                    HideCaption(chromeGrid);
                    chrome.Height = double.NaN;
                    grid.RowDefinitions[0].Height = GridLength.Auto;
                    break;
                }
            }
        }

        private static void HideCaption(Grid grid)
        {
            grid.RowDefinitions[0].Height = new GridLength(0);
            foreach (UIElement child in grid.Children)
                if (Grid.GetRow(child) == 0) child.Visibility = Visibility.Collapsed;
        }
    }
}
