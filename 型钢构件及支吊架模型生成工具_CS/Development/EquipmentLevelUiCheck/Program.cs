using System;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool condition, string label) { checks++; if (!condition) throw new Exception(label); }
        private static T Control<T>(EquipmentLevelPage page, string name) where T : class { return page.FindName(name) as T; }
        [STAThread] private static int Main(string[] args)
        {
            try
            {
                var page = new EquipmentLevelPage(); NativePanelLayout.Apply(page); page.OnActivated();
                var levels = Control<ComboBox>(page, "LevelCombo"); var mode = Control<ComboBox>(page, "ColorModeCombo");
                var apply = Control<Button>(page, "ApplyButton");
                Check(page.PageId == "equipment-level" && apply.IsEnabled, "注册标识与已读取设备可应用");
                Check(levels.Items.Count == 3 && ((EquipmentLevelChoice)levels.SelectedItem).Id == 1, "文档图层与活动层默认选中");
                Check(Control<TextBlock>(page, "SelectionSummary").Text.Contains("2 台") && Control<TextBlock>(page, "SelectionSummary").Text.Contains("跳过 1"), "设备及拒绝数量");
                Check(mode.SelectedIndex == 0 && Control<Grid>(page, "CustomColorPanel").Visibility == Visibility.Collapsed, "默认随层");
                levels.SelectedIndex = 1; mode.SelectedIndex = 1;
                Control<TextBox>(page, "ColorHexText").Text = "#123456";
                Check(Control<Grid>(page, "CustomColorPanel").Visibility == Visibility.Visible, "指定颜色字段显示");
                Check(((SolidColorBrush)Control<Border>(page, "ColorSwatch").Background).Color == Color.FromRgb(0x12,0x34,0x56), "颜色预览");
                bool closeBlocked = false, progressSeen = false;
                Fixture.DuringApply = delegate
                {
                    Check(page.IsBusy && !apply.IsEnabled && !levels.IsEnabled, "处理中禁用重复操作");
                    progressSeen = Control<TextBlock>(page, "StageText").Text.Contains("读取") &&
                        Control<ProgressBar>(page, "WorkProgress").IsIndeterminate && Control<TextBlock>(page, "ElapsedText").Text.Contains("用时");
                    try { page.OnDeactivated(); } catch (InvalidOperationException) { closeBlocked = true; }
                };
                Click(apply);
                Check(closeBlocked && progressSeen, "处理中反馈可见且离开受保护");
                Check(Fixture.Applied.TargetLevelId == 2 && Fixture.Applied.ColorMode == EquipmentColorMode.CustomRgb && Fixture.Applied.Rgb == 0x123456, "页面选项传递到业务层");
                Check(!page.IsBusy && apply.IsEnabled && Control<ProgressBar>(page, "WorkProgress").Value == 100, "完成恢复控件及100进度");
                Check(Control<TextBox>(page, "ResultText").Text.Contains("120"), "展示结果");
                Fixture.DuringApply = null; mode.SelectedIndex = 2; Click(apply);
                Check(Fixture.Applied.ColorMode == EquipmentColorMode.KeepOriginal, "保持原色选项");
                mode.SelectedIndex = 1; Control<TextBox>(page, "ColorHexText").Text = "#xyz";
                int calls = Fixture.ApplyCalls; Click(apply); Check(Fixture.ApplyCalls == calls && !page.IsBusy, "非法颜色不进入写入");
                Control<TextBox>(page, "ColorHexText").Text = "#7FA37C";
                Fixture.FailApply = true; Click(apply);
                Check(Control<TextBlock>(page, "StageText").Text == "处理未完成" && Control<ProgressBar>(page, "WorkProgress").Value == 0, "失败不显示成功进度");
                Check(Control<TextBox>(page, "ResultText").Text.Contains("回滚"), "失败结果可见");
                Fixture.FailApply = false;
                Bentley.DgnPlatformNET.TransactionManager.Undo(); Check(!apply.IsEnabled, "撤销后重新读取");
                Click(Control<Button>(page, "ReadSelectionButton")); Check(apply.IsEnabled, "重新读取恢复可用");
                Fixture.Model = new Bentley.DgnPlatformNET.DgnModel();
                Invoke(page, "Timer_Tick", null, EventArgs.Empty); Check(!apply.IsEnabled, "切换模型清空旧选择");
                Click(Control<Button>(page, "ReadSelectionButton")); levels.SelectedIndex = 1;
                // 截图和几何检查使用真实页面，模拟服务只提供文档/设备展示数据。
                string output = Path.GetFullPath(args.Length == 0 ? "previews" : args[0]); Directory.CreateDirectory(output);
                foreach (var size in new[] { new Size(400,560), new Size(400,600), new Size(400,880), new Size(400,1080), new Size(520,720) })
                {
                    page.Measure(size); page.Arrange(new Rect(new Point(),size)); page.UpdateLayout();
                    page.Dispatcher.Invoke(delegate { }, DispatcherPriority.Render);
                    Point pos = apply.TranslatePoint(new Point(),page);
                    Check(pos.Y >= 0 && pos.Y + apply.ActualHeight <= size.Height, "应用按钮固定且可见 " + size);
                    Check(pos.X >= 0 && pos.X + apply.ActualWidth <= size.Width, "应用按钮不溢出 " + size);
                    Check(TextContains(levels, "E-TNK") && !TextContains(levels, "SteelSectionProbe"), "目标层显示名称而非类型名 " + size);
                    var scroll = Control<ScrollViewer>(page,"ParameterScroll"); double y = pos.Y;
                    scroll.ScrollToBottom(); page.UpdateLayout();
                    Check(Math.Abs(apply.TranslatePoint(new Point(),page).Y-y)<.1, "参数滚动不移动操作区 " + size);
                    scroll.ScrollToTop(); page.UpdateLayout();
                    foreach (double dpi in new[] { 1d,1.25,1.5,2 })
                    {
                        var bmp = new RenderTargetBitmap((int)(size.Width*dpi),(int)(size.Height*dpi),96*dpi,96*dpi,PixelFormats.Pbgra32); bmp.Render(page);
                        Check(bmp.PixelWidth == (int)(size.Width*dpi), "DPI渲染 " + size + " " + dpi);
                        if (dpi == 1) { var png = new PngBitmapEncoder(); png.Frames.Add(BitmapFrame.Create(bmp)); using(var file=File.Create(Path.Combine(output,"equipment-level-"+size.Width+"x"+size.Height+".png"))) png.Save(file); }
                    }
                }
                page.OnDeactivated(); Check(!apply.IsEnabled, "离开清理选择与事件");
                Console.WriteLine("EquipmentLevelUiCheck: " + checks + " checks passed; real XAML and page lifecycle, host services use fixtures.");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
        private static void Click(Button button) { button.RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); }
        private static bool TextContains(DependencyObject element, string text)
        {
            var block = element as TextBlock;
            if (block != null && block.Text.Contains(text)) return true;
            for (int i = 0; i < VisualTreeHelper.GetChildrenCount(element); i++)
                if (TextContains(VisualTreeHelper.GetChild(element, i), text)) return true;
            return false;
        }
        private static void Invoke(object target, string method, params object[] args)
        { target.GetType().GetMethod(method,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(target,args); }
    }
}
