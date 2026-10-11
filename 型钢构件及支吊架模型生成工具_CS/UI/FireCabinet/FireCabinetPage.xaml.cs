using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Bentley.GeometryNET;
using Microsoft.Win32;

namespace SteelSectionProbe
{
    /// <summary>
    /// 选型、放置、预览确认及消防统计的工作区页面。
    /// </summary>
    internal partial class FireCabinetPage : UserControl, IWorkspacePage
    {
        private readonly FireCabinetPreviewSession preview = new FireCabinetPreviewSession();
        private bool ready;
        private bool active;
        private bool locating;
        private bool dirty;
        private int revision;
        private DPoint3d? origin;
        private FireCabinetSnapshot snapshot;

        public string PageId
        {
            get
            {
                return "fire-cabinet";
            }
        }
        public string PageTitle
        {
            get
            {
                return "灭火器箱";
            }
        }
        public string PageSubtitle
        {
            get
            {
                return "XMDDG 翻盖式箱体 · 两具灭火器外观模型 · 消防清单";
            }
        }
        public FrameworkElement View
        {
            get
            {
                return this;
            }
        }

        internal FireCabinetPage()
        {
            InitializeComponent();
            TypeCombo.ItemsSource = FireCabinetCatalog.Types;
            TypeCombo.SelectedIndex = 0;
            CapacityCombo.ItemsSource = FireCabinetCatalog.Capacities(SelectedType);
            CapacityCombo.SelectedIndex = 0;
            SetBoxes();
            ready = true;
            PageLastInput.Restore(this, PageId, "TypeCombo", "CapacityCombo", "BoxCombo", "HeadingText");
            Describe();
        }

        private string SelectedType
        {
            get
            {
                return TypeCombo.SelectedItem as string ?? FireCabinetCatalog.Types[0];
            }
        }
        private int SelectedCapacity
        {
            get
            {
                return CapacityCombo.SelectedItem is int ? (int)CapacityCombo.SelectedItem : 2;
            }
        }

        public void OnActivated()
        {
            if (active)
            {
                return;
            }
            active = true;
            FireCabinetPlacementTool.Picked += OnPicked;
            FireCabinetPlacementTool.Ended += OnEnded;
        }

        public void OnDeactivated()
        {
            Close();
        }
        public void OnWorkspaceClosing()
        {
            Close();
        }

        private void Close()
        {
            PageLastInput.Save(this, PageId, "TypeCombo", "CapacityCombo", "BoxCombo", "HeadingText");
            revision++;
            active = false;
            FireCabinetPlacementTool.Picked -= OnPicked;
            FireCabinetPlacementTool.Ended -= OnEnded;
            if (locating)
            {
                FireCabinetPlacementTool.End();
            }
            locating = false;
            CancelPreview();
        }

        private void SetBoxes()
        {
            FireCabinetPreset previous = BoxCombo.SelectedItem as FireCabinetPreset;
            FireCabinetPreset[] eligible = FireCabinetCatalog.EligibleBoxes(SelectedType, SelectedCapacity);
            BoxCombo.ItemsSource = eligible;
            BoxCombo.SelectedItem = eligible.FirstOrDefault(box => previous != null && box.Key == previous.Key) ?? eligible[0];
            CapacityLabel.Text = "容量（" + FireCabinetCatalog.Unit(SelectedType) + "）";
        }

        private void Type_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!ready)
            {
                return;
            }
            ready = false;
            try
            {
                CapacityCombo.ItemsSource = FireCabinetCatalog.Capacities(SelectedType);
                CapacityCombo.SelectedIndex = 0;
                SetBoxes();
            }
            finally { ready = true; }
            Changed();
        }

        private void Capacity_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!ready)
            {
                return;
            }
            ready = false;
            try
            {
                SetBoxes();
            }
            finally { ready = true; }
            Changed();
        }

        private void Parameter_Changed(object sender, RoutedEventArgs e)
        {
            if (ready)
            {
                Changed();
            }
        }

        private void Changed()
        {
            revision++;
            Describe();
            if (!origin.HasValue)
            {
                return;
            }
            dirty = true;
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            PreviewText.Text = "参数已变更，请更新预览。";
        }

        private FireCabinetPlan Calculate()
        {
            double heading;
            if (!double.TryParse(HeadingText.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out heading) &&
                !double.TryParse(HeadingText.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out heading))
            {
                throw new InvalidOperationException("旋转角度应为数字。");
            }

            var box = BoxCombo.SelectedItem as FireCabinetPreset;
            return FireCabinetCalculator.Calculate(new FireCabinetParameters
            {
                ExtinguisherType = SelectedType,
                Capacity = SelectedCapacity,
                BoxKey = box == null ? "" : box.Key,
                HeadingDegrees = heading
            });
        }

        private void Describe()
        {
            try
            {
                FireCabinetPlan plan = Calculate();
                SpecificationText.Text = plan.Box.Key + " · " + plan.Box.WidthMm + "×" + plan.Box.DepthMm + "×" + plan.Box.HeightMm +
                    " mm · 配置 " + plan.ExtinguisherLabel + " ×2";
                InteriorText.Text = plan.Interior == null ? "所选箱腔无法容纳标准外观模型，将生成空箱。" :
                    "箱内外观：" + plan.Interior.Model + " ×2（外观示意，配置选型保持不变）。";
            }
            catch (Exception exception) { SpecificationText.Text = exception.Message; InteriorText.Text = ""; }
        }

        private void OnPicked(DPoint3d point)
        {
            int ticket = revision;
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (!active || !locating || ticket != revision)
                {
                    return;
                }
                origin = point;
                Regenerate();
            }), DispatcherPriority.Background);
        }

        private void Regenerate()
        {
            if (!origin.HasValue)
            {
                Status("请先点取放置点。", true);
                return;
            }
            dirty = true;
            ConfirmButton.IsEnabled = false;
            PreviewUpdateHint.Set(UpdateButton, true);
            try
            {
                FireCabinetPlan plan = Calculate();
                preview.Show(plan, origin.Value);
                dirty = false;
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = string.IsNullOrEmpty(preview.Warning) ? "预览已生成，确定后写入消防清单。" : preview.Warning;
                Status("灭火器箱预览已生成。", false);
            }
            catch (Exception exception) { PreviewText.Text = "预览未更新：" + exception.Message; Status(exception.Message, true); }
        }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                FireCabinetPlacementTool.Begin();
                locating = true;
            }
            catch (Exception exception) { Status(exception.Message, true); }
        }
        private void End_Click(object sender, RoutedEventArgs e)
        {
            FireCabinetPlacementTool.End();
        }
        private void Update_Click(object sender, RoutedEventArgs e)
        {
            Regenerate();
        }
        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            revision++;
            CancelPreview();
        }
        private void OnEnded()
        {
            revision++;
            locating = false;
            CancelPreview();
        }

        private void CancelPreview()
        {
            ConfirmButton.IsEnabled = false;
            try
            {
                preview.Cancel();
                origin = null;
                dirty = false;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = "未确认预览已取消。";
            }
            catch (Exception exception) { Status(exception.Message, true); }
        }

        private void Confirm_Click(object sender, RoutedEventArgs e)
        {
            if (dirty || !ConfirmButton.IsEnabled)
            {
                return;
            }
            ConfirmButton.IsEnabled = false;
            try
            {
                string warning = preview.Warning;
                string elapsed = WriteDuration.Measure(preview.Confirm);
                revision++;
                origin = null;
                PreviewText.Text = "已生成并写入消防清单；写入耗时 " + elapsed + "。" + warning;
                Status(PreviewText.Text, false);
            }
            catch (Exception exception) { ConfirmButton.IsEnabled = preview.HasPreview; Status("确认失败：" + exception.Message, true); }
        }

        private void Tab_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!active || !ReferenceEquals(e.Source, PageTabs) || PageTabs.SelectedIndex != 1)
            {
                return;
            }
            if (locating)
            {
                FireCabinetPlacementTool.End();
            }
            else
            {
                revision++;
                CancelPreview();
            }
            RefreshStatistics();
        }

        private bool RefreshStatistics()
        {
            try
            {
                snapshot = FireCabinetStatistics.Read();
                SummaryGrid.ItemsSource = snapshot.Summary;
                TotalsText.ToolTip = snapshot.Records.Any(record => !record.Properties.ContainsKey("ActualInteriorModelQuantity")) ?
                    "Python 旧记录的外观模型数量依据已保存的模型名称推算。" : null;
                TotalsText.Text = "箱体 " + snapshot.TotalBoxCount + " 箱 · 配置灭火器 " + snapshot.TotalExtinguisherCount +
                    " 具 · 外观模型 " + snapshot.TotalInteriorModelCount + " 具";
                ExcelButton.IsEnabled = JsonButton.IsEnabled = snapshot.Records.Count > 0;
                Status("消防统计已更新（当前 DGN 的全部模型）。", false);
                return true;
            }
            catch (Exception exception)
            {
                snapshot = null;
                SummaryGrid.ItemsSource = null;
                ExcelButton.IsEnabled = JsonButton.IsEnabled = false;
                TotalsText.Text = "统计失败：" + exception.Message;
                Status(TotalsText.Text, true);
                return false;
            }
        }

        private void Statistics_Click(object sender, RoutedEventArgs e)
        {
            RefreshStatistics();
        }
        private void Excel_Click(object sender, RoutedEventArgs e)
        {
            Export(true);
        }
        private void Json_Click(object sender, RoutedEventArgs e)
        {
            Export(false);
        }
        private void Export(bool excel)
        {
            if (!RefreshStatistics() || snapshot.Records.Count == 0)
            {
                return;
            }
            var dialog = new SaveFileDialog
            {
                Title = "导出灭火器箱清单",
                FileName = "灭火器箱清单" + (excel ? ".xlsx" : ".json"),
                Filter = excel ? "Excel 工作簿 (*.xlsx)|*.xlsx" : "JSON 文件 (*.json)|*.json",
                DefaultExt = excel ? ".xlsx" : ".json",
                AddExtension = true,
                OverwritePrompt = true
            };
            if (dialog.ShowDialog() != true)
            {
                return;
            }
            try
            {
                if (excel)
                {
                    FireCabinetExporter.WriteExcel(dialog.FileName, snapshot);
                }
                else
                {
                    FireCabinetExporter.WriteJson(dialog.FileName, snapshot);
                }
                Status("消防清单已导出：" + dialog.FileName, false);
            }
            catch (Exception exception) { Status("导出失败：" + exception.Message, true); }
        }

        private static void Status(string message, bool error)
        {
            if (MainWindow.Current != null)
            {
                MainWindow.Current.SetStatus(message, error);
            }
        }
    }
}
