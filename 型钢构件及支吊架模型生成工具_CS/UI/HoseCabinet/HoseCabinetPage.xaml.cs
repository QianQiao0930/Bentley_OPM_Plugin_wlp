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
    internal partial class HoseCabinetPage : UserControl, IWorkspacePage
    {
        private readonly HoseCabinetPreviewSession preview = new HoseCabinetPreviewSession();
        private bool ready;
        private bool active;
        private bool locating;
        private bool dirty;
        private int revision;
        private DPoint3d? origin;
        private HoseCabinetSnapshot snapshot;

        public string PageId
        {
            get
            {
                return "hose-cabinet";
            }
        }
        public string PageTitle
        {
            get
            {
                return "轻便消防水龙柜";
            }
        }
        public string PageSubtitle
        {
            get
            {
                return "15S202 第53页 · P380 卷盘 · 消防器材清单";
            }
        }
        public FrameworkElement View
        {
            get
            {
                return this;
            }
        }

        internal HoseCabinetPage()
        {
            InitializeComponent();
            ready = true;
            PageLastInput.Restore(this, PageId, "WidthText", "DepthText", "HeightText", "LowerText",
                "ModelText", "QuantityText", "HeadingText", "EquipmentCheck");
            Describe();
        }

        public void OnActivated()
        {
            if (active)
            {
                return;
            }
            active = true;
            HoseCabinetPlacementTool.Picked += OnPicked;
            HoseCabinetPlacementTool.Ended += OnEnded;
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
            PageLastInput.Save(this, PageId, "WidthText", "DepthText", "HeightText", "LowerText", "ModelText", "QuantityText", "HeadingText", "EquipmentCheck");
            revision++;
            active = false;
            HoseCabinetPlacementTool.Picked -= OnPicked;
            HoseCabinetPlacementTool.Ended -= OnEnded;
            if (locating)
            {
                HoseCabinetPlacementTool.End();
            }
            locating = false;
            CancelPreview();
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

        private HoseCabinetPlan Calculate()
        {
            int quantity;
            if (!int.TryParse(QuantityText.Text, out quantity))
            {
                throw new InvalidOperationException("灭火器数量应为整数。");
            }
            return HoseCabinetCalculator.Calculate(new HoseCabinetParameters
            {
                WidthMm = Number(WidthText, "柜宽"),
                DepthMm = Number(DepthText, "进深"),
                HeightMm = Number(HeightText, "柜高"),
                LowerHeightMm = Number(LowerText, "隔板高度"),
                HeadingDegrees = Number(HeadingText, "旋转角度"),
                ExtinguisherModel = ModelText.Text.Trim(),
                ExtinguisherQuantity = quantity,
                WithEquipment = EquipmentCheck.IsChecked == true
            });
        }

        private static double Number(TextBox field, string label)
        {
            double value;
            if (!double.TryParse(field.Text, NumberStyles.Float, CultureInfo.CurrentCulture, out value) &&
                !double.TryParse(field.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
            {
                throw new InvalidOperationException(label + "应为数字。");
            }
            return value;
        }

        private void Describe()
        {
            try
            {
                HoseCabinetPlan plan = Calculate();
                SpecificationText.Text = "P380 卷盘 · DN25 接口 · 配置灭火器 " +
                    plan.Parameters.ExtinguisherModel + " ×" + plan.Parameters.ExtinguisherQuantity;
                InteriorText.Text = !plan.Parameters.WithEquipment ? "仅生成柜体，清单保留配套配置。" :
                    plan.Interior == null ? "不配置灭火器外观模型。" :
                    "灭火器外观：" + plan.Interior.Model + "（布置示意）；卷绕及螺纹为展示细节。";
            }
            catch (Exception exception)
            {
                SpecificationText.Text = exception.Message;
                InteriorText.Text = "";
            }
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
                HoseCabinetPlan plan = Calculate();
                preview.Show(plan, origin.Value);
                dirty = false;
                ConfirmButton.IsEnabled = true;
                PreviewUpdateHint.Set(UpdateButton, false);
                PreviewText.Text = string.IsNullOrEmpty(preview.Warning) ? "预览已生成，确定后写入消防清单。" : preview.Warning;
                Status("轻便消防水龙柜预览已生成。", false);
            }
            catch (Exception exception)
            {
                PreviewText.Text = "预览未更新：" + exception.Message;
                Status(exception.Message, true);
            }
        }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                HoseCabinetPlacementTool.Begin();
                locating = true;
            }
            catch (Exception exception)
            {
                Status(exception.Message, true);
            }
        }
        private void End_Click(object sender, RoutedEventArgs e)
        {
            HoseCabinetPlacementTool.End();
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
            catch (Exception exception)
            {
                Status(exception.Message, true);
            }
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
            catch (Exception exception)
            {
                ConfirmButton.IsEnabled = preview.HasPreview;
                Status("确认失败：" + exception.Message, true);
            }
        }

        private void Tab_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (!active || !ReferenceEquals(e.Source, PageTabs) || PageTabs.SelectedIndex != 1)
            {
                return;
            }
            if (locating)
            {
                HoseCabinetPlacementTool.End();
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
                snapshot = HoseCabinetStatistics.Read();
                SummaryGrid.ItemsSource = snapshot.Summary;
                TotalsText.ToolTip = snapshot.Records.Any(record => !record.Properties.ContainsKey("ActualExtinguisherQuantity")) ?
                    "旧 Python 记录没有实际内件数量，该部分不纳入已记录模型合计；明细标为未记录。" : null;
                TotalsText.Text = "柜体 " + snapshot.TotalCabinetCount + " 柜 · 配置灭火器 " + snapshot.TotalExtinguisherCount +
                    " 具 · 已记录模型 " + snapshot.TotalActualExtinguisherCount + " 具" + (snapshot.Records.Any(record => !record.Properties.ContainsKey("ActualExtinguisherQuantity")) ? "（旧记录实际数量未记录）" : "");
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
                Title = "导出轻便消防水龙柜清单",
                FileName = "轻便消防水龙柜清单" + (excel ? ".xlsx" : ".json"),
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
                    HoseCabinetExporter.WriteExcel(dialog.FileName, snapshot);
                }
                else
                {
                    HoseCabinetExporter.WriteJson(dialog.FileName, snapshot);
                }
                Status("消防清单已导出：" + dialog.FileName, false);
            }
            catch (Exception exception)
            {
                Status("导出失败：" + exception.Message, true);
            }
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
