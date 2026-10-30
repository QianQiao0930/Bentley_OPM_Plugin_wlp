using System;
using System.IO;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Bentley.MstnPlatformNET.InteropServices;
using Com = Bentley.Interop.MicroStationDGN;
using DrawingImage = System.Drawing.Image;
using WpfImage = System.Windows.Controls.Image;
using DrawingColor = System.Drawing.Color;
using Brushes = System.Windows.Media.Brushes;
using PixelFormat = System.Drawing.Imaging.PixelFormat;
using TextBlock = System.Windows.Controls.TextBlock;

namespace SteelSectionProbe
{
    /// <summary>Native CEL graphics rendered to a transparent picture, composed on this white WPF surface.</summary>
    internal sealed class CelLibraryPreviewControl : Border
    {
        private readonly Grid root = new Grid();
        private readonly WpfImage image = new WpfImage { Stretch = Stretch.Uniform,
            HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(8) };
        private readonly TextBlock message = new TextBlock { Text = "选择单元后显示真实几何", Foreground = new SolidColorBrush(System.Windows.Media.Color.FromRgb(91, 107, 123)),
            FontSize = 11, TextWrapping = TextWrapping.Wrap, HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(12), TextAlignment = TextAlignment.Center };
        private CelLibraryEntry entry;
        private double angle;
        private bool topView;
        public bool IsReady { get; private set; }
        internal event Action<string> Failed;

        public CelLibraryPreviewControl()
        {
            Background = Brushes.White; BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(221, 227, 234));
            BorderThickness = new Thickness(1); CornerRadius = new CornerRadius(4); ClipToBounds = true;
            RenderOptions.SetBitmapScalingMode(image, BitmapScalingMode.HighQuality);
            root.Children.Add(message); Child = root;
        }

        internal void ShowCell(CelLibraryEntry selected, double angleDegrees)
        {
            bool sameSelection = ReferenceEquals(entry, selected) && angle == angleDegrees;
            entry = selected; angle = angleDegrees;
            try { RenderCell(selected, angleDegrees); }
            catch (Exception ex)
            {
                CelLibraryLog.Write("preview-failed", "cell=" + selected.Name + "; top=" + topView + "; " + ex);
                if (!sameSelection) ShowMessage("预览显示失败；仍可放置。\n" + ex.Message);
                throw;
            }
        }
        private void RenderCell(CelLibraryEntry selected, double angleDegrees)
        {
            // The same offline factory is used for placement. Only this private preview copy is rotated into view.
            var cell = CelLibraryGeometry.CreatePreview(selected, angleDegrees);
            var bounds = cell.Range;
            var center = new Com.Point3d { X = (bounds.Low.X + bounds.High.X) / 2,
                Y = (bounds.Low.Y + bounds.High.Y) / 2, Z = (bounds.Low.Z + bounds.High.Z) / 2 };
            if (!Finite(center.X) || !Finite(center.Y) || !Finite(center.Z)) throw new InvalidOperationException("单元几何范围无效。");
            var move = new Com.Point3d { X = -center.X, Y = -center.Y, Z = -center.Z };
            cell.Move(ref move);
            if (!topView)
            {
                var rotation = new Com.Matrix3d {
                    RowX = new Com.Point3d { X = .7071067811865475, Y = -.7071067811865475, Z = 0 },
                    RowY = new Com.Point3d { X = .408248290463863, Y = .408248290463863, Z = .816496580927726 },
                    RowZ = new Com.Point3d { X = -.5773502691896258, Y = -.5773502691896258, Z = .5773502691896258 } };
                var transform = Utilities.ComApp.Transform3dFromMatrix3d(ref rotation);
                cell.Transform(ref transform);
            }
            // GetPicture uses the actual element graphics and performs native fitting. Suppressing its
            // background avoids the model's black background and any mutation of host view preferences.
            object picture = cell.GetPicture(1024, 1024, false);
            if (picture == null) throw new InvalidOperationException("Bentley 未返回 CEL 几何预览。");
            BitmapSource source;
            using (var rendered = PictureBridge.Read(picture)) source = Compose(rendered);
            CelLibraryLog.Write("preview", "cell=" + selected.Name + "; angle=" + angleDegrees + "; top=" + topView + "; picture=" + source.PixelWidth + "x" + source.PixelHeight);
            image.Source = source;
            IsReady = true;
            root.Children.Clear(); root.Children.Add(image);
            GC.KeepAlive(picture); GC.KeepAlive(cell);
        }

        internal void SetTopView(bool value)
        {
            if (topView == value && IsReady) return;
            bool previousView = topView;
            topView = value;
            if (entry == null) return;
            try { ShowCell(entry, angle); }
            catch (Exception ex)
            {
                // Keep the last successful frozen image and allow this direction to be retried.
                topView = previousView;
                var failed = Failed; if (failed != null) failed(ex.Message);
            }
        }
        internal void Clear(string reason)
        {
            entry = null; ShowMessage(reason ?? "选择单元后显示真实几何");
        }
        private void ShowMessage(string reason)
        {
            IsReady = false; image.Source = null;
            root.Children.Clear(); message.Text = reason; root.Children.Add(message);
        }

        internal static BitmapSource Compose(DrawingImage picture)
        {
            if (picture == null || picture.Width < 1 || picture.Height < 1) throw new InvalidOperationException("CEL 预览图片无效。");
            using (var raster = new Bitmap(1024, 1024, PixelFormat.Format32bppArgb))
            {
                using (var graphics = Graphics.FromImage(raster))
                {
                    graphics.Clear(DrawingColor.Transparent);
                    double pictureScale = Math.Min((double)raster.Width / picture.Width, (double)raster.Height / picture.Height);
                    float pictureWidth = (float)(picture.Width * pictureScale), pictureHeight = (float)(picture.Height * pictureScale);
                    graphics.DrawImage(picture, new RectangleF((raster.Width - pictureWidth) / 2,
                        (raster.Height - pictureHeight) / 2, pictureWidth, pictureHeight));
                }
                var rect = new Rectangle(0, 0, raster.Width, raster.Height);
                var data = raster.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
                int left = raster.Width, top = raster.Height, right = -1, bottom = -1;
                try
                {
                    byte[] pixels = new byte[data.Stride * data.Height]; Marshal.Copy(data.Scan0, pixels, 0, pixels.Length);
                    for (int y = 0; y < raster.Height; y++)
                    for (int x = 0; x < raster.Width; x++)
                    {
                        int i = y * data.Stride + x * 4;
                        if (pixels[i + 3] < 8) continue;
                        left = Math.Min(left, x); right = Math.Max(right, x); top = Math.Min(top, y); bottom = Math.Max(bottom, y);
                        // A white source pen needs contrast on the preview's white surface.
                        // This changes only picture pixels; source and placed-cell symbology are untouched.
                        if (pixels[i] > 240 && pixels[i + 1] > 240 && pixels[i + 2] > 240)
                        { pixels[i] = 72; pixels[i + 1] = 55; pixels[i + 2] = 43; }
                    }
                    Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
                }
                finally { raster.UnlockBits(data); }
                if (right < left || bottom < top) throw new InvalidOperationException("单元中没有可显示的预览图形。");
                // Crop to actual ink, then center and fit it with equal padding, irrespective of CEL origin.
                var crop = Rectangle.FromLTRB(left, top, right + 1, bottom + 1);
                int padding = Math.Max(4, (int)Math.Ceiling(Math.Max(crop.Width, crop.Height) / 32.0));
                using (var result = new Bitmap(crop.Width + 2 * padding, crop.Height + 2 * padding, PixelFormat.Format32bppArgb))
                {
                    using (var graphics = Graphics.FromImage(result))
                    {
                        graphics.Clear(DrawingColor.White);
                        graphics.DrawImage(raster, new Rectangle(padding, padding, crop.Width, crop.Height), crop, GraphicsUnit.Pixel);
                    }
                    using (var stream = new MemoryStream())
                    {
                        result.Save(stream, ImageFormat.Png); stream.Position = 0;
                        var source = new BitmapImage(); source.BeginInit(); source.CacheOption = BitmapCacheOption.OnLoad;
                        source.StreamSource = stream; source.EndInit(); source.Freeze(); return source;
                    }
                }
            }
        }
        private static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
        internal static DrawingImage ReadPicture(object picture) { return PictureBridge.Read(picture); }
        private static class PictureBridge
        {
            internal static DrawingImage Read(object picture)
            {
                var direct = picture as DrawingImage;
                if (direct != null) return (DrawingImage)direct.Clone();
                var native = picture as IOlePicture;
                if (native == null) throw new InvalidOperationException("Bentley 返回了不支持的预览图片类型。");
                int width, height;
                Marshal.ThrowExceptionForHR(native.GetWidth(out width));
                Marshal.ThrowExceptionForHR(native.GetHeight(out height));
                if (width <= 0 || height <= 0) throw new InvalidOperationException("预览图片尺寸无效。");
                // Render the borrowed OLE picture directly into our own DCs. Do not construct or dispose
                // a GDI+ Metafile wrapper over Bentley's cached WMF/EMF handle.
                using (var black = Render(native, width, height, DrawingColor.Black))
                using (var white = Render(native, width, height, DrawingColor.White))
                {
                    var dark = ReadPixels(black); var light = ReadPixels(white);
                    var pixels = new byte[dark.Length];
                    for (int i = 0; i < pixels.Length; i += 4)
                    {
                        int difference = Math.Max(light[i] - dark[i], Math.Max(light[i + 1] - dark[i + 1], light[i + 2] - dark[i + 2]));
                        int alpha = Math.Max(0, Math.Min(255, 255 - difference));
                        if (alpha < 8) continue;
                        pixels[i + 3] = (byte)alpha;
                        for (int channel = 0; channel < 3; channel++)
                            pixels[i + channel] = (byte)Math.Min(255, dark[i + channel] * 255 / alpha);
                    }
                    var result = new Bitmap(1024, 1024, PixelFormat.Format32bppArgb);
                    var data = result.LockBits(new Rectangle(0, 0, 1024, 1024), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
                    try { Marshal.Copy(pixels, 0, data.Scan0, pixels.Length); }
                    finally { result.UnlockBits(data); }
                    GC.KeepAlive(picture); return result;
                }
            }
            private static Bitmap Render(IOlePicture picture, int sourceWidth, int sourceHeight, DrawingColor background)
            {
                var bitmap = new Bitmap(1024, 1024, PixelFormat.Format32bppRgb);
                try
                {
                    using (var graphics = Graphics.FromImage(bitmap))
                    {
                        graphics.Clear(background);
                        double scale = Math.Min(1024.0 / sourceWidth, 1024.0 / sourceHeight);
                        int width = Math.Max(1, (int)Math.Round(sourceWidth * scale));
                        int height = Math.Max(1, (int)Math.Round(sourceHeight * scale));
                        IntPtr dc = graphics.GetHdc();
                        try { Marshal.ThrowExceptionForHR(picture.Render(dc, (1024 - width) / 2, (1024 - height) / 2,
                            width, height, 0, sourceHeight, sourceWidth, -sourceHeight, IntPtr.Zero)); }
                        finally { graphics.ReleaseHdc(dc); }
                    }
                    return bitmap;
                }
                catch { bitmap.Dispose(); throw; }
            }
            private static byte[] ReadPixels(Bitmap bitmap)
            {
                var data = bitmap.LockBits(new Rectangle(0, 0, bitmap.Width, bitmap.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppRgb);
                try { var bytes = new byte[data.Stride * data.Height]; Marshal.Copy(data.Scan0, bytes, 0, bytes.Length); return bytes; }
                finally { bitmap.UnlockBits(data); }
            }
        }
        // IPicture's IUnknown vtable, in ocidl.h order. OLE_HANDLE is a 32-bit int even in 64-bit hosts;
        // HDC and RECT pointers in Render are pointer-sized. Width/height/source coordinates are HIMETRIC.
        [ComImport, Guid("7BF80980-BF32-101A-8BBB-00AA00300CAB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IOlePicture
        {
            [PreserveSig] int GetHandle(out int handle);
            [PreserveSig] int GetPalette(out int palette);
            [PreserveSig] int GetPictureType(out short type);
            [PreserveSig] int GetWidth(out int width);
            [PreserveSig] int GetHeight(out int height);
            [PreserveSig] int Render(IntPtr dc, int x, int y, int width, int height,
                int sourceX, int sourceY, int sourceWidth, int sourceHeight, IntPtr bounds);
        }
    }
}
