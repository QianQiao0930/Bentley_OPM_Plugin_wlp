using System;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool value, string label) { checks++; if (!value) throw new Exception(label); }
        private static void Reject(Action action, string label) { bool failed = false; try { action(); } catch { failed = true; } Check(failed, label); }
        private static T Control<T>(ValveActuatorPage page, string name) where T : class { return page.FindName(name) as T; }
        private static void Invoke(object target, string name)
        { target.GetType().GetMethod(name, BindingFlags.NonPublic | BindingFlags.Instance).Invoke(target, null); }
        private static void Click(ValveActuatorPage page, string name)
        { Control<Button>(page, name).RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); }

        [STAThread] private static int Main()
        {
            string root = Path.Combine(Path.GetDirectoryName(typeof(Program).Assembly.Location), "artifacts", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            try
            {
                var layout = ActuatorControlLayout.FromBounds(-385, -350, 0, 385, 350, 600, 1);
                Check(layout.HeightMm == 600 && layout.DiameterMm == 770, "control points use millimetre envelope distances instead of 1mm seeds");
                var metreLayout = ActuatorControlLayout.FromBounds(-.385, -.350, 0, .385, .350, .600, 1000);
                Check(Math.Abs(metreLayout.HeightMm - layout.HeightMm) < 0.000001 && Math.Abs(metreLayout.DiameterMm - layout.DiameterMm) < 0.000001, "active metre master units convert once to mm");
                var flatLayout = ActuatorControlLayout.FromBounds(-200, -200, 0, 200, 200, 0, 1);
                Check(flatLayout.HeightMm > 0 && flatLayout.RadiusMm > 0, "flat graphics retain distinct origin and upper controls");
                var tallLayout = ActuatorControlLayout.FromBounds(0, 0, 0, 0, 0, 500, 1);
                Check(tallLayout.RadiusMm > 0 && tallLayout.HeightMm > 0, "narrow graphics retain distinct upper and side controls");
                Reject(() => ActuatorControlLayout.FromBounds(0, 0, 0, 0, 0, 0, 1), "empty control envelope rejected");
                Reject(() => ActuatorControlLayout.FromBounds(1, 0, 0, -1, 1, 1, 1), "inverted control envelope rejected");
                Reject(() => ActuatorControlLayout.FromBounds(0, 0, 0, double.NaN, 1, 1, 1), "nonfinite control envelope rejected");
                Reject(() => ActuatorControlLayout.FromBounds(0, 0, 0, 1, 1, 1, 0), "invalid active unit scale rejected");
                byte[] original = { 1, 2, 3, 4 };
                var first = new ActuatorCelAsset(original, "执行机构 A", "deleted.cel");
                original[0] = 9; var exposed = first.CopyBytes(); exposed[1] = 9;
                Check(first.CopyBytes()[0] == 1 && first.CopyBytes()[1] == 2, "asset is detached from caller and returned arrays");
                var second = new ActuatorCelAsset(new byte[] { 5, 6, 7 }, "执行机构 B", "other.cel");
                var firstInstance = new Bentley.ECObjects.Instance.FakeInstance();
                var secondInstance = new Bentley.ECObjects.Instance.FakeInstance();
                ActuatorCelInstanceData.Write(firstInstance, first, "token-A");
                ActuatorCelInstanceData.Write(secondInstance, second, "token-B");
                Check(ActuatorCelInstanceData.Read(firstInstance).CellName == first.CellName
                    && ActuatorCelInstanceData.Read(firstInstance).Hash == first.Hash, "later selection does not replace first instance payload");
                Check(ActuatorCelInstanceData.Read(secondInstance).Hash == second.Hash, "second instance owns second revision");
                Check(firstInstance["TOTAL_HEIGHT"].StringValue == "1" && firstInstance["HANDLE_OFFSET"].DoubleValue == 0, "native setup supports string catalogue fields and offset seed");
                firstInstance["SSP_CEL_DATA"].NativeValue = second.CopyBytes();
                Reject(() => ActuatorCelInstanceData.Read(firstInstance), "persisted payload corruption detected");
                firstInstance["SSP_CEL_DATA"].NativeValue = first.CopyBytes();
                firstInstance["SSP_CEL_SHA256"].StringValue = null;
                Reject(() => ActuatorCelInstanceData.Read(firstInstance), "missing persisted checksum detected");
                firstInstance["SSP_CEL_SHA256"].StringValue = first.Hash;
                firstInstance["SSP_CEL_VERSION"].IntValue = 2;
                Reject(() => ActuatorCelInstanceData.Read(firstInstance), "unknown data version fails");
                string firstPath = first.Materialize(root), secondPath = second.Materialize(root);
                Check(firstPath != secondPath && File.ReadAllBytes(firstPath)[0] == 1, "two revisions coexist without current-selection substitution");
                Check(first.Materialize(root) == firstPath, "same revision reuses validated immutable cache");
                File.Delete(firstPath);
                Check(File.Exists(first.Materialize(root)), "instance payload can restore cache without original source");
                File.WriteAllText(firstPath, "corrupt");
                Reject(() => first.Materialize(root), "cache corruption fails instead of silently accepting other geometry");
                Reject(() => new ActuatorCelAsset(second.CopyBytes(), first.CellName, "", first.Hash), "wrong persisted checksum fails");
                Reject(() => new ActuatorCelAsset(new byte[0], "A", ""), "empty payload fails");
                Reject(() => new ActuatorCelAsset(new byte[ActuatorCelAsset.MaxBytes + 1], "A", ""), "oversize payload fails");
                Reject(() => new ActuatorCelAsset(new byte[] { 1 }, "", ""), "missing model name fails");
                Reject(() => ActuatorCelAssetReader.RequireSupported(CelLibraryReader.Entry("", "A", "m")), "unsupported units fail");
                Reject(() => ActuatorCelAssetReader.RequireSupported(CelLibraryReader.Entry("", "A", "mm", 10000)), "unsupported resolution fails");
                Reject(() => ActuatorCelAssetReader.RequireSupported(CelLibraryReader.Entry("", "A", point: true)), "point cell fails");
                Reject(() => ActuatorCelAssetReader.RequireSupported(CelLibraryReader.Entry("", "A", origin: 2)), "shifted global origin fails");

                var page = new ValveActuatorPage(); NativePanelLayout.Apply(page); page.OnActivated();
                Check(page.PageId == "valve-actuator" && !Control<Button>(page, "StartButton").IsEnabled, "empty selection cannot start");
                typeof(ValveActuatorPage).GetField("libraryPath", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(page, "fixture.cel");
                bool guarded = false;
                CelLibraryReader.DuringRead = () => { guarded = page.IsBusy && !Control<Button>(page, "StartButton").IsEnabled; Reject(page.OnDeactivated, "busy read blocks navigation"); };
                Invoke(page, "ReadLibrary"); CelLibraryReader.DuringRead = null;
                Check(guarded && Control<ComboBox>(page, "CellCombo").Items.Count == 2, "read enumerates model choice while guarding reentry");
                Check(Control<Button>(page, "StartButton").IsEnabled, "selection enables start");
                CelLibraryPreviewControl.Fail = true;
                Control<ComboBox>(page, "CellCombo").SelectedIndex = 1;
                Check(Control<Button>(page, "StartButton").IsEnabled, "picture failure does not block native placement");
                CelLibraryPreviewControl.Fail = false;
                Click(page, "StartButton");
                Check(ValveActuatorPlacement.LastCell == "执行机构 B" && ValveActuatorPlacement.Starts == 1, "starts the selected model instead of hardcoded original");
                Check(!Control<Button>(page, "BrowseButton").IsEnabled && !Control<ComboBox>(page, "CellCombo").IsEnabled && !Control<Button>(page, "StartButton").IsEnabled
                    && Control<Button>(page, "EndButton").IsEnabled, "native interaction locks mutable choice and duplicate start");
                ValveActuatorPlacement.FailEnd = true;
                Reject(page.OnDeactivated, "failed native exit keeps page alive");
                ValveActuatorPlacement.FailEnd = false;
                Click(page, "EndButton");
                Check(Control<Button>(page, "StartButton").IsEnabled && !Control<Button>(page, "EndButton").IsEnabled, "end restores selection");
                CelLibraryReader.Fail = true; Invoke(page, "ReadLibrary");
                Check(Control<ComboBox>(page, "CellCombo").Items.Count == 0 && !Control<Button>(page, "StartButton").IsEnabled, "failed library refresh discards stale selection");
                CelLibraryReader.Fail = false; Invoke(page, "ReadLibrary");
                Render(page, 400, 720, 1, root); Render(page, 400, 880, 1.25, root); Render(page, 400, 560, 1.5, root); Render(page, 560, 720, 2, root);
                page.OnDeactivated();
                Check(!ValveActuatorPlacement.IsActive, "leaving ends only feature placement");
                page.OnActivated(); page.OnWorkspaceClosing();
                Console.WriteLine("PASS: " + checks + " asset integrity / real XAML interaction and layout checks; native SDK is substituted; no OPM started.");
                Console.WriteLine("Artifacts=" + root);
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
        private static void Render(ValveActuatorPage page, int width, int height, double dpi, string root)
        {
            page.Measure(new Size(width, height)); page.Arrange(new Rect(0, 0, width, height)); page.UpdateLayout();
            var operations = Control<Border>(page, "OperationCard");
            Point location = operations.TranslatePoint(new Point(0, 0), page);
            Check(location.Y >= 0 && location.Y + operations.ActualHeight <= height + 1, "fixed operation area fits " + width + "x" + height);
            Check(Control<Button>(page, "StartButton").ActualWidth > 100, "start button remains usable " + width);
            var image = new RenderTargetBitmap((int)(width * dpi), (int)(height * dpi), 96 * dpi, 96 * dpi, PixelFormats.Pbgra32);
            image.Render(page); var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(image));
            using (var output = File.Create(Path.Combine(root, "UI-" + width + "x" + height + "-" + dpi + ".png"))) encoder.Save(output);
        }
    }
}
