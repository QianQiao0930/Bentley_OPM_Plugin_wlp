using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace SteelSectionProbe
{
    internal static class NativePanelLayoutChecks
    {
        internal static void Verify(FrameworkElement root, UserControl page, Action<bool, string> check)
        {
            NativePanelLayout.Apply(page);
            NativePanelLayout.Apply(page); // Switching back to an existing page is idempotent.
            foreach (Size size in new[] { new Size(400, 560), new Size(400, 600), new Size(520, 720), new Size(400, 1080) })
            {
                root.Measure(size); root.Arrange(new Rect(new Point(), size)); root.UpdateLayout();
                root.Dispatcher.Invoke(() => { }, DispatcherPriority.Background); root.UpdateLayout();
                var footer = (FrameworkElement)root.FindName("WorkspaceFooter");
                Point pos = footer.TranslatePoint(new Point(), root);
                check(pos.Y >= 0 && Math.Abs(pos.Y + footer.ActualHeight - (size.Height - 1)) < 1.1,
                    "停靠底栏随高度贴底 " + page.GetType().Name + size);
                var confirm = page.FindName("ConfirmButton") as Button;
                if (confirm != null && confirm.IsVisible)
                {
                    Point button = confirm.TranslatePoint(new Point(), root);
                    check(button.Y >= 0 && button.Y + confirm.ActualHeight <= pos.Y + .1,
                        "停靠确认按钮可见 " + page.GetType().Name + size);
                }
                foreach (double dpi in new[] { 1d, 1.25, 1.5, 2 })
                {
                    var bitmap = new RenderTargetBitmap((int)(size.Width * dpi), (int)(size.Height * dpi),
                        96 * dpi, 96 * dpi, PixelFormats.Pbgra32);
                    bitmap.Render(root);
                    check(bitmap.PixelHeight == (int)(size.Height * dpi), "停靠尺寸DPI " + page.GetType().Name + size + dpi);
                }
            }
            root.Measure(new Size(400, 880)); root.Arrange(new Rect(0, 0, 400, 880)); root.UpdateLayout();
        }
    }
}
