using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class CelLibraryPage : UserControl, IWorkspacePage, IWorkspaceBusyPage
    {
        private CelLibraryCatalog catalog;
        private CelStatisticsSnapshot statistics;
        private DgnModel model;
        private string libraryPath;
        private bool active, loading = true, busy;
        private int placedThisRun;
        private readonly DispatcherTimer contextTimer;
        private readonly DispatcherTimer previewTimer;
        public string PageId { get { return "cel-library"; } }
        public string PageTitle { get { return "CEL 构件库放置"; } }
        public string PageSubtitle { get { return "选取库单元，预览并连续放置，附加项统计数量"; } }
        public FrameworkElement View { get { return this; } }
        public bool IsBusy { get { return busy; } }

        internal CelLibraryPage()
        {
            InitializeComponent();
            libraryPath = CelLibraryReader.DefaultLibraryPath;
            LibraryPathText.Text = libraryPath;
            contextTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
            contextTimer.Tick += Context_Tick;
            previewTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(180) };
            previewTimer.Tick += Preview_Tick;
            CellPreview.Failed += Preview_Failed;
            loading = false;
        }

        public void OnActivated()
        {
            if (active) return;
            active = true;
            CelPlacementTool.Placed += Tool_Placed;
            CelPlacementTool.Failed += Tool_Failed;
            CelPlacementTool.Ended += Tool_Ended;
            TransactionManager.OnUndoRedoFinished += UndoFinished;
            try { model = Session.Instance.GetActiveDgnModel(); } catch { model = null; }
            if (catalog == null) ReadLibrary(); else RefreshPreview();
            contextTimer.Start(); UpdateEnabled();
        }
        public void OnDeactivated()
        {
            if (busy) throw new InvalidOperationException("正在读取构件库或统计，请等待完成后离开。");
            if (!active) return;
            CelPlacementTool.End();
            CellPreview.Clear("选择单元后显示真实几何");
            active = false; contextTimer.Stop(); previewTimer.Stop();
            CelPlacementTool.Placed -= Tool_Placed;
            CelPlacementTool.Failed -= Tool_Failed;
            CelPlacementTool.Ended -= Tool_Ended;
            TransactionManager.OnUndoRedoFinished -= UndoFinished;
            model = null; placedThisRun = 0;
            InvalidateStatistics("离开页面后请重新统计。"); UpdateEnabled();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }

        private void Browse_Click(object sender, RoutedEventArgs e)
        {
            if (!active || busy) return;
            using (var dialog = new System.Windows.Forms.OpenFileDialog { Filter = "单元库 (*.cel)|*.cel|所有文件 (*.*)|*.*",
                Title = "选择 CEL 构件库", FileName = libraryPath, CheckFileExists = true, Multiselect = false })
            {
                if (dialog.ShowDialog(MainWindow.Current) != System.Windows.Forms.DialogResult.OK) return;
                libraryPath = dialog.FileName;
            }
            ReadLibrary();
        }
        private void RefreshLibrary_Click(object sender, RoutedEventArgs e) { ReadLibrary(); }
        private void ReadLibrary()
        {
            if (!active || busy) return;
            if (!TryEndPlacement()) return; previewTimer.Stop();
            string previous = (CellCombo.SelectedItem as CelLibraryEntry)?.Name;
            busy = true; loading = true; UpdateEnabled();
            LibraryCountText.Text = "01 / 单元库 · 读取中";
            try
            {
                var fresh = CelLibraryReader.Read(libraryPath);
                catalog = fresh; libraryPath = fresh.LibraryPath; LibraryPathText.Text = libraryPath;
                CellCombo.ItemsSource = fresh.Entries;
                CellCombo.SelectedItem = fresh.Entries.FirstOrDefault(item => item.Name == previous) ?? fresh.Entries.FirstOrDefault();
                LibraryCountText.Text = "01 / 单元库 · 共 " + fresh.Count + " 种";
                LibraryCountText.ToolTip = "可放置单元 " + fresh.Count + " 种；跳过非单元模型 " + fresh.SkippedModelCount + " 个。";
                CategoryText.Text = Path.GetFileNameWithoutExtension(libraryPath);
                PlacementStateText.Text = fresh.Count == 0 ? "该库没有可放置单元，请选择其他 CEL。" : "选择构件，调整角度后开始放置。";
                Status("已读取 " + fresh.Count + " 种 CEL 构件。", false);
            }
            catch (Exception ex)
            {
                catalog = null; CellCombo.ItemsSource = null; LibraryPathText.Text = libraryPath;
                LibraryCountText.Text = "01 / 单元库 · 读取失败";
                TryClearPreview("单元库读取失败，请选择或刷新库文件。"); PreviewInfoText.Text = ex.Message;
                PlacementStateText.Text = ex.Message; Status(ex.Message, true);
            }
            finally { busy = false; loading = false; RefreshPreview(); UpdateEnabled(); }
        }
        private void Cell_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (loading || !active || busy) return;
            if (!TryEndPlacement()) return; previewTimer.Stop(); RefreshPreview();
        }
        private void Angle_Changed(object sender, TextChangedEventArgs e)
        {
            if (loading || !active || busy) return;
            double angle;
            if (!TryAngle(out angle))
            {
                previewTimer.Stop(); if (!TryEndPlacement()) return; TryClearPreview("请输入有效的绕 Z 角度。");
                PreviewInfoText.Text = "角度无效，预览与放置已暂停。"; UpdateEnabled(); return;
            }
            // Coalesce intermediate keystrokes; all Bentley work remains on the host UI thread.
            previewTimer.Stop(); previewTimer.Start();
            UpdatePlacementIfActive(); UpdateEnabled();
        }
        private void Preview_Tick(object sender, EventArgs e) { previewTimer.Stop(); RefreshPreview(); }
        private void MinusAngle_Click(object sender, RoutedEventArgs e) { StepAngle(-90); }
        private void PlusAngle_Click(object sender, RoutedEventArgs e) { StepAngle(90); }
        private void StepAngle(double increment)
        {
            double angle; if (!TryAngle(out angle)) angle = 0;
            AngleText.Text = Normalize(angle + increment).ToString("0.########", CultureInfo.InvariantCulture);
            previewTimer.Stop(); RefreshPreview();
        }
        private void Metadata_Changed(object sender, TextChangedEventArgs e)
        { if (!loading && active && !busy) { UpdatePlacementIfActive(); UpdateEnabled(); } }
        private void IsoView_Click(object sender, RoutedEventArgs e) { CellPreview.SetTopView(false); }
        private void TopView_Click(object sender, RoutedEventArgs e) { CellPreview.SetTopView(true); }

        private void RefreshPreview()
        {
            if (!active || busy) return;
            var entry = CellCombo.SelectedItem as CelLibraryEntry;
            double angle;
            if (entry == null || !TryAngle(out angle))
            { TryClearPreview(entry == null ? "选择单元后显示真实几何" : "请输入有效的绕 Z 角度。"); UpdateEnabled(); return; }
            try
            {
                CellPreview.ShowCell(entry, angle);
                PreviewInfoText.Text = entry.Name + " · " + Normalize(angle).ToString("0.##", CultureInfo.InvariantCulture) + "° · 原点放置";
                DirectionText.Text = "中心轴固定世界 +Z；绕 Z 角度 " + Normalize(angle).ToString("0.##", CultureInfo.InvariantCulture) + "°。";
                UpdatePlacementIfActive();
            }
            catch (Exception ex)
            { Preview_Failed(ex.Message); }
            UpdateEnabled();
        }
        private void Preview_Failed(string error)
        {
            if (!active) return;
            PreviewInfoText.Text = "预览显示失败，仍可放置：" + error;
            Status(PreviewInfoText.Text, true); UpdateEnabled();
        }
        private void Start_Click(object sender, RoutedEventArgs e)
        {
            if (!active || busy) return;
            try
            {
                if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
                previewTimer.Stop();
                var selected = CellCombo.SelectedItem as CelLibraryEntry;
                double angle;
                if (selected == null || !TryAngle(out angle)) throw new InvalidOperationException("请选择单元并输入有效角度。");
                // Validate actual offline cell creation, independently of picture rendering.
                CelLibraryGeometry.Create(selected, DPoint3d.Zero, angle);
                StartOrUpdatePlacement();
                PlacementStateText.Text = "左键放置一套，继续点击可连续放置；右键结束。";
                Status("已清空旧选择，请在模型中点击 CEL 原点的安装位置。", false);
            }
            catch (Exception ex) { PlacementStateText.Text = ex.Message; Status(ex.Message, true); }
            UpdateEnabled();
        }
        private void StartOrUpdatePlacement()
        {
            var entry = CellCombo.SelectedItem as CelLibraryEntry;
            double angle;
            if (entry == null || !TryAngle(out angle)) throw new InvalidOperationException("请选择单元并输入有效角度。");
            var metadata = new CelPlacementMetadata { LibraryFileName = Path.GetFileName(entry.LibraryPath), CellName = entry.Name,
                Category = CategoryText.Text.Trim(), Specification = SpecificationText.Text.Trim(), RotationDegrees = Normalize(angle) };
            CelPlacementTool.Begin(point => CelLibraryGeometry.Create(entry, point, angle), metadata);
        }
        private void UpdatePlacementIfActive()
        {
            if (!CelPlacementTool.IsActive) return;
            try { StartOrUpdatePlacement(); }
            catch (Exception ex) { TryEndPlacement(); PlacementStateText.Text = ex.Message; Status(ex.Message, true); }
        }
        private void End_Click(object sender, RoutedEventArgs e) { TryEndPlacement(); UpdateEnabled(); }
        private void Tool_Ended()
        { PlacementStateText.Text = "已结束放置；本次已放置 " + placedThisRun + " 套。"; UpdateEnabled(); }
        private void Tool_Failed(string error)
        { PlacementStateText.Text = error; Status(error, true); UpdateEnabled(); }
        private void Tool_Placed(CelPlacementResult result)
        {
            placedThisRun++;
            PlacementStateText.Text = "已放置 " + result.CellName + "；本次 " + placedThisRun + " 套，继续点击放置。";
            InvalidateStatistics("模型已更新，请刷新统计。已放置构件可以撤销。");
            Status(PlacementStateText.Text, false); UpdateEnabled();
        }

        private void ReadStatistics_Click(object sender, RoutedEventArgs e) { ReadStatistics(); }
        private void StatsScope_Changed(object sender, SelectionChangedEventArgs e)
        { if (!loading) InvalidateStatistics("统计范围已改变，请刷新统计。"); }
        private void ReadStatistics()
        {
            if (!active || busy) return;
            busy = true; UpdateEnabled(); StatisticsCountText.Text = "统计中…";
            try
            {
                statistics = CelComponentStore.Read(StatsScopeCombo.SelectedIndex == 1);
                StatisticsCountText.Text = "合计 " + statistics.TotalQuantity.ToString(CultureInfo.InvariantCulture) + " 套 · " + statistics.InstanceCount + " 个实例";
                var text = new StringBuilder();
                foreach (var row in statistics.Rows)
                    text.AppendLine(row.CellName + " · " + row.Quantity.ToString(CultureInfo.InvariantCulture) + " 套" +
                        (string.IsNullOrWhiteSpace(row.Specification) ? "" : " · " + row.Specification) +
                        Environment.NewLine + "  " + row.ModelName + " [" + row.ElementId + "] · " + row.LibraryFileName);
                StatisticsText.Text = statistics.InstanceCount == 0 ? "该范围内没有带本功能附加项的构件。参考文件不计入。" : text.ToString().TrimEnd();
                Status("CEL 构件统计完成，合计 " + statistics.TotalQuantity + " 套。", false);
            }
            catch (Exception ex)
            { statistics = null; StatisticsCountText.Text = "统计失败"; StatisticsText.Text = ex.Message; Status(ex.Message, true); }
            finally { busy = false; UpdateEnabled(); }
        }
        private void Export_Click(object sender, RoutedEventArgs e)
        {
            if (busy || statistics == null) return;
            using (var dialog = new System.Windows.Forms.SaveFileDialog { Title = "导出 CEL 构件统计", Filter = "CSV 表格 (*.csv)|*.csv|JSON 数据 (*.json)|*.json",
                FileName = "CEL构件统计.csv", AddExtension = true, OverwritePrompt = true })
            {
                if (dialog.ShowDialog(MainWindow.Current) != System.Windows.Forms.DialogResult.OK) return;
                try
                {
                    if (dialog.FilterIndex == 2) CelStatisticsExporter.WriteJson(dialog.FileName, statistics);
                    else CelStatisticsExporter.WriteCsv(dialog.FileName, statistics);
                    Status("已导出：" + dialog.FileName, false);
                }
                catch (Exception ex) { Status(ex.Message, true); }
            }
        }
        private void InvalidateStatistics(string reason)
        { statistics = null; StatisticsCountText.Text = "尚未统计"; StatisticsText.Text = reason; if (ExportButton != null) ExportButton.IsEnabled = false; }
        private void UndoFinished(object sender, EventArgs e)
        { if (active && !busy) { placedThisRun = 0; InvalidateStatistics("已撤销或重做，请刷新统计。数量以当前模型中的实际构件为准。"); PlacementStateText.Text = "模型已撤销或重做，当前数量请刷新统计。"; } }
        private void Context_Tick(object sender, EventArgs e)
        {
            if (!active || busy) return;
            DgnModel current = null; try { current = Session.Instance.GetActiveDgnModel(); } catch { }
            if (ReferenceEquals(current, model)) return;
            previewTimer.Stop(); if (!TryEndPlacement()) return;
            if (!TryClearPreview(current == null ? "请先打开三维模型。" : "活动模型已切换，正在更新预览…")) return;
            model = current; placedThisRun = 0;
            InvalidateStatistics("活动文档或模型已改变，请重新统计。"); RefreshPreview(); UpdateEnabled();
        }
        private bool TryEndPlacement()
        {
            try { CelPlacementTool.End(); return true; }
            catch (Exception ex) { ReportCleanupFailure(ex); return false; }
            finally { UpdateEnabled(); }
        }
        private bool TryClearPreview(string reason)
        {
            try { CellPreview.Clear(reason); return true; }
            catch (Exception ex) { ReportCleanupFailure(ex); return false; }
        }
        private void ReportCleanupFailure(Exception ex)
        {
            PlacementStateText.Text = "清理失败，请点击结束或关闭重试：" + ex.Message;
            Status(PlacementStateText.Text, true);
        }
        private bool TryAngle(out double angle)
        {
            string text = AngleText == null ? "" : AngleText.Text;
            return double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out angle) && !double.IsNaN(angle) && !double.IsInfinity(angle);
        }
        private static double Normalize(double angle) { return ((angle % 360) + 360) % 360; }
        private void UpdateEnabled()
        {
            if (StartButton == null || EndButton == null) return;
            double angle;
            StartButton.IsEnabled = active && !busy && CellCombo.SelectedItem is CelLibraryEntry && TryAngle(out angle);
            EndButton.IsEnabled = active && !busy && CelPlacementTool.NeedsCleanup;
            BrowseButton.IsEnabled = RefreshLibraryButton.IsEnabled = CellCombo.IsEnabled = !busy;
            AngleText.IsEnabled = MinusAngleButton.IsEnabled = PlusAngleButton.IsEnabled = !busy;
            CategoryText.IsEnabled = SpecificationText.IsEnabled = !busy;
            StatsScopeCombo.IsEnabled = ReadStatisticsButton.IsEnabled = !busy;
            ExportButton.IsEnabled = !busy && statistics != null;
            PageChrome.IsEnabled = !busy;
        }
        private static void Status(string text, bool error)
        { if (MainWindow.Current != null) MainWindow.Current.SetStatus(text, error); }
    }
}
