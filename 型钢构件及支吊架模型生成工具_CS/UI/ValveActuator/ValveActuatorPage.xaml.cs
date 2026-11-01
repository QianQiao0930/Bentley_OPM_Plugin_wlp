using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace SteelSectionProbe
{
    internal partial class ValveActuatorPage : UserControl, IWorkspacePage, IWorkspaceBusyPage
    {
        private string libraryPath;
        private bool active, busy, loading, wasPlacing;
        private readonly DispatcherTimer contextTimer;
        public string PageId { get { return "valve-actuator"; } }
        public string PageTitle { get { return "阀门执行机构"; } }
        public string PageSubtitle { get { return "选择 CEL 外形，点选阀门安装"; } }
        public FrameworkElement View { get { return this; } }
        public bool IsBusy { get { return busy; } }

        internal ValveActuatorPage()
        {
            InitializeComponent();
            contextTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
            contextTimer.Tick += Context_Tick;
            CellPreview.Failed += PreviewFailed;
        }
        public void OnActivated() { if (active) return; active = true; contextTimer.Start(); RefreshPreview(); UpdateEnabled(); }
        public void OnDeactivated()
        {
            if (busy) throw new InvalidOperationException("正在读取单元库或启动官方工具，请稍候。");
            if (!active) return;
            ValveActuatorPlacement.End();
            CellPreview.Clear("选择单元后显示真实几何。");
            active = false; wasPlacing = false; contextTimer.Stop();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }

        private void Browse_Click(object sender, RoutedEventArgs args)
        {
            if (!active || busy) return;
            try
            {
                ValveActuatorPlacement.End();
                using (var dialog = new System.Windows.Forms.OpenFileDialog { Filter = "CEL 单元库 (*.cel)|*.cel", Title = "选择执行机构 CEL 单元库",
                    FileName = libraryPath ?? string.Empty, CheckFileExists = true, Multiselect = false })
                {
                    if (dialog.ShowDialog(MainWindow.Current) != System.Windows.Forms.DialogResult.OK) return;
                    libraryPath = dialog.FileName;
                }
                ReadLibrary();
            }
            catch (Exception error) { Report(error.Message, true); }
            finally { UpdateEnabled(); }
        }
        private void Refresh_Click(object sender, RoutedEventArgs args) { ReadLibrary(); }
        private void ReadLibrary()
        {
            if (!active || busy || string.IsNullOrEmpty(libraryPath)) return;
            try
            {
                ValveActuatorPlacement.End();
                busy = true; loading = true; UpdateEnabled();
                string previous = (CellCombo.SelectedItem as CelLibraryEntry)?.Name;
                // Clear first: an unreadable new library must never leave an old item enabled.
                CellCombo.ItemsSource = null;
                LibraryPathText.Text = libraryPath;
                var catalog = CelLibraryReader.Read(libraryPath);
                CellCombo.ItemsSource = catalog.Entries;
                CellCombo.SelectedItem = catalog.Entries.FirstOrDefault(item => item.Name == previous) ?? catalog.Entries.FirstOrDefault();
                LibraryCountText.Text = "01 / 单元库 · 共 " + catalog.Count + " 种";
                Report(catalog.Count == 0 ? "该文件没有可放置三维单元，请选择其他 CEL。" : "请选择执行机构单元，再点击开始放置。", false);
            }
            catch (Exception error)
            {
                CellCombo.ItemsSource = null; LibraryCountText.Text = "01 / 单元库 · 读取失败";
                Report(error.Message, true);
            }
            finally { busy = false; loading = false; RefreshPreview(); UpdateEnabled(); }
        }
        private void Cell_Changed(object sender, SelectionChangedEventArgs args)
        {
            if (!active || loading || busy) return;
            try { ValveActuatorPlacement.End(); RefreshPreview(); }
            catch (Exception error) { Report(error.Message, true); }
            UpdateEnabled();
        }
        private void RefreshPreview()
        {
            if (!active || busy) return;
            var entry = CellCombo.SelectedItem as CelLibraryEntry;
            if (entry == null)
            {
                CellPreview.Clear("选择单元后显示真实几何。"); PreviewText.Text = "尚未选择单元。";
                UnitText.Text = "读取文件后选择需要安装的执行机构。"; return;
            }
            UnitText.Text = "源单位：" + entry.UnitText + " · " + entry.UorPerMasterUnit + " UOR/主单位";
            PreviewText.Text = entry.Name + " · 使用单元原点安装";
            try { CellPreview.ShowCell(entry, 0); }
            catch (Exception error) { PreviewFailed(error.Message); }
        }
        private void PreviewFailed(string message)
        {
            if (!active) return;
            PreviewText.Text = "预览失败，仍可尝试放置：" + message;
        }
        private void Iso_Click(object sender, RoutedEventArgs args) { CellPreview.SetTopView(false); }
        private void Top_Click(object sender, RoutedEventArgs args) { CellPreview.SetTopView(true); }
        private void Start_Click(object sender, RoutedEventArgs args)
        {
            if (!active || busy) return;
            busy = true; UpdateEnabled();
            try
            {
                Report(ValveActuatorPlacement.Start(CellCombo.SelectedItem as CelLibraryEntry), false);
                wasPlacing = ValveActuatorPlacement.IsActive;
            }
            catch (Exception error) { ValveActuatorLog.Write("ui-start-failed", error.ToString()); Report(error.Message, true); }
            finally { busy = false; UpdateEnabled(); }
        }
        private void End_Click(object sender, RoutedEventArgs args)
        {
            try { ValveActuatorPlacement.End(); wasPlacing = false; Report("已结束官方放置，可重新选择执行机构。", false); }
            catch (Exception error) { Report(error.Message, true); }
            UpdateEnabled();
        }
        private void Context_Tick(object sender, EventArgs args)
        {
            if (!active || busy) return;
            try
            {
                ValveActuatorPlacement.CheckContext();
                bool placing = ValveActuatorPlacement.IsActive;
                if (wasPlacing && !placing) Report("官方放置已结束，可重新选择执行机构。", false);
                wasPlacing = placing;
                UpdateEnabled();
            }
            catch (Exception error) { Report(error.Message, true); }
        }
        private void UpdateEnabled()
        {
            if (StartButton == null) return;
            bool placing = active && ValveActuatorPlacement.IsActive;
            bool editable = active && !busy && !placing;
            BrowseButton.IsEnabled = editable;
            RefreshButton.IsEnabled = editable && !string.IsNullOrEmpty(libraryPath);
            CellCombo.IsEnabled = editable && CellCombo.Items.Count > 0;
            var selected = CellCombo.SelectedItem as CelLibraryEntry;
            bool supported = selected != null;
            if (supported) { try { ActuatorCelAssetReader.RequireSupported(selected); } catch { supported = false; } }
            StartButton.IsEnabled = editable && supported;
            StartButton.ToolTip = selected == null ? "请先选择 CEL 文件及库内单元。" : supported ? "启动官方工具后点选阀门。" : "当前单元不受本轮支持：须为 mm、1000 UOR/mm、零 GlobalOrigin 的三维图形单元。";
            EndButton.IsEnabled = active && !busy && placing;
            IsoButton.IsEnabled = TopButton.IsEnabled = active && !busy && selected != null;
        }
        private void Report(string message, bool error)
        {
            PlacementStateText.Text = message;
            MainWindow.Current?.SetStatus(message, error);
        }
    }
}
